import asyncio
import sys
from collections.abc import Iterator, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql.elements import TextClause

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.core.markets import market_argument
from lotscope.verdict.composition import VERDICT_VERSION
from lotscope.verdict.decision import DECISION_VERSION
from lotscope.verdict.service import recompute_verdicts

_STALE_ONLY_PREDICATE = (
    " AND NOT EXISTS (SELECT 1 FROM parcel_verdict v "
    "WHERE v.parcel_number = parcel.parcel_number "
    "AND v.verdict_version = CAST(:version AS text) "
    "AND v.decision_version = CAST(:decision_version AS text))"
)
_DEFAULT_BATCH_SIZE = 500


def _chunks(items: Sequence[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


def _numbers_statement(*, vacant_only: bool, only_stale: bool) -> TextClause:
    base = (
        "SELECT parcel_number FROM parcel WHERE "
        + ("is_vacant IS TRUE AND geom_local IS NOT NULL AND " if vacant_only else "")
        + "(CAST(:market AS text) IS NULL OR market_code = CAST(:market AS text))"
    )
    if only_stale:
        base += _STALE_ONLY_PREDICATE
    return text(base + " ORDER BY parcel_number")


async def _parcel_numbers(
    session: AsyncSession, *, vacant_only: bool, market: str | None, only_stale: bool = False
) -> list[str]:
    statement = _numbers_statement(vacant_only=vacant_only, only_stale=only_stale)
    params: dict[str, str | None] = {"market": market}
    if only_stale:
        params["version"] = VERDICT_VERSION
        params["decision_version"] = DECISION_VERSION
    result = await session.execute(statement, params)
    return [row[0] for row in result]


async def recompute_all_verdicts(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    vacant_only: bool = False,
    market: str | None = None,
    only_stale: bool = False,
) -> int:
    async with session_factory() as session:
        parcel_numbers = await _parcel_numbers(
            session, vacant_only=vacant_only, market=market, only_stale=only_stale
        )

    logger = get_logger("verdict.jobs")
    total = 0
    for chunk in _chunks(parcel_numbers, batch_size):
        async with session_factory() as session:
            total += await recompute_verdicts(session, chunk)
            await session.commit()
        logger.info("verdict_progress", done=total, of=len(parcel_numbers))
    return total


async def _run(*, vacant_only: bool, market: str | None, only_stale: bool) -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        count = await recompute_all_verdicts(
            session_factory, vacant_only=vacant_only, market=market, only_stale=only_stale
        )
        get_logger("verdict.jobs").info(
            "recomputed_verdicts",
            count=count,
            vacant_only=vacant_only,
            market=market,
            only_stale=only_stale,
        )
    finally:
        await engine.dispose()


def main() -> None:
    args = sys.argv[1:]
    asyncio.run(
        _run(
            vacant_only="vacant" in args,
            market=market_argument(args),
            only_stale="stale" in args,
        )
    )


if __name__ == "__main__":
    main()
