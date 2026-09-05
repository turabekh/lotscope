"""Fold a long conversation down into memory.

A conversation past fifty turns costs more to carry than it is worth, and the useful part of
it is rarely the transcript — it is the handful of durable things the buyer said. This job
asks the model for those, stores them as memory rows, and marks how far it got so the same
turns are never summarised twice.
"""

from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.agent.memory import AnalystMemory
from lotscope.agent.memory_service import remember
from lotscope.agent.models import AgentRun
from lotscope.agent.runtime import ModelClient
from lotscope.core.config import Settings
from lotscope.core.logging import get_logger

SUMMARY_TURN_THRESHOLD = 50
MAX_TURNS_PER_SUMMARY = 200
SUMMARY_MAX_TOKENS = 700

_logger = get_logger(__name__)

SUMMARY_PROMPT = """\
You are compressing a long conversation between a Philadelphia land buyer and their analyst \
into what is worth remembering about the buyer.

Keep only what will still be true next month and what no database can tell us: rules they \
hold about what they buy, decisions they made and why, things that happened to them, \
constraints they stated.

Drop everything a tool can look up — owners, prices, violation counts, sale statuses, \
parcel facts. Those change, and a remembered copy becomes a stale fact asserted as current.

Answer with one line per memory, at most six lines, no numbering, no preamble. If there is \
nothing durable in the conversation, answer with the single word NOTHING."""

_LONG_CONVERSATIONS_SQL = text(
    "SELECT r.conversation_id, r.user_id, count(*) AS turns, max(r.id) AS last_run_id "
    "FROM agent_run r "
    "WHERE r.status = 'succeeded' AND r.id > coalesce(("
    "  SELECT max(m.source_run_id) FROM analyst_memory m "
    "  JOIN agent_run mr ON mr.id = m.source_run_id "
    "  WHERE mr.conversation_id = r.conversation_id"
    "), 0) "
    "GROUP BY r.conversation_id, r.user_id "
    "HAVING count(*) > :threshold "
    "ORDER BY r.conversation_id"
)


async def _turns(session: AsyncSession, conversation_id: int, after_run_id: int) -> list[AgentRun]:
    rows = (
        await session.execute(
            select(AgentRun)
            .where(
                AgentRun.conversation_id == conversation_id,
                AgentRun.id > after_run_id,
                AgentRun.status == "succeeded",
            )
            .order_by(AgentRun.id)
            .limit(MAX_TURNS_PER_SUMMARY)
        )
    ).scalars()
    return list(rows)


async def _watermark(session: AsyncSession, conversation_id: int) -> int:
    found = await session.scalar(
        select(AnalystMemory.source_run_id)
        .join(AgentRun, AgentRun.id == AnalystMemory.source_run_id)
        .where(AgentRun.conversation_id == conversation_id)
        .order_by(AnalystMemory.source_run_id.desc())
        .limit(1)
    )
    return int(found or 0)


def transcript(turns: list[AgentRun]) -> str:
    lines: list[str] = []
    for turn in turns:
        lines.append(f"BUYER: {turn.question.strip()}")
        if turn.answer:
            lines.append(f"ANALYST: {turn.answer.strip()[:1200]}")
    return "\n".join(lines)


async def _ask(client: ModelClient, model: str, body: str) -> str:
    parts: list[str] = []
    async for chunk in client.stream(
        model=model,
        system=SUMMARY_PROMPT,
        messages=[{"role": "user", "content": body}],
        tools=[],
        max_tokens=SUMMARY_MAX_TOKENS,
    ):
        if chunk.get("type") == "text_delta":
            parts.append(chunk.get("text", ""))
    return "".join(parts).strip()


def parse_memories(answer: str) -> list[str]:
    if not answer or answer.strip().upper().startswith("NOTHING"):
        return []
    found: list[str] = []
    for raw in answer.splitlines():
        line = raw.strip().lstrip("-•*").strip()
        if len(line) >= 10:
            found.append(line)
    return found[:6]


async def summarise_long_conversations(
    factory: async_sessionmaker[AsyncSession],
    client: ModelClient,
    settings: Settings,
    *,
    threshold: int = SUMMARY_TURN_THRESHOLD,
) -> int:
    stored = 0
    async with factory() as session:
        candidates: list[dict[str, Any]] = [
            dict(row)
            for row in (
                await session.execute(_LONG_CONVERSATIONS_SQL, {"threshold": threshold})
            ).mappings()
        ]

    for candidate in candidates:
        conversation_id = int(candidate["conversation_id"])
        async with factory() as session:
            after = await _watermark(session, conversation_id)
            turns = await _turns(session, conversation_id, after)
            if len(turns) <= threshold:
                continue
            body = transcript(turns)
            last_run_id = turns[-1].id

        try:
            answer = await _ask(client, settings.analyst_model, body)
        except Exception as cause:
            _logger.error(
                "conversation_summary_failed", conversation_id=conversation_id, error=str(cause)
            )
            continue

        lines = parse_memories(answer)
        if not lines:
            _logger.info("conversation_had_nothing_durable", conversation_id=conversation_id)
            continue

        async with factory() as session:
            for line in lines:
                # source_run_id is both provenance and watermark: it says which turn this
                # memory came out of, and stops those turns being summarised again.
                if await remember(
                    session,
                    int(candidate["user_id"]),
                    kind="fact",
                    text=line,
                    source_run_id=last_run_id,
                ):
                    stored += 1
            await session.commit()
        _logger.info(
            "conversation_summarised",
            conversation_id=conversation_id,
            turns=len(turns),
            memories=len(lines),
        )
    return stored
