import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.deal.underwriting import build_underwriting

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


async def test_a_users_profile_defaults_reach_their_own_analysis(
    db_session: AsyncSession,
) -> None:
    from lotscope.underwriting.schemas import ProfileWrite
    from lotscope.underwriting.service import create_profile

    owner = await _user(db_session)
    await _parcel(db_session)
    await create_profile(
        db_session,
        owner,
        ProfileWrite(name="Mine", is_default=True, assumptions={"target_margin": 0.35}),
    )

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
