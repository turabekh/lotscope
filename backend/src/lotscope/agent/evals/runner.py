import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.agent.evals import stale as stale_state
from lotscope.agent.runtime import ModelClient, create_run, ensure_conversation, run_agent
from lotscope.agent.tools import REGISTRY
from lotscope.agent.tools.registry import ToolContext
from lotscope.buybox.service import read_buy_box

TASKS_PATH = Path(__file__).with_name("tasks.yaml")

# Marks a task the cap cut off, as opposed to one deliberately not run. The first is a
# gate that did not run and must fail the suite; the second is a choice.
CAP_REACHED = "spend cap ${cap:.2f} reached"

# Sonnet list price per million tokens, used only to enforce the spend cap.
INPUT_COST_PER_MTOK = 3.0
OUTPUT_COST_PER_MTOK = 15.0


def estimate_cost(input_tokens: int, output_tokens: int) -> float:
    return (
        input_tokens / 1_000_000 * INPUT_COST_PER_MTOK
        + output_tokens / 1_000_000 * OUTPUT_COST_PER_MTOK
    )


@dataclass
class AssertionResult:
    kind: str
    value: str
    passed: bool
    why: str


@dataclass
class TaskResult:
    task_id: str
    question: str
    answer: str
    tools_called: list[str]
    assertions: list[AssertionResult] = field(default_factory=list)
    input_tokens: int = 0
    output_tokens: int = 0
    duration_ms: int = 0
    error: str | None = None
    skipped: bool = False

    @property
    def errored(self) -> bool:
        """The task could not run — an API error, not something the model got wrong."""
        return bool(self.error) and not self.skipped

    @property
    def passed(self) -> bool:
        return not self.error and all(a.passed for a in self.assertions)


def load_tasks(path: Path | None = None) -> list[dict[str, Any]]:
    loaded = yaml.safe_load((path or TASKS_PATH).read_text())
    if not isinstance(loaded, list):
        raise ValueError("tasks.yaml must hold a list of tasks.")
    return [dict(task) for task in loaded]


def check(assertion: dict[str, Any], answer: str, tools: list[str]) -> AssertionResult:
    kind = assertion["kind"]
    raw = assertion["value"]
    lowered = answer.lower()

    if kind == "tool_called":
        passed = raw in tools
    elif kind == "tool_called_any":
        passed = any(option in tools for option in raw)
    elif kind == "contains":
        passed = str(raw).lower() in lowered
    elif kind == "not_contains":
        passed = str(raw).lower() not in lowered
    elif kind == "any_of":
        passed = any(str(option).lower() in lowered for option in raw)
    elif kind == "precedes":
        # For a stale-copy answer, naming the wrong value is fine — leading with it is not.
        first, second = (str(option).lower() for option in raw)
        if first not in lowered:
            passed = False
        else:
            passed = second not in lowered or lowered.index(first) < lowered.index(second)
    else:
        raise ValueError(f"Unknown assertion kind {kind!r}.")

    return AssertionResult(
        kind=kind,
        value=str(raw),
        passed=passed,
        why=assertion.get("why", ""),
    )


async def run_task(
    session: AsyncSession,
    client: ModelClient,
    task: dict[str, Any],
    *,
    user_id: int,
    model: str,
    redis: Redis | None = None,
) -> TaskResult:
    buy_box = await read_buy_box(session, user_id)
    context = ToolContext(
        user_id=user_id,
        buy_box=buy_box.model_dump(mode="json"),
        owned_parcels=tuple(buy_box.owned_parcels),
        redis=redis,
    )
    conversation = await ensure_conversation(session, user_id, None, task["question"])
    run = await create_run(
        session,
        user_id=user_id,
        conversation=conversation,
        question=task["question"],
        model=model,
    )
    await session.commit()

    tools_called: list[str] = []
    answer_parts: list[str] = []
    started = time.monotonic()
    error: str | None = None

    async for event in run_agent(session, client, run, context=context, registry=REGISTRY):
        if event.kind == "tool_started":
            tools_called.append(event.payload["tool"])
        elif event.kind == "text_delta":
            answer_parts.append(event.payload["text"])
        elif event.kind == "error":
            error = event.payload.get("detail")
    await session.commit()

    answer = "".join(answer_parts)
    # A run that errored has no answer to judge. Checking assertions against an empty
    # string reports nonsense in both directions: every not_contains trivially passes and
    # every contains fails, so a broken run looks like a partial behaviour regression.
    assertions = (
        [] if error else [check(a, answer, tools_called) for a in task.get("assertions", [])]
    )
    return TaskResult(
        task_id=task["id"],
        question=task["question"],
        answer=answer,
        tools_called=tools_called,
        assertions=assertions,
        input_tokens=run.input_tokens,
        output_tokens=run.output_tokens,
        duration_ms=int((time.monotonic() - started) * 1000),
        error=error,
    )


async def run_suite(
    factory: async_sessionmaker[AsyncSession],
    client: ModelClient,
    *,
    user_id: int,
    model: str,
    spend_cap_usd: float,
    only: str | None = None,
    first: int | None = None,
    path: Path | None = None,
    redis: Redis | None = None,
    allow_mutation: bool = True,
) -> list[TaskResult]:
    tasks = load_tasks(path)
    if only:
        tasks = [task for task in tasks if task["id"] == only]
    if first is not None:
        tasks = tasks[:first]

    results: list[TaskResult] = []
    spent = 0.0
    for task in tasks:
        if spent >= spend_cap_usd:
            results.append(
                TaskResult(
                    task_id=task["id"],
                    question=task["question"],
                    answer="",
                    tools_called=[],
                    skipped=True,
                    error=CAP_REACHED.format(cap=spend_cap_usd),
                )
            )
            continue
        edits = stale_state.parse(task.get("stale"))
        if edits and not allow_mutation:
            # These tasks make LotScope's stored copy wrong on purpose. That is fine on a
            # local copy and unacceptable on production, where a buyer could read the
            # planted value while the task runs.
            results.append(
                TaskResult(
                    task_id=task["id"],
                    question=task["question"],
                    answer="",
                    tools_called=[],
                    skipped=True,
                    error="not run: edits stored data, so it is local-only",
                )
            )
            continue
        planted: stale_state.Planted | None = None
        try:
            async with factory() as session:
                if edits:
                    planted = await stale_state.apply(session, edits)
                result = await run_task(
                    session, client, task, user_id=user_id, model=model, redis=redis
                )
        finally:
            if planted is not None:
                async with factory() as session:
                    await stale_state.undo(session, planted)
        spent += estimate_cost(result.input_tokens, result.output_tokens)
        results.append(result)
    return results
