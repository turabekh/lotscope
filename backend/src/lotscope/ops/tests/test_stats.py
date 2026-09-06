from typing import cast

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.ops.models import MarketStats
from lotscope.ops.stats import snapshot_market_stats

pytestmark = pytest.mark.integration


async def test_snapshot_computes_coverage_stats(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, is_vacant, geom_local) VALUES "
            "('phl:s-1', 'phl', true, ST_SetSRID(ST_GeomFromText('POINT(0 0)'), 2272)), "
            "('phl:s-2', 'phl', true, NULL), "
            "('phl:s-3', 'phl', false, ST_SetSRID(ST_GeomFromText('POINT(1 1)'), 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel_screen "
            "(parcel_number, est_margin) VALUES "
            "('phl:s-1', 0.22), "
            "('phl:s-2', NULL)"
        ),
    )
    await db_session.flush()

    class _Ctx:
        def __init__(self, s: AsyncSession) -> None:
            self._s = s

        async def __aenter__(self) -> AsyncSession:
            return self._s

        async def __aexit__(self, *exc: object) -> bool:
            return False

    class _SF:
        def __call__(self) -> "_Ctx":
            return _Ctx(db_session)

    count = await snapshot_market_stats(cast("async_sessionmaker[AsyncSession]", _SF()))
    assert count >= 1

    row = await db_session.get(MarketStats, "phl")
    assert row is not None
    assert row.parcel_count == 3
    assert row.vacant_count == 2
    assert row.geometry_pct is not None
    assert row.screened_pct is not None
    assert row.vacant_priced_pct is not None
    assert float(row.geometry_pct) == pytest.approx(66.67, abs=0.1)
    # Both vacant lots are in the index; one of them carries a priced margin.
    assert float(row.screened_pct) == pytest.approx(100.0, abs=0.1)
    assert float(row.vacant_priced_pct) == pytest.approx(50.0, abs=0.1)
