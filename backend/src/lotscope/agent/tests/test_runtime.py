import asyncio
from typing import Any

import pytest
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.envelope import Source, ToolResult
from lotscope.agent.models import AgentStep
from lotscope.agent.runtime import (
    MAX_TOOL_CALLS,
    AgentEvent,
    RunBudget,
    create_run,
    ensure_conversation,
    run_agent,
)
from lotscope.agent.stream import format_event
from lotscope.agent.tools.registry import ToolContext, ToolRegistry, tool

pytestmark = pytest.mark.integration


class EchoInput(BaseModel):
    parcel_number: str = Field(description="The parcel to echo back.")


def _registry() -> ToolRegistry:
    registry = ToolRegistry()

    @tool(
        name="echo_parcel",
        description="Return the parcel number you were given, with a source.",
        input_model=EchoInput,
        registry=registry,
    )
    async def _echo(session: AsyncSession, context: ToolContext, payload: EchoInput) -> ToolResult:
        return ToolResult(
            data={"parcel_number": payload.parcel_number},
            sources=[Source(name="parcel", url="https://example.test/parcel")],
            unverified=["Water liens are not held."],
        )

    return registry


class FakeModel:
    def __init__(self, turns: list[dict[str, Any]]) -> None:
        self._turns = list(turns)
        self.calls: list[dict[str, Any]] = []

    async def complete(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        if not self._turns:
            return {
                "content": [{"type": "text", "text": "done"}],
                "stop_reason": "end_turn",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            }
        return self._turns.pop(0)


def _tool_turn(tool_id: str = "tu_1", parcel: str = "phl:1") -> dict[str, Any]:
    return {
        "content": [
            {
                "type": "tool_use",
                "id": tool_id,
                "name": "echo_parcel",
                "input": {"parcel_number": parcel},
            }
        ],
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 100, "output_tokens": 20},
    }


def _text_turn(body: str = "2138 N Fairhill St is vacant.") -> dict[str, Any]:
    return {
        "content": [{"type": "text", "text": body}],
        "stop_reason": "end_turn",
        "usage": {"input_tokens": 120, "output_tokens": 40},
    }


async def _user(session: AsyncSession, email: str) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:e, 'x', 'user', 'user', true)"
        ),
        {"e": email},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email}))


async def _run(session: AsyncSession, email: str, question: str = "what about phl:1?"):  # type: ignore[no-untyped-def]
    user_id = await _user(session, email)
    conversation = await ensure_conversation(session, user_id, None, question)
    run = await create_run(
        session, user_id=user_id, conversation=conversation, question=question, model="fake-model"
    )
    return user_id, run


async def _collect(events) -> list[AgentEvent]:  # type: ignore[no-untyped-def]
    return [event async for event in events]


def test_the_registry_emits_an_anthropic_tool_schema() -> None:
    schemas = _registry().schemas()

    assert len(schemas) == 1
    schema = schemas[0]
    assert schema["name"] == "echo_parcel"
    assert schema["description"].startswith("Return the parcel number")
    assert schema["input_schema"]["type"] == "object"
    assert "parcel_number" in schema["input_schema"]["properties"]
    assert schema["input_schema"]["required"] == ["parcel_number"]
    assert "title" not in schema["input_schema"]


def test_registering_the_same_tool_twice_is_refused() -> None:
    registry = _registry()

    with pytest.raises(ValueError, match="already registered"):

        @tool(
            name="echo_parcel",
            description="A second echo.",
            input_model=EchoInput,
            registry=registry,
        )
        async def _dup(
            session: AsyncSession, context: ToolContext, payload: EchoInput
        ) -> ToolResult:
            return ToolResult()


async def test_a_tool_call_then_text_runs_the_loop_to_an_answer(
    db_session: AsyncSession,
) -> None:
    user_id, run = await _run(db_session, "loop@example.com")
    model = FakeModel([_tool_turn(), _text_turn()])

    events = await _collect(
        run_agent(
            db_session,
            model,
            run,
            context=ToolContext(user_id=user_id),
            registry=_registry(),
        )
    )

    kinds = [event.kind for event in events]
    assert kinds == ["tool_started", "tool_finished", "text", "final"]
    assert run.status == "succeeded"
    assert run.answer == "2138 N Fairhill St is vacant."
    assert run.tool_calls == 1
    assert run.input_tokens == 220
    assert run.output_tokens == 60


