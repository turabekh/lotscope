from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.assessment.analysis import PHILADELPHIA_REALTY_TAX_RATE
from lotscope.assessment.service import analyze_parcel_assessment

pytestmark = pytest.mark.integration

_SINCE = date(2000, 1, 1)


async def _add_subject(session: AsyncSession, parcel_number: str, *, market_value: float) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, market_value, geom_2272) VALUES "
            "(:pn, 2000, :mv, ST_GeomFromText('POLYGON((0 0,0 5,5 5,5 0,0 0))', 2272))"
        ),
        {"pn": parcel_number, "mv": market_value},
    )


async def _add_comp(session: AsyncSession, parcel_number: str, *, offset_ft: float) -> None:
    geom = (
        f"POLYGON(({offset_ft} 0,{offset_ft} 5,{offset_ft + 5} 5,{offset_ft + 5} 0,{offset_ft} 0))"
    )
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, is_vacant, geom_2272) "
            "VALUES (:pn, 1000, true, ST_GeomFromText(:geom, 2272))"
        ),
        {"pn": parcel_number, "geom": geom},
    )
    await session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, sale_price, sale_date) "
            "VALUES (:pn, :doc, 100000, '2025-01-01')"
        ),
        {"pn": parcel_number, "doc": f"DOC-{parcel_number}"},
    )


async def _seed_with_comps(
    session: AsyncSession, parcel_number: str, *, market_value: float
) -> None:
    await _add_subject(session, parcel_number, market_value=market_value)
    for index in range(5):
        await _add_comp(session, f"0000001{index}", offset_ft=50 * (index + 1))
    await session.flush()


async def test_over_assessed_parcel_reports_savings(db_session: AsyncSession) -> None:
    await _seed_with_comps(db_session, "000000001", market_value=400000)

    result = await analyze_parcel_assessment(db_session, "000000001", since=_SINCE)
    assert result is not None
    assert result.status == "over_assessed"
    assert result.market_estimate == 200000.0
    assert result.over_assessed_amount == 200000.0
    assert result.estimated_annual_tax_savings == round(200000.0 * PHILADELPHIA_REALTY_TAX_RATE, 0)
    assert result.disclaimer


async def test_fairly_assessed_parcel_has_no_savings(db_session: AsyncSession) -> None:
    await _seed_with_comps(db_session, "000000002", market_value=200000)

    result = await analyze_parcel_assessment(db_session, "000000002", since=_SINCE)
    assert result is not None
    assert result.status == "fairly_assessed"
    assert result.estimated_annual_tax_savings is None


async def test_unknown_parcel_returns_none(db_session: AsyncSession) -> None:
    assert await analyze_parcel_assessment(db_session, "999999999") is None
