import asyncio
import sys
from collections.abc import Iterator, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.verdict.service import recompute_verdicts

_PARCEL_NUMBERS_SQL = text("SELECT parcel_number FROM parcel ORDER BY parcel_number")
_VACANT_PARCEL_NUMBERS_SQL = text(
    "SELECT parcel_number FROM parcel "
    "WHERE is_vacant IS TRUE AND geom_2272 IS NOT NULL ORDER BY parcel_number"
)
_DEFAULT_BATCH_SIZE = 500


def _chunks(items: Sequence[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


async def _parcel_numbers(session: AsyncSession, *, vacant_only: bool) -> list[str]:
    statement = _VACANT_PARCEL_NUMBERS_SQL if vacant_only else _PARCEL_NUMBERS_SQL
    result = await session.execute(statement)
    return [row[0] for row in result]


async def recompute_all_verdicts(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    vacant_only: bool = False,
) -> int:
    async with session_factory() as session:
        parcel_numbers = await _parcel_numbers(session, vacant_only=vacant_only)

    logger = get_logger("verdict.jobs")
    total = 0
    for chunk in _chunks(parcel_numbers, batch_size):
        async with session_factory() as session:
            total += await recompute_verdicts(session, chunk)
            await session.commit()
        logger.info("verdict_progress", done=total, of=len(parcel_numbers))
    return total


async def _run(*, vacant_only: bool) -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        count = await recompute_all_verdicts(session_factory, vacant_only=vacant_only)
        get_logger("verdict.jobs").info("recomputed_verdicts", count=count, vacant_only=vacant_only)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run(vacant_only="vacant" in sys.argv[1:]))


if __name__ == "__main__":
    main()
