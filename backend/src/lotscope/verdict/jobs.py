"""The nightly rebuild of the screening index.

Every row is recomputed from the same composition the Lot page reads, so the index and
the answer can only differ by a night. It covers vacant land, which is the universe the
product screens; anything else is answered by computing it on read.
"""

import asyncio
from collections.abc import Iterator, Sequence

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.core.config import get_settings
from lotscope.core.db import create_engine, create_session_factory
from lotscope.core.logging import configure_logging, get_logger
from lotscope.verdict.service import compute_verdict

_DEFAULT_BATCH_SIZE = 500

_NUMBERS_SQL = text(
    "SELECT parcel_number FROM parcel "
    "WHERE is_vacant IS TRUE AND geom_local IS NOT NULL "
    "AND (CAST(:market AS text) IS NULL OR market_code = CAST(:market AS text)) "
    "ORDER BY parcel_number"
)

_UPSERT_SQL = text(
    "INSERT INTO parcel_screen (parcel_number, opportunity_score, deal_score, "
    "max_allowable_offer, est_margin, risk_score, by_right_units, can_build_by_right, "
    "is_underpriced, sources, computed_at) VALUES (:parcel_number, :opportunity_score, "
    ":deal_score, :max_allowable_offer, :est_margin, :risk_score, :by_right_units, "
    ":can_build_by_right, :is_underpriced, '[]'::jsonb, :computed_at) "
    "ON CONFLICT (parcel_number) DO UPDATE SET "
    "opportunity_score = excluded.opportunity_score, deal_score = excluded.deal_score, "
    "max_allowable_offer = excluded.max_allowable_offer, est_margin = excluded.est_margin, "
    "risk_score = excluded.risk_score, by_right_units = excluded.by_right_units, "
    "can_build_by_right = excluded.can_build_by_right, "
    "is_underpriced = excluded.is_underpriced, computed_at = excluded.computed_at, "
    "updated_at = now()"
)

_logger = get_logger("verdict.jobs")


def _chunks(items: Sequence[str], size: int) -> Iterator[list[str]]:
    for start in range(0, len(items), size):
        yield list(items[start : start + size])


async def rebuild_screen(session: AsyncSession, parcel_numbers: Sequence[str]) -> int:
    written = 0
    for parcel_number in parcel_numbers:
        try:
            async with session.begin_nested():
                verdict = await compute_verdict(session, parcel_number)
                if verdict is None:
                    continue
                await session.execute(
                    _UPSERT_SQL,
                    {
                        "parcel_number": parcel_number,
                        "opportunity_score": verdict.opportunity_score,
                        "deal_score": verdict.deal_score,
                        "max_allowable_offer": verdict.max_allowable_offer,
                        "est_margin": verdict.est_margin,
                        "risk_score": verdict.risk_score,
                        "by_right_units": verdict.by_right_units,
                        "can_build_by_right": verdict.can_build_by_right,
                        "is_underpriced": verdict.is_underpriced,
                        "computed_at": verdict.computed_at,
                    },
                )
                written += 1
        except Exception as error:
            _logger.warning("screen_row_skipped", parcel_number=parcel_number, error=str(error))
    return written


async def rebuild_all_screens(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    batch_size: int = _DEFAULT_BATCH_SIZE,
    market: str | None = None,
) -> int:
    async with session_factory() as session:
        parcel_numbers = [row[0] for row in await session.execute(_NUMBERS_SQL, {"market": market})]

    total = 0
    for chunk in _chunks(parcel_numbers, batch_size):
        async with session_factory() as session:
            total += await rebuild_screen(session, chunk)
            await session.commit()
        _logger.info("screen_progress", done=total, of=len(parcel_numbers))
    return total


async def _run(*, market: str | None) -> None:
    settings = get_settings()
    configure_logging(settings)
    engine = create_engine(settings)
    session_factory = create_session_factory(engine)
    try:
        count = await rebuild_all_screens(session_factory, market=market)
        _logger.info("rebuilt_screen_index", count=count, market=market)
    finally:
        await engine.dispose()


def main() -> None:
    asyncio.run(_run(market=None))


if __name__ == "__main__":
    main()
