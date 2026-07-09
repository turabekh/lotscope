import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zoning.service import assess_parcel, refresh_resolved_districts

pytestmark = pytest.mark.integration

_DISPLAY_ZONING_SQL = text(
    "SELECT coalesce(nullif(base_zoning_code, ''), resolved_zoning_code) AS display "
    "FROM parcel WHERE parcel_number = :parcel_number"
)


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


async def test_assess_parcel_resolves_overlap_by_majority_area(db_session: AsyncSession) -> None:
    await _add_standard(db_session, "RSA-5")
    await _add_standard(db_session, "RM-1")
    await db_session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RM-1', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RSA-5', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,5 100,5 -100,-100 -100))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, lot_area_sqft, frontage_ft, depth_ft, "
            "base_zoning_code, geom_local) VALUES "
            "('000000010', 1600, 18, 90, 'CMX-2', "
            "ST_GeomFromText('POLYGON((-90 0,-90 10,90 10,90 0,-90 0))', 2272))"
        )
    )
    await db_session.flush()

    first = await assess_parcel(db_session, "000000010")
    second = await assess_parcel(db_session, "000000010")
    assert first is not None
    assert second is not None
    assert first.district_code == "RM-1"
    assert first.district_code == second.district_code


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


async def test_refresh_resolved_districts_materializes_for_missing_attribute(
    db_session: AsyncSession,
) -> None:
    await db_session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RM', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code, geom_local) VALUES "
            "('000000021', NULL, ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code, geom_local) VALUES "
            "('000000022', 'CMX-2', ST_GeomFromText('POLYGON((1 1,1 9,9 9,9 1,1 1))', 2272))"
        )
    )
    await db_session.flush()

    changed = await refresh_resolved_districts(db_session, "phl")
    assert changed == 1

    missing = (
        await db_session.execute(
            text(
                "SELECT resolved_zoning_code, resolved_zoning_source FROM parcel "
                "WHERE parcel_number = '000000021'"
            )
        )
    ).one()
    assert missing.resolved_zoning_code == "RM"
    assert missing.resolved_zoning_source == "spatial"

    present = await db_session.scalar(
        text("SELECT resolved_zoning_code FROM parcel WHERE parcel_number = '000000022'")
    )
    assert present is None

    display_missing = await db_session.scalar(_DISPLAY_ZONING_SQL, {"parcel_number": "000000021"})
    display_present = await db_session.scalar(_DISPLAY_ZONING_SQL, {"parcel_number": "000000022"})
    assert display_missing == "RM"
    assert display_present == "CMX-2"


async def test_refresh_resolved_districts_is_idempotent(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO zoning_district (code, geom_local) VALUES ('RM', "
            "ST_GeomFromText('POLYGON((-100 -100,-100 100,100 100,100 -100,-100 -100))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code, geom_local) VALUES "
            "('000000023', '', ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await db_session.flush()

    assert await refresh_resolved_districts(db_session, "phl") == 1
    assert await refresh_resolved_districts(db_session, "phl") == 0
