import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.subdivision.service import analyze_parcel_subdivision

pytestmark = pytest.mark.integration


async def _add_standard(session: AsyncSession, code: str) -> None:
    await session.execute(
        text(
            "INSERT INTO zoning_standard (code, code_version, permitted_uses, "
            "min_lot_area_sqft, min_lot_width_ft, max_height_ft, max_units, "
            "front_setback_ft, rear_setback_ft, side_setback_ft) "
            "VALUES (:code, '2024-01', '[\"single_family\"]'::jsonb, 1440, 16, 38, 1, 0, 9, 0)"
        ),
        {"code": code},
    )


async def _add_parcel(
    session: AsyncSession, parcel_number: str, *, area: float, width: float
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, base_zoning_code) "
            "VALUES (:pn, :area, :width, 'RSA-5')"
        ),
        {"pn": parcel_number, "area": area, "width": width},
    )


async def test_wide_lot_reports_subdivision(db_session: AsyncSession) -> None:
    await _add_standard(db_session, "RSA-5")
    await _add_parcel(db_session, "000000001", area=3200, width=36)
    await db_session.flush()

    result = await analyze_parcel_subdivision(db_session, "000000001")
    assert result is not None
    assert result.district_code == "RSA-5"
    assert result.can_subdivide is True
    assert result.max_lots == 2
    assert any(source["source"] == "zoning_standard" for source in result.sources)


async def test_undersized_lot_needs_consolidation(db_session: AsyncSession) -> None:
    await _add_standard(db_session, "RSA-5")
    await _add_parcel(db_session, "000000002", area=960, width=14)
    await db_session.flush()

    result = await analyze_parcel_subdivision(db_session, "000000002")
    assert result is not None
    assert result.can_subdivide is False
    assert result.needs_consolidation is True


async def test_bogus_frontage_equal_to_area_is_ignored(db_session: AsyncSession) -> None:
    await _add_standard(db_session, "RSA-5")
    await _add_parcel(db_session, "000000003", area=8000, width=8000)
    await db_session.flush()

    result = await analyze_parcel_subdivision(db_session, "000000003")
    assert result is not None
    assert result.lot_width_ft is None
    assert result.max_lots == 5
    assert result.limiting_factor == "area"


async def test_unknown_parcel_returns_none(db_session: AsyncSession) -> None:
    assert await analyze_parcel_subdivision(db_session, "999999999") is None
