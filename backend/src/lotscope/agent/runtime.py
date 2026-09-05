import asyncio
import time
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Any, Protocol

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.envelope import ToolResult, empty
from lotscope.agent.models import AgentConversation, AgentRun, AgentStep
from lotscope.agent.prompts import system_blocks
from lotscope.agent.tools.registry import REGISTRY, ToolContext, ToolRegistry
from lotscope.core.config import Settings
from lotscope.core.logging import get_logger

MAX_TOOL_CALLS = 25
DEFAULT_TOKEN_BUDGET = 120_000
DEFAULT_MAX_OUTPUT_TOKENS = 2_000

_logger = get_logger(__name__)


@dataclass(frozen=True)
class AgentEvent:
    kind: str
    payload: dict[str, Any] = field(default_factory=dict)


class ModelClient(Protocol):
    def stream(
        self,
        *,
        model: str,
        system: str,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        max_tokens: int,
    ) -> AsyncIterator[dict[str, Any]]: ...


@dataclass
class RunBudget:
    max_tool_calls: int = MAX_TOOL_CALLS
    max_total_tokens: int = DEFAULT_TOKEN_BUDGET
    max_output_tokens: int = DEFAULT_MAX_OUTPUT_TOKENS

    input_tokens: int = 0
    output_tokens: int = 0
    tool_calls: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def record(self, usage: dict[str, Any]) -> None:
        self.input_tokens += int(usage.get("input_tokens", 0) or 0)
        self.output_tokens += int(usage.get("output_tokens", 0) or 0)

    def exhausted(self) -> str | None:
        if self.tool_calls >= self.max_tool_calls:
            return "tool_call_limit"
        if self.total_tokens >= self.max_total_tokens:
            return "token_budget"
        return None


def analyst_model(settings: Settings) -> str:
    return settings.analyst_model


async def ensure_conversation(
    session: AsyncSession, user_id: int, conversation_id: int | None, question: str
) -> AgentConversation:
    if conversation_id is not None:
        found = (
            await session.execute(
                select(AgentConversation).where(
                    AgentConversation.id == conversation_id,
                    AgentConversation.user_id == user_id,
                )
            )
        ).scalar_one_or_none()
        if found is not None:
            return found
    conversation = AgentConversation(user_id=user_id, title=question[:200])
    session.add(conversation)
    await session.flush()
    return conversation


async def create_run(
    session: AsyncSession,
    *,
    user_id: int,
    conversation: AgentConversation,
    question: str,
    model: str,
) -> AgentRun:
    run = AgentRun(
        conversation_id=conversation.id,
        user_id=user_id,
        status="running",
        model=model,
        question=question,
    )
    session.add(run)
    await session.flush()
    return run


async def _record_step(
    session: AsyncSession,
    run_id: int,
    sequence: int,
    *,
    kind: str,
    tool_name: str | None = None,
    tool_input: dict[str, Any] | None = None,
    envelope: dict[str, Any] | None = None,
    text: str | None = None,
    input_tokens: int = 0,
    output_tokens: int = 0,
    duration_ms: int | None = None,
) -> None:
    session.add(
        AgentStep(
            run_id=run_id,
            sequence=sequence,
            kind=kind,
            tool_name=tool_name,
            tool_input=tool_input,
            envelope=envelope,
            text=text,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            duration_ms=duration_ms,
        )
    )
    await session.flush()


async def _run_tool(
    session: AsyncSession,
    registry: ToolRegistry,
    context: ToolContext,
    name: str,
    raw_input: dict[str, Any],
) -> ToolResult:
    registered = registry.get(name)
    if registered is None:
        return empty(f"No tool named {name!r} exists.")
    try:
        payload = registered.input_model.model_validate(raw_input)
    except Exception as cause:
        return empty(f"The input to {name} did not validate: {cause}")
    try:
        async with session.begin_nested():
            return await registered.handler(session, context, payload)
    except asyncio.CancelledError:
        raise
    except Exception as cause:
        _logger.error("agent_tool_failed", tool=name, error=str(cause))
        return empty(f"{name} failed: {cause}")


