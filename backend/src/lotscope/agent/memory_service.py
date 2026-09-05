"""Reading and writing what the Analyst remembers."""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.agent.memory import MEMORY_WINDOW, AnalystMemory

_MAX_TEXT = 500


async def recent_memories(
    session: AsyncSession, user_id: int, *, limit: int = MEMORY_WINDOW
) -> list[AnalystMemory]:
    """The newest memories first, so the window keeps what the buyer said most recently."""
    rows = (
        await session.execute(
            select(AnalystMemory)
            .where(AnalystMemory.user_id == user_id)
            .order_by(AnalystMemory.created_at.desc(), AnalystMemory.id.desc())
            .limit(limit)
        )
    ).scalars()
    return list(rows)


async def remember(
    session: AsyncSession,
    user_id: int,
    *,
    kind: str,
    text: str,
    source_run_id: int | None = None,
) -> AnalystMemory | None:
    """Store one durable fact, unless we already hold it word for word.

    Returns None when it is a duplicate: repeating a memory does not make it truer, and a
    window of thirty fills up fast if the same preference is restated every session.
    """
    cleaned = " ".join(text.split())[:_MAX_TEXT]
    if not cleaned:
        return None

    existing = await session.scalar(
        select(AnalystMemory.id).where(
            AnalystMemory.user_id == user_id,
            AnalystMemory.text == cleaned,
        )
    )
    if existing is not None:
        return None

    memory = AnalystMemory(user_id=user_id, kind=kind, text=cleaned, source_run_id=source_run_id)
    session.add(memory)
    await session.flush()
    return memory
