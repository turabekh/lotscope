import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.buybox.schemas import BuyBoxWrite
from lotscope.buybox.service import write_buy_box
from lotscope.deal.service import _assumptions, analyze_parcel_deal, assumptions_source
from lotscope.deal.underwriting import build_underwriting

pytestmark = pytest.mark.integration

BUY_BOX_COST_PER_SQFT = 145.0
PLATFORM_COST_PER_SQFT = 175.0
PLATFORM_SOFT_COST_PCT = 0.15
PLATFORM_TARGET_MARGIN = 0.20


async def _user(session: AsyncSession, email: str) -> int:
    await session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES (:email, 'x', 'user', 'pro', true)"
        ),
        {"email": email},
    )
    await session.flush()
    return int(await session.scalar(text("SELECT id FROM app_user WHERE email=:e"), {"e": email}))


async def _buy_box(session: AsyncSession, user_id: int, **assumptions: float) -> None:
    await write_buy_box(session, user_id, BuyBoxWrite(assumptions=assumptions))
    await session.flush()


async def _standard(session: AsyncSession, market_code: str) -> None:
    await session.execute(
        text(
            "INSERT INTO zoning_standard (code, code_version, market_code, min_lot_area_sqft, "
            "min_lot_width_ft, max_height_ft, max_occupancy_pct, permitted_uses, max_units) "
            "VALUES ('RSA-5', 'test-1', :market, 640, 16, 38, 75, "
            "'[\"single_family\"]'::jsonb, 3)"
        ),
        {"market": market_code},
    )
    await session.flush()


async def _parcel_with_comps(session: AsyncSession, market_code: str, parcel: str) -> None:
    await _standard(session, market_code)
    await session.execute(
        text(
            "INSERT INTO parcel (parcel_number, market_code, base_zoning_code, market_value, "
            "lot_area_sqft, frontage_ft, is_vacant, geom_local) VALUES (:parcel, :market, "
            "'RSA-5', 90000, 4000, 40, true, "
            "ST_SetSRID(ST_MakePoint(2690000, 240000), 2272))"
        ),
        {"parcel": parcel, "market": market_code},
    )
    for index in range(6):
        await session.execute(
            text(
                "INSERT INTO parcel (parcel_number, market_code, base_zoning_code, market_value, "
                "lot_area_sqft, is_vacant, geom_local) VALUES (:parcel, :market, 'RSA-5', 900000, "
                "2000, false, ST_SetSRID(ST_MakePoint(2690000, 240000), 2272))"
            ),
            {"parcel": f"{market_code}:comp{index}", "market": market_code},
        )
        await session.execute(
            text(
                "INSERT INTO sale (parcel_number, sale_date, sale_price, document_type) "
                "VALUES (:parcel, current_date - interval '200 days', 900000, 'DEED')"
            ),
            {"parcel": f"{market_code}:comp{index}"},
        )
    await session.flush()


async def test_a_buy_box_construction_cost_reaches_the_computed_offer(
    db_session: AsyncSession,
) -> None:
    await _parcel_with_comps(db_session, "phl", "phl:bb1")
    user_id = await _user(db_session, "bb1@example.com")
    await _buy_box(db_session, user_id, construction_cost_per_sqft=BUY_BOX_COST_PER_SQFT)

    with_box = await analyze_parcel_deal(db_session, "phl:bb1", user_id=user_id)
    at_platform = await analyze_parcel_deal(db_session, "phl:bb1")
    forced = await analyze_parcel_deal(
        db_session, "phl:bb1", construction_cost_per_sqft=BUY_BOX_COST_PER_SQFT
    )

    assert with_box is not None
    assert at_platform is not None
    assert forced is not None
    assert at_platform.max_allowable_offer != forced.max_allowable_offer
    assert with_box.max_allowable_offer == forced.max_allowable_offer
    assert with_box.assumptions_source == "buy_box"
    assert at_platform.assumptions_source == "platform_default"


async def test_one_buyers_box_does_not_move_another_buyers_offer(
    db_session: AsyncSession,
) -> None:
    await _parcel_with_comps(db_session, "phl", "phl:bb2")
    mine = await _user(db_session, "bb2-mine@example.com")
    theirs = await _user(db_session, "bb2-theirs@example.com")
    await _buy_box(db_session, mine, construction_cost_per_sqft=BUY_BOX_COST_PER_SQFT)

    ours = await analyze_parcel_deal(db_session, "phl:bb2", user_id=mine)
    hers = await analyze_parcel_deal(db_session, "phl:bb2", user_id=theirs)
    anonymous = await analyze_parcel_deal(db_session, "phl:bb2")

    assert ours is not None
    assert hers is not None
    assert anonymous is not None
    assert hers.max_allowable_offer == anonymous.max_allowable_offer
    assert ours.max_allowable_offer != hers.max_allowable_offer


