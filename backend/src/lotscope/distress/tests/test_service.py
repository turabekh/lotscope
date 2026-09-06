from datetime import date

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.distress.service import (
    assess_parcel_distress,
    find_leads,
    recompute_distress,
    tired_landlord_owner_keys,
)

pytestmark = pytest.mark.integration


async def _parcel(
    session: AsyncSession,
    parcel_number: str,
    *,
    address: str,
    mailing: str,
    owner: str = "OWNER",
    is_vacant: bool = False,
    is_city_owned: bool = False,
) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, owner, address, mailing_address, zip_code, "
            "is_vacant, is_city_owned) VALUES (:pn, :owner, :addr, :mail, '19140', :vac, :city)"
        ),
        {
            "pn": parcel_number,
            "owner": owner,
            "addr": address,
            "mail": mailing,
            "vac": is_vacant,
            "city": is_city_owned,
        },
    )


async def _open_violation(session: AsyncSession, parcel_number: str, external_id: str) -> None:
    await session.execute(
        text(
            "INSERT INTO li_event (parcel_number, event_type, external_id, status) "
            "VALUES (:pn, 'violation', :xid, 'OPEN')"
        ),
        {"pn": parcel_number, "xid": external_id},
    )


async def _deed(
    session: AsyncSession,
    parcel_number: str,
    document_id: str,
    sale_date: str,
    *,
    sale_price: float | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO sale (parcel_number, document_id, document_type, sale_date, sale_price) "
            "VALUES (:pn, :doc, 'DEED', :d, :price)"
        ),
        {
            "pn": parcel_number,
            "doc": document_id,
            "d": date.fromisoformat(sale_date),
            "price": sale_price,
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
    delinquency_owner: str | None = None,
    snapshot_period: str | None = None,
) -> None:
    await session.execute(
        text(
            "INSERT INTO tax_status (parcel_number, is_delinquent, total_due, years_owed, "
            "in_sheriff_sale, delinquency_owner, snapshot_period) "
            "VALUES (:pn, :d, :due, :yrs, :sh, :downer, :period)"
        ),
        {
            "pn": parcel_number,
            "d": delinquent,
            "due": due,
            "yrs": years,
            "sh": sheriff,
            "downer": delinquency_owner,
            "period": snapshot_period,
        },
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

    await recompute_distress(db_session, ["000000001", "000000002", "000000003", "000000004"])
    leads = await find_leads(db_session, limit=50, min_score=1)
    numbers = [lead.parcel_number for lead in leads]

    assert numbers[0] == "000000001"
    assert "000000003" not in numbers  # no distress signals
    assert "000000004" not in numbers  # city owned

    top = next(lead for lead in leads if lead.parcel_number == "000000001")
    parcel = await assess_parcel_distress(db_session, "000000001")
    assert parcel is not None
    assert top.score == parcel.score  # precomputed lead score and live per-parcel scorer agree
    stored_score = await db_session.scalar(
        text("SELECT score FROM parcel_distress WHERE parcel_number = '000000001'")
    )
    assert stored_score == parcel.score  # the nightly index and the live scorer agree


async def test_long_tenure_absentee_from_old_deed(db_session: AsyncSession) -> None:
    await _parcel(db_session, "000000010", address="10 A ST", mailing="99 ZZ AVE, NEW YORK NY")
    await _deed(db_session, "000000010", "D-10", "2005-01-01")
    await db_session.flush()

    result = await assess_parcel_distress(db_session, "000000010")
    assert result is not None
    assert {f.code for f in result.factors} >= {"absentee", "long_tenure"}
    assert result.score == 15  # absentee 10 + long_tenure 5


async def test_recent_deed_does_not_add_long_tenure(db_session: AsyncSession) -> None:
    await _parcel(db_session, "000000011", address="11 A ST", mailing="99 ZZ AVE, NEW YORK NY")
    await _deed(db_session, "000000011", "D-11", "2023-01-01")
    await db_session.flush()

    result = await assess_parcel_distress(db_session, "000000011")
    assert result is not None
    assert "long_tenure" not in {f.code for f in result.factors}


async def test_nominal_transfer_does_not_reset_long_tenure(db_session: AsyncSession) -> None:
    await _parcel(db_session, "000000012", address="12 A ST", mailing="99 ZZ AVE, NEW YORK NY")
    await _deed(db_session, "000000012", "REAL", "2003-01-01", sale_price=185000)
    await _deed(db_session, "000000012", "NOMINAL", "2025-01-01", sale_price=1)
    await db_session.flush()

    result = await assess_parcel_distress(db_session, "000000012")
    assert result is not None
    assert "long_tenure" in {f.code for f in result.factors}


async def test_leads_surface_long_held_absentee(db_session: AsyncSession) -> None:
    await _parcel(db_session, "000000030", address="30 A ST", mailing="99 ZZ AVE, NEW YORK NY")
    await _deed(db_session, "000000030", "REAL", "2003-01-01", sale_price=185000)
    await _deed(db_session, "000000030", "NOMINAL", "2025-01-01", sale_price=1)
    await db_session.flush()
    await recompute_distress(db_session, ["000000030"])

    leads = await find_leads(db_session, limit=50, min_score=1)
    lead = next(item for item in leads if item.parcel_number == "000000030")
    assert any(factor.startswith("Long-held") for factor in lead.top_factors)


async def test_tired_landlord_scores_across_the_owner_portfolio(db_session: AsyncSession) -> None:
    for index in range(3):
        await _parcel(
            db_session,
            f"00000002{index}",
            address=f"{index} T ST",
            mailing=f"{index} T ST, PHILADELPHIA PA",
            owner="TIRED LLC",
        )
    for parcel, external_id in [
        ("000000020", "V1"),
        ("000000020", "V2"),
        ("000000021", "V3"),
        ("000000021", "V4"),
        ("000000022", "V5"),
    ]:
        await _open_violation(db_session, parcel, external_id)
    await db_session.flush()

    tired = await tired_landlord_owner_keys(db_session)
    assert len(tired) == 1

    live = await assess_parcel_distress(db_session, "000000020")
    assert live is not None
    assert "portfolio_distress" in {f.code for f in live.factors}

    await recompute_distress(db_session, ["000000020"], tired)
    leads = await find_leads(db_session, limit=50, min_score=1)
    lead = next(item for item in leads if item.parcel_number == "000000020")
    assert lead.score == 15  # open violations 5 + portfolio_distress 10
    assert "Tired landlord" in lead.top_factors


async def test_recompute_distress_is_idempotent(db_session: AsyncSession) -> None:
    await _parcel(
        db_session, "000000001", address="1 A ST", mailing="99 ZZ AVE, NEW YORK NY", is_vacant=True
    )
    await _tax(db_session, "000000001", delinquent=True, due=25000, years=5, sheriff=True)
    await db_session.flush()

    first = await recompute_distress(db_session, ["000000001"])
    second = await recompute_distress(db_session, ["000000001"])
    assert first == 1
    assert second == 1

    leads = await find_leads(db_session, limit=50, min_score=1)
    assert len(leads) == 1
    assert leads[0].score == 80


async def test_leads_respect_min_score_and_vacant_filter(db_session: AsyncSession) -> None:
    await _parcel(db_session, "000000002", address="2 B ST", mailing="2 B ST, PHILADELPHIA PA")
    await _tax(db_session, "000000002", delinquent=True, due=500, years=1)
    await db_session.flush()
    await recompute_distress(db_session, ["000000002"])

    assert await find_leads(db_session, limit=50, min_score=30) == []
    assert await find_leads(db_session, limit=50, min_score=1, vacant_only=True) == []


async def test_leads_long_held_factor_is_profile_driven(db_session: AsyncSession) -> None:
    await _parcel(db_session, "000000020", address="20 A ST", mailing="99 ZZ AVE, NEW YORK NY")
    await _tax(db_session, "000000020", delinquent=True, due=25000, years=5)
    await _deed(db_session, "000000020", "D-20", "2005-01-01")
    await _parcel(db_session, "000000021", address="21 A ST", mailing="99 ZZ AVE, NEW YORK NY")
    await _tax(db_session, "000000021", delinquent=True, due=25000, years=5)
    await _deed(db_session, "000000021", "D-21", "2023-01-01")
    await db_session.flush()
    await recompute_distress(db_session, ["000000020", "000000021"])

    leads = {lead.parcel_number: lead for lead in await find_leads(db_session, limit=50)}
    old = next(f for f in leads["000000020"].top_factors if f.startswith("Long-held"))
    assert old
    assert all(not f.startswith("Long-held") for f in leads["000000021"].top_factors)


async def test_leads_never_show_or_rank_on_a_debt_the_owner_does_not_owe(
    db_session: AsyncSession,
) -> None:
    await _parcel(
        db_session,
        "000000901",
        address="1 OWED ST",
        mailing="99 ELSEWHERE AVE, NEW YORK NY",
        owner="KENNEDY PATRICIA",
    )
    await _tax(
        db_session,
        "000000901",
        delinquent=True,
        due=500,
        delinquency_owner="KENNEDY PATRICIA",
        snapshot_period="202206",
    )
    await _parcel(
        db_session,
        "000000902",
        address="2 STRANGER ST",
        mailing="99 ELSEWHERE AVE, NEW YORK NY",
        owner="SHLAYEN RACHEL",
        is_vacant=True,
    )
    await _tax(
        db_session,
        "000000902",
        delinquent=True,
        due=999999,
        delinquency_owner="MATUSOW JOSEPH",
        snapshot_period="202206",
    )
    await _open_violation(db_session, "000000902", "v-902")
    await db_session.flush()

    await recompute_distress(db_session, ["000000901", "000000902"])
    leads = {lead.parcel_number: lead for lead in await find_leads(db_session, limit=50)}

    assert leads["000000901"].total_due == 500
    assert leads["000000902"].total_due is None
    assert not any("owed" in factor for factor in leads["000000902"].top_factors)

    ordered = [lead.parcel_number for lead in await find_leads(db_session, limit=50)]
    assert leads["000000901"].score == leads["000000902"].score
    assert ordered.index("000000901") < ordered.index("000000902")
