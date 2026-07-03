import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.risk.service import assess_parcel_risk

pytestmark = pytest.mark.integration


def _codes(result: object) -> set[str]:
    return {flag.code for flag in result.flags}  # type: ignore[attr-defined]


async def test_delinquency_and_sheriff_sale_flagged(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000001')"))
    await db_session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "in_sheriff_sale) VALUES ('000000001', true, 25000, 4, true)"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000001")
    assert result is not None
    assert {"sheriff_sale", "tax_delinquency"} <= _codes(result)
    assert result.risk_score > 0
    assert result.confidence == "high"


async def test_unsafe_li_event_flagged(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000002')"))
    await db_session.execute(
        text(
            "INSERT INTO li_event (parcel_number, external_id, event_type, is_unsafe) "
            "VALUES ('000000002', 'V-1', 'violation', true)"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000002")
    assert result is not None
    assert "unsafe_structure" in _codes(result)
    assert "li_violations" in _codes(result)


async def test_li_violation_types_surface_in_detail(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000009')"))
    await db_session.execute(
        text(
            "INSERT INTO li_event "
            "(parcel_number, external_id, event_type, status, description) VALUES "
            "('000000009', 'V-1', 'violation', 'OPEN', 'DANGEROUS'), "
            "('000000009', 'V-2', 'violation', 'OPEN', 'DANGEROUS'), "
            "('000000009', 'V-3', 'violation', 'CLOSED', 'INTERIOR')"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000009")
    assert result is not None
    flag = next(f for f in result.flags if f.code == "li_violations")
    assert "Dangerous" in flag.detail
    assert "Interior" in flag.detail
    assert "2 still open" in flag.detail


async def test_flood_zone_intersection_flagged(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_2272) VALUES "
            "('000000003', ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO flood_zone (zone, geom_2272) VALUES "
            "('AE', ST_GeomFromText('POLYGON((5 5,5 20,20 20,20 5,5 5))', 2272))"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000003")
    assert result is not None
    flood = next(flag for flag in result.flags if flag.code == "flood_zone")
    assert flood.severity == "high"
    assert "AE" in flood.detail


async def test_estate_owner_flag_from_owner_record(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner) "
            "VALUES ('000000010', 'AGHOIAN GREGORY K ESTATE OF')"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000010")
    assert result is not None
    flag = next(f for f in result.flags if f.code == "estate_owner")
    assert flag.severity == "medium"
    assert flag.source == "parcel"


async def test_landlocked_parcel_flagged(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_2272) VALUES "
            "('000000020', ST_GeomFromText('POLYGON((0 0,0 20,20 20,20 0,0 0))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO street_centerline (external_id, geom_2272) VALUES "
            "('S-FAR', ST_GeomFromText('LINESTRING(0 200, 20 200)', 2272))"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000020")
    assert result is not None
    flag = next(f for f in result.flags if f.code == "no_street_access")
    assert flag.severity == "low"


async def test_parcel_with_frontage_not_flagged(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_2272) VALUES "
            "('000000021', ST_GeomFromText('POLYGON((0 0,0 20,20 20,20 0,0 0))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO street_centerline (external_id, geom_2272) VALUES "
            "('S-NEAR', ST_GeomFromText('LINESTRING(0 40, 20 40)', 2272))"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000021")
    assert result is not None
    assert "no_street_access" not in _codes(result)


async def test_historic_district_intersection_flagged(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_2272) VALUES "
            "('000000030', ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO historic_district (name, geom_2272) VALUES "
            "('Society Hill', ST_GeomFromText('POLYGON((5 5,5 20,20 20,20 5,5 5))', 2272))"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000030")
    assert result is not None
    flag = next(f for f in result.flags if f.code == "historic_district")
    assert flag.severity == "low"
    assert "Society Hill" in flag.detail
    assert flag.source == "historicdistricts_local"


async def test_parcel_outside_historic_district_not_flagged(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_2272) VALUES "
            "('000000031', ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO historic_district (name, geom_2272) VALUES "
            "('Far Away', ST_GeomFromText('POLYGON((100 100,100 120,120 120,120 100,100 100))', "
            "2272))"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000031")
    assert result is not None
    assert "historic_district" not in _codes(result)


async def test_clean_parcel_has_no_flags(db_session: AsyncSession) -> None:
    await db_session.execute(text("INSERT INTO parcel (parcel_number) VALUES ('000000004')"))
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000004")
    assert result is not None
    assert result.flags == []
    assert result.risk_score == 0.0
    assert result.confidence == "medium"


async def test_missing_parcel_returns_none(db_session: AsyncSession) -> None:
    assert await assess_parcel_risk(db_session, "999999999") is None


@pytest.mark.integration
async def test_overlay_and_rco_intersection_flagged(db_session: AsyncSession) -> None:
    await db_session.execute(
        text(
            "INSERT INTO parcel (parcel_number, geom_2272) VALUES "
            "('000000030', ST_GeomFromText('POLYGON((0 0,0 10,10 10,10 0,0 0))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO zoning_overlay (external_id, name, geom_2272) VALUES "
            "('O-1', '/NCA Overlay', ST_GeomFromText('POLYGON((5 5,5 20,20 20,20 5,5 5))', 2272))"
        )
    )
    await db_session.execute(
        text(
            "INSERT INTO rco (external_id, name, geom_2272) VALUES "
            "('R-1', 'Test RCO', ST_GeomFromText('POLYGON((1 1,1 30,30 30,30 1,1 1))', 2272))"
        )
    )
    await db_session.flush()

    result = await assess_parcel_risk(db_session, "000000030")
    assert result is not None
    flags = {flag.code: flag for flag in result.flags}
    assert "overlay_district" in flags
    assert "/NCA Overlay" in flags["overlay_district"].detail
    assert "rco" in flags
    assert "Test RCO" in flags["rco"].detail