async def test_an_explicit_request_value_still_beats_the_buy_box(
    db_session: AsyncSession,
) -> None:
    await _parcel_with_comps(db_session, "phl", "phl:bb3")
    user_id = await _user(db_session, "bb3@example.com")
    await _buy_box(db_session, user_id, construction_cost_per_sqft=BUY_BOX_COST_PER_SQFT)

    requested = await analyze_parcel_deal(
        db_session, "phl:bb3", user_id=user_id, construction_cost_per_sqft=PLATFORM_COST_PER_SQFT
    )
    from_box = await analyze_parcel_deal(db_session, "phl:bb3", user_id=user_id)

    assert requested is not None
    assert from_box is not None
    assert requested.max_allowable_offer != from_box.max_allowable_offer


async def test_a_higher_target_margin_lowers_the_offer(db_session: AsyncSession) -> None:
    await _parcel_with_comps(db_session, "phl", "phl:bb4")
    patient = await _user(db_session, "bb4-patient@example.com")
    greedy = await _user(db_session, "bb4-greedy@example.com")
    await _buy_box(db_session, patient, target_margin=0.10)
    await _buy_box(db_session, greedy, target_margin=0.35)

    at_ten = await analyze_parcel_deal(db_session, "phl:bb4", user_id=patient)
    at_thirty_five = await analyze_parcel_deal(db_session, "phl:bb4", user_id=greedy)

    assert at_ten is not None
    assert at_thirty_five is not None
    assert at_ten.max_allowable_offer is not None
    assert at_thirty_five.max_allowable_offer is not None
    assert at_thirty_five.max_allowable_offer < at_ten.max_allowable_offer


async def test_underwriting_computes_from_the_buy_box_not_only_displays_it(
    db_session: AsyncSession,
) -> None:
    await _parcel_with_comps(db_session, "phl", "phl:bb5")
    user_id = await _user(db_session, "bb5@example.com")
    await _buy_box(db_session, user_id, construction_cost_per_sqft=BUY_BOX_COST_PER_SQFT)

    analysis = await build_underwriting(
        db_session,
        "phl:bb5",
        owner_id=user_id,
        market_code="phl",
        base_zoning_code="RSA-5",
        market_value=90000.0,
        buildability=None,
        land_value=None,
    )

    origins = {item["name"]: item["origin"] for item in analysis.assumptions}
    values = {item["name"]: item["value"] for item in analysis.assumptions}
    assert origins["construction_cost_per_sqft"] == "user_override"
    assert values["construction_cost_per_sqft"] == BUY_BOX_COST_PER_SQFT


def test_precedence_is_request_then_buy_box_then_platform() -> None:
    box = {"construction_cost_per_sqft": BUY_BOX_COST_PER_SQFT, "soft_cost_pct": 0.11}

    from_box = _assumptions(buy_box=box)
    from_request = _assumptions(construction_cost_per_sqft=200.0, buy_box=box)
    from_platform = _assumptions(buy_box={})

    assert from_box.construction_cost_per_sqft == BUY_BOX_COST_PER_SQFT
    assert from_box.soft_cost_pct == 0.11
    assert from_request.construction_cost_per_sqft == 200.0
    assert from_request.soft_cost_pct == 0.11
    assert from_platform.construction_cost_per_sqft == PLATFORM_COST_PER_SQFT
    assert from_platform.soft_cost_pct == PLATFORM_SOFT_COST_PCT
    assert from_platform.target_margin == PLATFORM_TARGET_MARGIN


def test_an_empty_buy_box_is_identical_to_no_buy_box() -> None:
    assert _assumptions(buy_box={}) == _assumptions()
    assert _assumptions(buy_box=None) == _assumptions()


def test_the_assumptions_source_names_where_the_numbers_came_from() -> None:
    assert assumptions_source(None) == "platform_default"
    assert assumptions_source({}) == "platform_default"
    assert assumptions_source({"construction_cost_per_sqft": BUY_BOX_COST_PER_SQFT}) == "buy_box"
