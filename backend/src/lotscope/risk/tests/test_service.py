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
