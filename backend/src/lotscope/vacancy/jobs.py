import asyncio
from collections.abc import Iterator, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.vacancy.service import recompute_vacancy_confidence

_PARCEL_NUMBERS_SQL = text(
    "SELECT parcel_number FROM parcel WHERE is_vacant IS TRUE ORDER BY parcel_number"
)
_DEFAULT_BATCH_SIZE = 1000


def _chunks(items: Sequence[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


async def recompute_all_vacancy_confidence(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
) -> int:
    async with session_factory() as session:
        result = await session.execute(_PARCEL_NUMBERS_SQL)
        parcel_numbers = [row[0] for row in result]

    logger = get_logger("vacancy.jobs")
    total = 0
    for chunk in _chunks(parcel_numbers, batch_size):
        async with session_factory() as session:
            total += await recompute_vacancy_confidence(session, chunk)
            await session.commit()
        logger.info("vacancy_confidence_progress", done=total, of=len(parcel_numbers))
    return total


async def _run() -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        count = await recompute_all_vacancy_confidence(session_factory)
        get_logger("vacancy.jobs").info("recomputed_vacancy_confidence", count=count)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run())


if __name__ == "__main__":
    main()
