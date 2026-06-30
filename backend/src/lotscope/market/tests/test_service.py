from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.market.service import get_parcel_market

pytestmark = pytest.mark.integration

_SINCE = date(2000, 1, 1)


async def _add_parcel(
    session: AsyncSession,
    parcel_number: str,
    *,
    x: float,
    vacant: bool | None = None,
    market_value: float | None = None,
) -> None:
    geom = f"POLYGON(({x} 0,{x} 5,{x + 5} 5,{x + 5} 0,{x} 0))"
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, is_vacant, market_value, geom_2272) "
            "VALUES (:pn, :v, :mv, ST_GeomFromText(:geom, 2272))"
        ),
        {"pn": parcel_number, "v": vacant, "mv": market_value, "geom": geom},
    )


async def test_market_context_aggregates_nearby_activity(db_session: AsyncSession) -> None:
    await _add_parcel(db_session, "000000001", x=0)
    await _add_parcel(db_session, "000000002", x=20, vacant=True, market_value=100000)
    await _add_parcel(db_session, "000000003", x=40, vacant=False, market_value=200000)
    await _add_parcel(db_session, "000000004", x=9000)  # far away, excluded
    await db_session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, sale_price, sale_date) VALUES "
            "('000000002', 'D1', 150000, '2025-01-01'), "
            "('000000003', 'D2', 250000, '2025-02-01')"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO li_event (parcel_number, external_id, event_type, event_date) VALUES "
            "('000000002', 'P1', 'permit', '2025-03-01'), "
            "('000000003', 'P2', 'permit', '2025-04-01'), "
            "('000000003', 'X1', 'demolition', '2025-05-01')"
        )
    )
    await db_session.flush()

    result = await get_parcel_market(db_session, "000000001", radius_ft=200, years=3, since=_SINCE)
    assert result is not None
    assert result.parcels_nearby == 3
    assert result.vacant_nearby == 1
    assert result.recent_sales == 2
    assert result.median_sale_price == 200000.0
    assert result.permits == 2
    assert result.demolitions == 1
    assert result.median_assessed_value == 150000.0


async def test_market_context_without_geometry_is_empty(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000009')"))
    await db_session.flush()
    result = await get_parcel_market(db_session, "000000009")
    assert result is not None
    assert result.parcels_nearby == 0
    assert result.recent_sales == 0


async def test_market_context_unknown_parcel_returns_none(db_session: AsyncSession) -> None:
    assert await get_parcel_market(db_session, "999999999") is None
