import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.distress.service import assess_parcel_distress, find_leads

pytestmark = pytest.mark.integration


async def _parcel(
    session: AsyncSession,
    parcel_number: str,
    *,
    address: str,
    mailing: str,
    is_vacant: bool = False,
    is_city_owned: bool = False,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, address, mailing_address, zip_code, "
            "is_vacant, is_city_owned) VALUES (:pn, 'OWNER', :addr, :mail, '19140', :vac, :city)"
        ),
        {
            "pn": parcel_number,
            "addr": address,
            "mail": mailing,
            "vac": is_vacant,
            "city": is_city_owned,
        },
    )


async def _tax(
    session: AsyncSession,
    parcel_number: str,
    *,
    delinquent: bool,
    due: float = 0,
    years: int = 0,
    sheriff: bool = False,
) -> None:
    await session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "in_sheriff_sale) VALUES (:pn, :d, :due, :yrs, :sh)"
        ),
        {"pn": parcel_number, "d": delinquent, "due": due, "yrs": years, "sh": sheriff},
    )


async def test_parcel_distress_scores_signals(db_session: AsyncSession) -> None:
    await _parcel(
        db_session, "000000001", address="1 A ST", mailing="99 ZZ AVE, NEW YORK NY", is_vacant=True
    )
    await _tax(db_session, "000000001", delinquent=True, due=25000, years=5, sheriff=True)
    await db_session.flush()

    result = await assess_parcel_distress(db_session, "000000001")
    assert result is not None
    assert result.score == 80  # sheriff 30 + delinquent 15 + severe 15 + vacant 10 + absentee 10
    assert result.tier == "high"


async def test_city_owned_parcel_scores_zero(db_session: AsyncSession) -> None:
    await _parcel(
        db_session, "000000004", address="4 D ST", mailing="CITY HALL", is_city_owned=True
    )
    await _tax(db_session, "000000004", delinquent=True, due=50000, years=9, sheriff=True)
    await db_session.flush()

    result = await assess_parcel_distress(db_session, "000000004")
    assert result is not None
    assert result.score == 0


async def test_leads_rank_and_exclude(db_session: AsyncSession) -> None:
    await _parcel(
        db_session, "000000001", address="1 A ST", mailing="99 ZZ AVE, NEW YORK NY", is_vacant=True
    )
    await _tax(db_session, "000000001", delinquent=True, due=25000, years=5, sheriff=True)

    await _parcel(db_session, "000000002", address="2 B ST", mailing="2 B ST, PHILADELPHIA PA")
    await _tax(db_session, "000000002", delinquent=True, due=500, years=1)

    await _parcel(db_session, "000000003", address="3 C ST", mailing="3 C ST, PHILADELPHIA PA")

    await _parcel(
        db_session, "000000004", address="4 D ST", mailing="CITY HALL", is_city_owned=True
    )
    await _tax(db_session, "000000004", delinquent=True, due=50000, years=9, sheriff=True)
    await db_session.flush()

    leads = await find_leads(db_session, limit=50, min_score=1)
    numbers = [lead.parcel_number for lead in leads]

    assert numbers[0] == "000000001"
    assert "000000003" not in numbers  # no distress signals
    assert "000000004" not in numbers  # city owned

    top = next(lead for lead in leads if lead.parcel_number == "000000001")
    parcel = await assess_parcel_distress(db_session, "000000001")
    assert parcel is not None
    assert top.score == parcel.score  # lead-list SQL and per-parcel scorer agree


async def test_leads_respect_min_score_and_vacant_filter(db_session: AsyncSession) -> None:
    await _parcel(db_session, "000000002", address="2 B ST", mailing="2 B ST, PHILADELPHIA PA")
    await _tax(db_session, "000000002", delinquent=True, due=500, years=1)
    await db_session.flush()

    assert await find_leads(db_session, limit=50, min_score=30) == []
    assert await find_leads(db_session, limit=50, min_score=1, vacant_only=True) == []
