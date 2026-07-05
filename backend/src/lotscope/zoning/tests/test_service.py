import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.service import assess_parcel

pytestmark = pytest.mark.integration


async def _add_standard(session: AsyncSession, code: str) -> None:
    await session.execute(
        text(
            "INSERT INTO zoning_standard (code, code_version, permitted_uses, "
            "min_lot_area_sqft, min_lot_width_ft, max_height_ft, max_units, "
            "front_setback_ft, rear_setback_ft, side_setback_ft) "
            "VALUES (:code, '2024-01', '[\"single_family\"]'::jsonb, "
            "1440, 16, 38, 1, 0, 9, 0)"
        ),
        {"code": code},
    )


async def test_assess_parcel_resolves_spatially(db_session: AsyncSession) -> None:
    await _add_standard(db_session, "RSA-5")
    await db_session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "base_zoning_code, geom_local) VALUES "
            "('000000001', 1600, 18, 90, 'CMX-2', "
            "ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await db_session.flush()

    result = await assess_parcel(db_session, "000000001")
    assert result is not None
    assert result.district_code == "RSA-5"
    assert result.district_method == "spatial"
    assert result.can_build_by_right is True
    assert result.by_right_units == 1
    assert any(source["source"] == "zoning_standard" for source in result.sources)


async def test_assess_parcel_falls_back_to_opa_attribute(db_session: AsyncSession) -> None:
    await _add_standard(db_session, "RSA-5")
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "base_zoning_code) VALUES ('000000002', 1600, 18, 90, 'RSA-5')"
        )
    )
    await db_session.flush()

    result = await assess_parcel(db_session, "000000002")
    assert result is not None
    assert result.district_method == "opa_attribute"
    assert result.district_code == "RSA-5"


async def test_assess_parcel_without_standard_is_low_confidence(db_session: AsyncSession) -> None:
    await db_session.execute(
        text("INSERT INTO parcel (parcel_number, base_zoning_code) VALUES ('000000003', 'CMX-2')")
    )
    await db_session.flush()

    result = await assess_parcel(db_session, "000000003")
    assert result is not None
    assert result.district_code == "CMX-2"
    assert result.can_build_by_right is False
    assert result.confidence == "low"
    assert "No Title 14 standards" in result.reasons[0]


async def test_assess_parcel_unknown_district(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000004')"))
    await db_session.flush()

    result = await assess_parcel(db_session, "000000004")
    assert result is not None
    assert result.district_code is None
    assert result.buildability_score == 0.0
    assert "could not be resolved" in result.reasons[0]


async def test_assess_parcel_returns_none_when_missing(db_session: AsyncSession) -> None:
    assert await assess_parcel(db_session, "999999999") is None