async def test_the_tool_envelope_is_persisted_with_its_sources(
    db_session: AsyncSession,
) -> None:
    user_id, run = await _run(db_session, "persist@example.com")
    model = FakeModel([_tool_turn(parcel="phl:99"), _text_turn()])

    await _collect(
        run_agent(
            db_session, model, run, context=ToolContext(user_id=user_id), registry=_registry()
        )
    )

    rows = (
        (
            await db_session.execute(
                text(
                    "SELECT sequence, kind, tool_name, tool_input, envelope, text FROM agent_step "
                    "WHERE run_id = :r ORDER BY sequence"
                ),
                {"r": run.id},
            )
        )
        .mappings()
        .all()
    )

    assert [row["kind"] for row in rows] == ["tool", "text"]
    step = rows[0]
    assert step["tool_name"] == "echo_parcel"
    assert step["tool_input"] == {"parcel_number": "phl:99"}
    assert step["envelope"]["data"] == {"parcel_number": "phl:99"}
    assert step["envelope"]["sources"][0]["name"] == "parcel"
    assert step["envelope"]["unverified"] == ["Water liens are not held."]


async def test_the_model_receives_the_envelope_verbatim(db_session: AsyncSession) -> None:
    user_id, run = await _run(db_session, "verbatim@example.com")
    model = FakeModel([_tool_turn(), _text_turn()])

    await _collect(
        run_agent(
            db_session, model, run, context=ToolContext(user_id=user_id), registry=_registry()
        )
    )

    second_call = model.calls[1]
    tool_result = second_call["messages"][-1]["content"][0]
    assert tool_result["type"] == "tool_result"
    assert tool_result["tool_use_id"] == "tu_1"
    assert '"sources"' in tool_result["content"]
    assert '"unverified"' in tool_result["content"]


async def test_the_tool_call_ceiling_stops_a_looping_model(db_session: AsyncSession) -> None:
    user_id, run = await _run(db_session, "ceiling@example.com")
    model = FakeModel([_tool_turn(tool_id=f"tu_{n}") for n in range(MAX_TOOL_CALLS + 5)])

    events = await _collect(
        run_agent(
            db_session, model, run, context=ToolContext(user_id=user_id), registry=_registry()
        )
    )

    budget = next(event for event in events if event.kind == "budget")
    assert budget.payload["reason"] == "tool_call_limit"
    assert run.tool_calls == MAX_TOOL_CALLS
    assert run.stop_reason == "tool_call_limit"


async def test_the_token_budget_stops_the_run(db_session: AsyncSession) -> None:
    user_id, run = await _run(db_session, "tokens@example.com")
    model = FakeModel([_tool_turn(tool_id=f"tu_{n}") for n in range(10)])

    events = await _collect(
        run_agent(
            db_session,
            model,
            run,
            context=ToolContext(user_id=user_id),
            registry=_registry(),
            budget=RunBudget(max_total_tokens=300),
        )
    )

    budget = next(event for event in events if event.kind == "budget")
    assert budget.payload["reason"] == "token_budget"
    assert run.stop_reason == "token_budget"
    assert run.input_tokens + run.output_tokens >= 300


async def test_cancellation_stops_before_the_next_model_call(db_session: AsyncSession) -> None:
    user_id, run = await _run(db_session, "cancel@example.com")
    model = FakeModel([_tool_turn(), _text_turn()])
    calls = {"n": 0}

    def should_cancel() -> bool:
        calls["n"] += 1
        return calls["n"] > 1

    events = await _collect(
        run_agent(
            db_session,
            model,
            run,
            context=ToolContext(user_id=user_id),
            registry=_registry(),
            should_cancel=should_cancel,
        )
    )

    assert [event.kind for event in events][-2:] == ["cancelled", "final"]
    assert run.status == "cancelled"
    assert len(model.calls) == 1


