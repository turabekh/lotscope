import asyncio
from collections.abc import Iterator, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.distress.service import recompute_distress, tired_landlord_owner_keys

_PARCEL_NUMBERS_SQL = text(
    "SELECT parcel_number FROM parcel "
    "WHERE (CAST(:market AS text) IS NULL OR market_code = CAST(:market AS text)) "
    "ORDER BY parcel_number"
)
_DEFAULT_BATCH_SIZE = 1000


def _chunks(items: Sequence[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


async def recompute_all_distress(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    market: str | None = None,
) -> int:
    async with session_factory() as session:
        result = await session.execute(_PARCEL_NUMBERS_SQL, {"market": market})
        parcel_numbers = [row[0] for row in result]
        tired_owners = await tired_landlord_owner_keys(session)

    logger = get_logger("distress.jobs")
    total = 0
    for chunk in _chunks(parcel_numbers, batch_size):
        async with session_factory() as session:
            total += await recompute_distress(session, chunk, tired_owners)
            await session.commit()
        logger.info("distress_progress", done=total, of=len(parcel_numbers), market=market)
    return total


async def _run(*, market: str | None) -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        count = await recompute_all_distress(session_factory, market=market)
        get_logger("distress.jobs").info("recomputed_distress", count=count, market=market)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run(market=None))


if __name__ == "__main__":
    main()