async def run_agent(
    session: AsyncSession,
    client: ModelClient,
    run: AgentRun,
    *,
    context: ToolContext,
    history: list[dict[str, Any]] | None = None,
    registry: ToolRegistry | None = None,
    budget: RunBudget | None = None,
    should_cancel: Callable[[], bool] | None = None,
) -> AsyncIterator[AgentEvent]:
    tools = registry or REGISTRY
    limits = budget or RunBudget()
    started = time.monotonic()
    sequence = 0
    context = replace(context, agent_run_id=run.id)
    system = system_blocks(context.buy_box, list(context.owned_parcels))
    messages: list[dict[str, Any]] = list(history or [])
    messages.append({"role": "user", "content": run.question})
    answer_parts: list[str] = []
    stop_reason = "end_turn"

    try:
        while True:
            if should_cancel is not None and should_cancel():
                stop_reason = "cancelled"
                run.status = "cancelled"
                yield AgentEvent("cancelled", {"reason": "The run was cancelled."})
                break

            exhausted = limits.exhausted()
            if exhausted is not None:
                stop_reason = exhausted
                yield AgentEvent(
                    "budget",
                    {
                        "reason": exhausted,
                        "tool_calls": limits.tool_calls,
                        "total_tokens": limits.total_tokens,
                    },
                )
                break

            turn_started = time.monotonic()
            response: dict[str, Any] = {}
            turn_text: list[str] = []
            async for chunk in client.stream(
                model=run.model,
                system=system,
                messages=messages,
                tools=tools.schemas(),
                max_tokens=limits.max_output_tokens,
            ):
                if chunk.get("type") == "text_delta":
                    delta = chunk.get("text", "")
                    if delta:
                        turn_text.append(delta)
                        answer_parts.append(delta)
                        yield AgentEvent("text_delta", {"text": delta})
                elif chunk.get("type") == "message":
                    response = chunk
            turn_ms = int((time.monotonic() - turn_started) * 1000)
            usage = response.get("usage", {}) or {}
            limits.record(usage)

            blocks = response.get("content", []) or []
            tool_blocks = [b for b in blocks if b.get("type") == "tool_use"]

            if turn_text:
                sequence += 1
                await _record_step(
                    session,
                    run.id,
                    sequence,
                    kind="text",
                    text="".join(turn_text),
                    input_tokens=int(usage.get("input_tokens", 0) or 0),
                    output_tokens=int(usage.get("output_tokens", 0) or 0),
                    duration_ms=turn_ms,
                )

            if not tool_blocks:
                stop_reason = response.get("stop_reason") or "end_turn"
                break

            messages.append({"role": "assistant", "content": blocks})
            tool_results: list[dict[str, Any]] = []

            for block in tool_blocks:
                name = block.get("name", "")
                raw_input = block.get("input", {}) or {}
                limits.tool_calls += 1
                sequence += 1
                yield AgentEvent("tool_started", {"tool": name, "input": raw_input})

                tool_started = time.monotonic()
                result = await _run_tool(session, tools, context, name, raw_input)
                tool_ms = int((time.monotonic() - tool_started) * 1000)
                envelope = result.model_dump(mode="json")

                await _record_step(
                    session,
                    run.id,
                    sequence,
                    kind="tool",
                    tool_name=name,
                    tool_input=raw_input,
                    envelope=envelope,
                    duration_ms=tool_ms,
                )
                yield AgentEvent(
                    "tool_finished",
                    {
                        "tool": name,
                        "sources": envelope.get("sources", []),
                        "unverified": envelope.get("unverified", []),
                        "duration_ms": tool_ms,
                    },
                )
                tool_results.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": block.get("id", ""),
                        "content": result.to_model_json(),
                    }
                )

            messages.append({"role": "user", "content": tool_results})

        run.answer = "".join(answer_parts) or None
        run.stop_reason = stop_reason
        run.input_tokens = limits.input_tokens
        run.output_tokens = limits.output_tokens
        run.tool_calls = limits.tool_calls
        run.duration_ms = int((time.monotonic() - started) * 1000)
        run.finished_at = datetime.now(UTC)
        if run.status == "running":
            run.status = "succeeded"
        await session.flush()

        yield AgentEvent(
            "final",
            {
                "run_id": run.id,
                "status": run.status,
                "stop_reason": stop_reason,
                "answer": run.answer,
                "input_tokens": limits.input_tokens,
                "output_tokens": limits.output_tokens,
                "tool_calls": limits.tool_calls,
                "duration_ms": run.duration_ms,
            },
        )
    except asyncio.CancelledError:
        run.status = "cancelled"
        run.stop_reason = "cancelled"
        run.finished_at = datetime.now(UTC)
        await session.flush()
        raise
    except Exception as cause:
        run.status = "failed"
        run.error = str(cause)
        run.finished_at = datetime.now(UTC)
        await session.flush()
        _logger.error("agent_run_failed", run_id=run.id, error=str(cause))
        yield AgentEvent("error", {"detail": str(cause)})
