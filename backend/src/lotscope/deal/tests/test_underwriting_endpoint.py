from typing import Any

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.schemas import BuyBoxWrite
from lotscope.buybox.service import write_buy_box
from lotscope.deal.underwriting import UnderwritingAnalysis, build_underwriting

pytestmark = pytest.mark.integration


async def _user(session: AsyncSession) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('uw@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email='uw@example.com'")))


async def _parcel(session: AsyncSession) -> None:
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, base_zoning_code, market_value) "
            "VALUES ('phl:uw1', 'phl', 'RSA-5', 150000)"
        )
    )
    await session.flush()


async def test_the_analysis_exposes_assumptions_with_their_origins(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session)
    await _parcel(db_session)

    analysis = await build_underwriting(
        db_session,
        "phl:uw1",
        owner_id=owner,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=150000.0,
        buildability=None,
        land_value=None,
    )
    origins = {item["name"]: item["origin"] for item in analysis.assumptions}
    assert origins["construction_cost_per_sqft"] == "platform_default"
    assert any(item["value"] is None for item in analysis.assumptions)


async def test_the_analysis_exposes_the_mao_formula_and_exclusions(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session)
    await _parcel(db_session)

    analysis = await build_underwriting(
        db_session,
        "phl:uw1",
        owner_id=owner,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=150000.0,
        buildability=None,
        land_value=None,
    )
    assert "max_allowable_offer" in str(analysis.mao["formula"])
    assert analysis.mao["exclusions"]
    unavailable = analysis.mao["unavailable_inputs"]
    assert isinstance(unavailable, list)
    assert "interest_rate" in unavailable


async def test_all_three_cases_and_a_sensitivity_verdict_are_present(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session)
    await _parcel(db_session)

    analysis = await build_underwriting(
        db_session,
        "phl:uw1",
        owner_id=owner,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=150000.0,
        buildability=None,
        land_value=None,
    )
    assert [r.case for r in analysis.cases.results] == ["downside", "base", "upside"]
    assert analysis.sensitivity.unavailable_reason is not None


async def test_a_users_buy_box_reaches_their_own_analysis(
    db_session: AsyncSession,
) -> None:
    owner = await _user(db_session)
    await _parcel(db_session)
    await write_buy_box(db_session, owner, BuyBoxWrite(assumptions={"target_margin": 0.35}))
    await db_session.flush()

    analysis = await build_underwriting(
        db_session,
        "phl:uw1",
        owner_id=owner,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=150000.0,
        buildability=None,
        land_value=None,
    )
    target = next(i for i in analysis.assumptions if i["name"] == "target_margin")
    assert target["value"] == 0.35
    assert target["origin"] == "user_override"


async def test_a_request_override_beats_the_users_buy_box(db_session: AsyncSession) -> None:
    owner = await _user(db_session)
    await _parcel(db_session)
    await write_buy_box(
        db_session, owner, BuyBoxWrite(assumptions={"construction_cost_per_sqft": 210.0})
    )
    await db_session.flush()

    from_buy_box = await build_underwriting(
        db_session,
        "phl:uw1",
        owner_id=owner,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=150000.0,
        buildability=None,
        land_value=None,
    )
    from_request = await build_underwriting(
        db_session,
        "phl:uw1",
        owner_id=owner,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=150000.0,
        buildability=None,
        land_value=None,
        construction_cost_per_sqft=190.0,
    )

    def item(analysis: UnderwritingAnalysis, name: str) -> dict[str, Any]:
        return next(entry for entry in analysis.assumptions if entry["name"] == name)

    assert item(from_buy_box, "construction_cost_per_sqft")["value"] == 210.0
    assert item(from_buy_box, "construction_cost_per_sqft")["origin"] == "user_override"
    assert item(from_request, "construction_cost_per_sqft")["value"] == 190.0
    assert item(from_request, "construction_cost_per_sqft")["origin"] == "scenario_override"


async def test_supplying_no_overrides_is_value_neutral(db_session: AsyncSession) -> None:
    owner = await _user(db_session)
    await _parcel(db_session)

    baseline = await build_underwriting(
        db_session,
        "phl:uw1",
        owner_id=owner,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=150000.0,
        buildability=None,
        land_value=None,
    )
    explicit_none = await build_underwriting(
        db_session,
        "phl:uw1",
        owner_id=owner,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=150000.0,
        buildability=None,
        land_value=None,
        construction_cost_per_sqft=None,
        soft_cost_pct=None,
        selling_cost_pct=None,
        target_margin=None,
    )

    assert baseline.mao == explicit_none.mao
    assert baseline.assumptions == explicit_none.assumptions
    assert [c.max_allowable_offer for c in baseline.cases.results] == [
        c.max_allowable_offer for c in explicit_none.cases.results
    ]
