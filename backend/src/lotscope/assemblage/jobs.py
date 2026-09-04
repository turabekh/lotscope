import asyncio
from collections.abc import Iterator, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.assemblage.service import recompute_assemblage
from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger

_VACANT_PARCEL_NUMBERS_SQL = text(
    "SELECT parcel_number FROM parcel "
    "WHERE is_vacant IS TRUE AND geom_local IS NOT NULL "
    "AND (CAST(:market AS text) IS NULL OR market_code = CAST(:market AS text)) "
    "ORDER BY parcel_number"
)
_DEFAULT_BATCH_SIZE = 500


def _chunks(items: Sequence[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


async def recompute_all_assemblage(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    market: str | None = None,
) -> int:
    async with session_factory() as session:
        result = await session.execute(_VACANT_PARCEL_NUMBERS_SQL, {"market": market})
        parcel_numbers = [row[0] for row in result]

    logger = get_logger("assemblage.jobs")
    total = 0
    for chunk in _chunks(parcel_numbers, batch_size):
        async with session_factory() as session:
            total += await recompute_assemblage(session, chunk)
            await session.commit()
        logger.info("assemblage_progress", plays=total, of=len(parcel_numbers), market=market)
    return total


async def _run(*, market: str | None) -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        count = await recompute_all_assemblage(session_factory, market=market)
        get_logger("assemblage.jobs").info("recomputed_assemblage", plays=count, market=market)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run(market=None))


if __name__ == "__main__":
    main()
