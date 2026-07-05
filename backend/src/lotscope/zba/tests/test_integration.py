from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.zba.service import variance_outlook

pytestmark = pytest.mark.integration

_TODAY = date(2026, 1, 1)


async def _add_parcel(
    session: AsyncSession, parcel_number: str, *, zoning: str, zip_code: str
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, base_zoning_code, zip_code) "
            "VALUES (:pn, :zoning, :zip)"
        ),
        {"pn": parcel_number, "zoning": zoning, "zip": zip_code},
    )


async def _add_appeal(
    session: AsyncSession,
    appeal_number: str,
    *,
    parcel_number: str | None,
    decision: str,
    day: date,
) -> None:
    await session.execute(
        text(
            "INSERT INTO zba_appeal (appeal_number, parcel_number, decision, decision_date) "
            "VALUES (:an, :pn, :decision, :day)"
        ),
        {"an": appeal_number, "pn": parcel_number, "decision": decision, "day": day},
    )


async def test_variance_outlook_scopes_to_district_and_window(db_session: AsyncSession) -> None:
    await _add_parcel(db_session, "000000001", zoning="RSA5", zip_code="19123")
    for index in range(12):
        await _add_parcel(db_session, f"1000000{index:02d}", zoning="RSA5", zip_code="19123")
        decision = "GRANTED" if index < 9 else "DENIED"
        await _add_appeal(
            db_session,
            f"A{index}",
            parcel_number=f"1000000{index:02d}",
            decision=decision,
            day=date(2025, 1, 1),
        )
    await _add_parcel(db_session, "20000000", zoning="RSA5", zip_code="19123")
    await _add_appeal(
        db_session, "OLD", parcel_number="20000000", decision="GRANTED", day=date(2010, 1, 1)
    )
    await _add_parcel(db_session, "30000000", zoning="CMX3", zip_code="19123")
    await _add_appeal(
        db_session, "OTHER", parcel_number="30000000", decision="DENIED", day=date(2025, 1, 1)
    )
    await db_session.flush()

    result = await variance_outlook(db_session, "000000001", today=_TODAY)
    assert result is not None
    assert result.district == "RSA5"
    assert result.decided == 12
    assert result.granted == 9
    assert result.grant_rate == 0.75
    assert result.population_label == "all ZBA appeals for RSA5 parcels"


async def test_variance_outlook_reports_too_few_below_threshold(db_session: AsyncSession) -> None:
    await _add_parcel(db_session, "000000001", zoning="RSA5", zip_code="19123")
    await _add_parcel(db_session, "10000000", zoning="RSA5", zip_code="19123")
    await _add_appeal(
        db_session, "A0", parcel_number="10000000", decision="GRANTED", day=date(2025, 1, 1)
    )
    await db_session.flush()

    result = await variance_outlook(db_session, "000000001", today=_TODAY)
    assert result is not None
    assert result.grant_rate is None
    assert result.decided == 1
    assert result.reason is not None
    assert "too few" in result.reason


async def test_variance_outlook_none_for_missing_parcel(db_session: AsyncSession) -> None:
    assert await variance_outlook(db_session, "999999999", today=_TODAY) is None