async def test_a_failing_tool_becomes_an_unverified_envelope_not_a_crash(
    db_session: AsyncSession,
) -> None:
    registry = ToolRegistry()

    @tool(
        name="boom",
        description="Always fails.",
        input_model=EchoInput,
        registry=registry,
    )
    async def _boom(session: AsyncSession, context: ToolContext, payload: EchoInput) -> ToolResult:
        raise RuntimeError("upstream is down")

    user_id, run = await _run(db_session, "boom@example.com")
    model = FakeModel(
        [
            {
                "content": [
                    {
                        "type": "tool_use",
                        "id": "tu_1",
                        "name": "boom",
                        "input": {"parcel_number": "phl:1"},
                    }
                ],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
            _text_turn("I could not read that."),
        ]
    )

    events = await _collect(
        run_agent(db_session, model, run, context=ToolContext(user_id=user_id), registry=registry)
    )

    finished = next(event for event in events if event.kind == "tool_finished")
    assert "boom failed: upstream is down" in finished.payload["unverified"][0]
    assert run.status == "succeeded"


async def test_an_unknown_tool_is_reported_rather_than_raising(
    db_session: AsyncSession,
) -> None:
    user_id, run = await _run(db_session, "unknown@example.com")
    model = FakeModel(
        [
            {
                "content": [{"type": "tool_use", "id": "tu_1", "name": "nope", "input": {}}],
                "stop_reason": "tool_use",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
            _text_turn("No such tool."),
        ]
    )

    events = await _collect(
        run_agent(
            db_session, model, run, context=ToolContext(user_id=user_id), registry=_registry()
        )
    )

    finished = next(event for event in events if event.kind == "tool_finished")
    assert "No tool named 'nope' exists." in finished.payload["unverified"]


async def test_the_sse_stream_orders_tool_events_before_text_and_ends_with_final(
    db_session: AsyncSession,
) -> None:
    user_id, run = await _run(db_session, "sse@example.com")
    model = FakeModel([_tool_turn(), _text_turn()])

    frames = [
        format_event(event)
        async for event in run_agent(
            db_session, model, run, context=ToolContext(user_id=user_id), registry=_registry()
        )
    ]

    names = [frame.split("\n")[0].removeprefix("event: ") for frame in frames]
    assert names == ["tool_started", "tool_finished", "text", "final"]
    assert all(frame.endswith("\n\n") for frame in frames)
    assert '"sources"' in frames[1]
    assert '"answer"' in frames[-1]


def test_an_sse_frame_is_shaped_for_eventsource() -> None:
    frame = format_event(AgentEvent("text", {"text": "hello"}))

    assert frame == 'event: text\ndata: {"text": "hello"}\n\n'


async def test_the_buy_box_reaches_the_system_prompt(db_session: AsyncSession) -> None:
    user_id, run = await _run(db_session, "context@example.com")
    model = FakeModel([_text_turn("ok")])

    await _collect(
        run_agent(
            db_session,
            model,
            run,
            context=ToolContext(
                user_id=user_id,
                buy_box={"max_bid": 95000, "min_lot_sqft": 640},
                owned_parcels=("phl:1", "phl:2"),
            ),
            registry=_registry(),
        )
    )

    system = model.calls[0]["system"]
    assert "95000" in system
    assert "phl:1, phl:2" in system
    assert "unverified" in system.lower()
    assert "never infer" in system.lower()


async def test_a_buyer_with_no_buy_box_is_stated_not_invented(db_session: AsyncSession) -> None:
    user_id, run = await _run(db_session, "nobox@example.com")
    model = FakeModel([_text_turn("ok")])

    await _collect(
        run_agent(
            db_session, model, run, context=ToolContext(user_id=user_id), registry=_registry()
        )
    )

    assert "has not set a buy box yet" in model.calls[0]["system"]


async def test_a_hard_cancel_marks_the_run_and_re_raises(db_session: AsyncSession) -> None:
    class Slow:
        async def complete(self, **kwargs: Any) -> dict[str, Any]:
            raise asyncio.CancelledError

    user_id, run = await _run(db_session, "hardcancel@example.com")

    with pytest.raises(asyncio.CancelledError):
        await _collect(
            run_agent(
                db_session, Slow(), run, context=ToolContext(user_id=user_id), registry=_registry()
            )
        )

    assert run.status == "cancelled"


async def test_a_model_failure_is_recorded_on_the_run(db_session: AsyncSession) -> None:
    class Broken:
        async def complete(self, **kwargs: Any) -> dict[str, Any]:
            raise RuntimeError("model refused")

    user_id, run = await _run(db_session, "broken@example.com")

    events = await _collect(
        run_agent(
            db_session, Broken(), run, context=ToolContext(user_id=user_id), registry=_registry()
        )
    )

    assert events[-1].kind == "error"
    assert run.status == "failed"
    assert run.error == "model refused"


async def test_steps_are_numbered_in_the_order_they_happened(db_session: AsyncSession) -> None:
    user_id, run = await _run(db_session, "seq@example.com")
    model = FakeModel([_tool_turn(), _tool_turn(tool_id="tu_2"), _text_turn()])

    await _collect(
        run_agent(
            db_session, model, run, context=ToolContext(user_id=user_id), registry=_registry()
        )
    )

    rows = (
        await db_session.execute(
            text("SELECT sequence, kind FROM agent_step WHERE run_id = :r ORDER BY sequence"),
            {"r": run.id},
        )
    ).all()

    assert [row.sequence for row in rows] == [1, 2, 3]
    assert [row.kind for row in rows] == ["tool", "tool", "text"]
    assert (
        await db_session.scalar(
            text("SELECT count(*) FROM agent_step WHERE run_id = :r"), {"r": run.id}
        )
        == 3
    )
    assert AgentStep.__tablename__ == "agent_step"
