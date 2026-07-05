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


async def _add_geo_parcel(
    session: AsyncSession, parcel_number: str, *, area: float, width: float, polygon: str
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, base_zoning_code, "
            "geom_local) VALUES (:pn, :area, :width, 'RSA-5', ST_GeomFromText(:poly, 2272))"
        ),
        {"pn": parcel_number, "area": area, "width": width, "poly": polygon},
    )


_SUBJECT_POLY = "POLYGON((0 0,0 80,20 80,20 0,0 0))"
_LEFT_SMALL = "POLYGON((-10 0,-10 80,0 80,0 0,-10 0))"
_RIGHT_SMALL = "POLYGON((20 0,20 80,30 80,30 0,20 0))"
_REAR_SMALL = "POLYGON((0 80,0 120,20 120,20 80,0 80))"
_FRONT_LARGE = "POLYGON((0 -60,0 0,20 0,20 -60,0 -60))"


async def test_small_lot_division_when_adjacent_lots_are_small(db_session: AsyncSession) -> None:
    await _add_standard(db_session, "RSA-5")
    await _add_geo_parcel(db_session, "000000001", area=1600, width=20, polygon=_SUBJECT_POLY)
    await _add_geo_parcel(db_session, "000000010", area=800, width=10, polygon=_LEFT_SMALL)
    await _add_geo_parcel(db_session, "000000011", area=800, width=10, polygon=_RIGHT_SMALL)
    await _add_geo_parcel(db_session, "000000012", area=800, width=20, polygon=_REAR_SMALL)
    await _add_geo_parcel(db_session, "000000013", area=1200, width=20, polygon=_FRONT_LARGE)
    await db_session.flush()

    result = await analyze_parcel_subdivision(db_session, "000000001")
    assert result is not None
    assert result.can_subdivide is True
    assert result.max_lots == 2
    assert result.min_lot_area_sqft == 800.0
    assert any("Small-lot provision applies" in reason for reason in result.reasons)


async def test_no_small_lot_division_when_neighbors_are_large(db_session: AsyncSession) -> None:
    await _add_standard(db_session, "RSA-5")
    await _add_geo_parcel(db_session, "000000001", area=1600, width=20, polygon=_SUBJECT_POLY)
    await _add_geo_parcel(db_session, "000000010", area=800, width=10, polygon=_LEFT_SMALL)
    await _add_geo_parcel(db_session, "000000011", area=1600, width=20, polygon=_RIGHT_SMALL)
    await _add_geo_parcel(db_session, "000000012", area=1600, width=20, polygon=_REAR_SMALL)
    await _add_geo_parcel(db_session, "000000013", area=1200, width=20, polygon=_FRONT_LARGE)
    await db_session.flush()

    result = await analyze_parcel_subdivision(db_session, "000000001")
    assert result is not None
    assert result.can_subdivide is False
    assert result.max_lots == 1
