"""Memory, the summariser, and brief mode."""

from collections.abc import AsyncIterator
from datetime import UTC, date, datetime
from typing import Any, cast, get_args

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.agent.brief import (
    NO_TOOLS,
    brief_question,
    generate_brief,
    send_daily_briefs,
)
from lotscope.agent.memory import MEMORY_KINDS
from lotscope.agent.memory_service import recent_memories, remember
from lotscope.agent.models import AgentRun
from lotscope.agent.prompts import memory_context, system_blocks
from lotscope.agent.signals import AnalystSignal
from lotscope.agent.summarise import parse_memories, transcript
from lotscope.agent.tools.memory_tools import MemoryKind, RememberInput, remember_tool
from lotscope.agent.tools.registry import ToolContext
from lotscope.core.config import get_settings

pytestmark = pytest.mark.integration

TODAY = date(2026, 9, 5)


@pytest.fixture
def session_factory(db_session: AsyncSession) -> async_sessionmaker[AsyncSession]:
    """A factory on the test's own connection, so a job's sessions see the fixture rows."""
    return async_sessionmaker(
        bind=db_session.bind, expire_on_commit=False, join_transaction_mode="create_savepoint"
    )


class FakeModel:
    def __init__(self, text_out: str) -> None:
        self._text = text_out
        self.calls: list[dict[str, Any]] = []

    async def stream(self, **kwargs: Any) -> AsyncIterator[dict[str, Any]]:
        self.calls.append(kwargs)
        yield {"type": "text_delta", "text": self._text}
        yield {
            "type": "message",
            "content": [{"type": "text", "text": self._text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 120, "output_tokens": 40},
        }


class CountingSender:
    def __init__(self) -> None:
        self.sent: list[dict[str, Any]] = []

    async def send(self, **kwargs: Any) -> None:
        self.sent.append(kwargs)


async def _user(session: AsyncSession, email: str) -> int:
    return int(
        await session.scalar(
            text(
                "INSERT INTO app_user (email, hashed_password, role, tier, is_active, "
                "email_verified_at) VALUES (:e, 'x', 'user', 'user', true, now()) RETURNING id"
            ),
            {"e": email},
        )
    )


async def _buy_box(session: AsyncSession, user_id: int) -> None:
    await session.execute(
        text(
            "INSERT INTO buy_box (user_id, areas, target_use, owned_parcels, zoning_codes, "
            "assumptions) VALUES (:u, '[]'::jsonb, 'build', '[]'::jsonb, '[]'::jsonb, "
            "'{}'::jsonb)"
        ),
        {"u": user_id},
    )
    await session.flush()


def _signal(user_id: int) -> AnalystSignal:
    return AnalystSignal(
        user_id=user_id,
        signal_key="sale_status:sheriff_sale_event:1",
        signal_date=TODAY,
        kind="sale_status",
        parcel_number="phl:191357500",
        headline="3862 Aspen St: status Active → Postponed",
        detail={"case_number": "2301-1234"},
        source="civilview",
        source_url="https://philadelphia.sheriffsale.com/",
        source_table="sheriff_sale_event",
        source_row_id="1",
        observed_at=datetime(2026, 9, 5, 5, 0, tzinfo=UTC),
    )


# --- memory ------------------------------------------------------------------------------


def test_the_tool_offers_exactly_the_kinds_the_table_accepts() -> None:
    """The model is told these; the table enforces them. They must not drift apart."""
    assert set(MEMORY_KINDS) == set(get_args(MemoryKind))


async def test_a_memory_is_stored_once_however_often_it_is_repeated(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "mem-dupe@example.com")

    first = await remember(db_session, user_id, kind="preference", text="I only buy west of Broad")
    again = await remember(db_session, user_id, kind="preference", text="I only buy west of Broad")

    assert first is not None
    assert again is None
    assert len(await recent_memories(db_session, user_id)) == 1


async def test_the_remember_tool_records_the_run_that_stored_it(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "mem-run@example.com")
    result = await remember_tool(
        db_session,
        ToolContext(user_id=user_id, agent_run_id=None),
        RememberInput(text="I lost 2138 Fairhill at auction last year", kind="fact"),
    )

    assert result.data["text"] == "I lost 2138 Fairhill at auction last year"
    assert any("memory, not evidence" in note for note in result.unverified)


async def test_the_newest_memories_are_the_ones_that_reach_the_model(
    db_session: AsyncSession,
) -> None:
    user_id = await _user(db_session, "mem-window@example.com")
    for index in range(35):
        await remember(db_session, user_id, kind="fact", text=f"memory number {index}")

    window = await recent_memories(db_session, user_id, limit=30)

    assert len(window) == 30
    assert window[0].text == "memory number 34"


def test_memories_reach_the_system_prompt() -> None:
    blocks = system_blocks({}, [], ["I only buy west of Broad"])
    assert "west of Broad" in blocks
    assert "never as a substitute for looking something up" in memory_context(["x"])


def test_with_no_memories_the_prompt_says_so_rather_than_inventing_any() -> None:
    assert "not been told anything durable" in memory_context([])


# --- summariser --------------------------------------------------------------------------


def test_nothing_durable_stores_nothing() -> None:
    assert parse_memories("NOTHING") == []
    assert parse_memories("") == []


def test_a_summary_is_split_into_one_memory_per_line() -> None:
    lines = parse_memories("- buys only west of Broad\n- walked away from 2138 Fairhill\n")
    assert lines == ["buys only west of Broad", "walked away from 2138 Fairhill"]


def test_a_summary_keeps_at_most_six_lines() -> None:
    assert len(parse_memories("\n".join(f"a memory line {i}" for i in range(20)))) == 6


# --- brief -------------------------------------------------------------------------------


def test_the_brief_question_carries_every_signal_with_its_row() -> None:
    question = brief_question([_signal(1)], None, "https://example.test")
    assert "sheriff_sale_event#1" in question
    assert "Postponed" in question


def test_a_packet_scheduled_today_becomes_one_line_not_a_restatement() -> None:
    question = brief_question(
        [_signal(1)], {"id": 3, "sale_date": TODAY, "status": "ready"}, "https://example.test"
    )
    assert "do not restate its contents" in question.lower()
    assert "/packets" in question


def test_brief_mode_gives_the_model_no_tools() -> None:
    assert NO_TOOLS.names() == []


def test_brief_mode_adds_the_fixed_instruction() -> None:
    blocks = system_blocks({}, [], [], mode="brief")
    assert "At most 8 items" in blocks
    assert "does not go in the brief" in blocks
    assert "At most 8 items" not in system_blocks({}, [], [])


async def test_no_signals_means_no_brief_and_no_email(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "brief-quiet@example.com")
    await _buy_box(db_session, user_id)
    model = FakeModel("should never be written")

    brief = await generate_brief(
        db_session, model, get_settings(), user_id=user_id, on_date=TODAY, signals=[]
    )

    assert brief is None
    assert model.calls == []
    stored = await db_session.scalar(
        text("SELECT count(*) FROM analyst_brief WHERE user_id = :u"), {"u": user_id}
    )
    assert stored == 0


async def test_signals_produce_a_brief_that_records_its_run(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "brief-loud@example.com")
    await _buy_box(db_session, user_id)
    db_session.add(_signal(user_id))
    await db_session.flush()

    brief = await generate_brief(
        db_session,
        FakeModel("3862 Aspen St was postponed."),
        get_settings(),
        user_id=user_id,
        on_date=TODAY,
    )

    assert brief is not None
    assert brief.text == "3862 Aspen St was postponed."
    assert brief.signal_count == 1
    assert brief.run_id is not None


async def test_a_second_run_on_the_same_day_reuses_the_brief(db_session: AsyncSession) -> None:
    user_id = await _user(db_session, "brief-idem@example.com")
    await _buy_box(db_session, user_id)
    db_session.add(_signal(user_id))
    await db_session.flush()

    first = await generate_brief(
        db_session, FakeModel("first"), get_settings(), user_id=user_id, on_date=TODAY
    )
    second = await generate_brief(
        db_session, FakeModel("second"), get_settings(), user_id=user_id, on_date=TODAY
    )

    assert first is not None
    assert second is not None
    assert first.id == second.id
    assert second.text == "first"


async def test_a_quiet_night_sends_nothing_at_all(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_id = await _user(db_session, "brief-nomail@example.com")
    await _buy_box(db_session, user_id)
    await db_session.commit()
    sender = CountingSender()

    sent = await send_daily_briefs(
        session_factory, FakeModel("unused"), sender, get_settings(), on_date=TODAY
    )

    assert sent == 0
    assert sender.sent == []


async def test_a_brief_is_emailed_once_and_marked(
    db_session: AsyncSession, session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_id = await _user(db_session, "brief-mail@example.com")
    await _buy_box(db_session, user_id)
    db_session.add(_signal(user_id))
    await db_session.commit()
    sender = CountingSender()

    first = await send_daily_briefs(
        session_factory, FakeModel("Postponed."), sender, get_settings(), on_date=TODAY
    )
    second = await send_daily_briefs(
        session_factory, FakeModel("Postponed."), sender, get_settings(), on_date=TODAY
    )

    assert first == 1
    assert second == 0
    assert len(sender.sent) == 1
    assert "Postponed." in sender.sent[0]["text"]


def test_the_transcript_pairs_each_question_with_its_answer() -> None:
    class Turn:
        def __init__(self, q: str, a: str | None) -> None:
            self.question, self.answer = q, a

    turns = cast("list[AgentRun]", [Turn("who owns it", "ACME LLC"), Turn("and next door", None)])
    body = transcript(turns)
    assert "BUYER: who owns it" in body
    assert "ANALYST: ACME LLC" in body
    # The unanswered turn contributes no ANALYST line rather than an empty one.
    assert body.count("ANALYST") == 1
