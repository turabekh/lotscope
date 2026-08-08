import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.deal.service import (
    _assumptions,
    analyze_parcel_deal,
    assumptions_source,
    normalize_overrides,
)
from lotscope.deal.underwriting import build_underwriting

pytestmark = pytest.mark.integration

OVERRIDE_COST_PER_SQFT = 145.0
PLATFORM_COST_PER_SQFT = 175.0


async def _market_with_override(session: AsyncSession, code: str, overrides: str) -> None:
    await session.execute(
        text(
            "INSERT INTO market (code, name, url_slug, state, local_srid, map_center, "
            "default_zoom, timezone, deal_assumption_overrides, launch_status) VALUES "
            "(:code, :code, :code, 'PA', 2272, '{}'::jsonb, 12, 'America/New_York', "
            "(:overrides)::jsonb, 'live')"
        ),
        {"code": code, "overrides": overrides},
    )
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


async def test_a_market_construction_cost_override_reaches_the_computed_deal(
    db_session: AsyncSession,
) -> None:
    await _market_with_override(db_session, "ovr", '{"construction_cost_per_sqft": 145.0}')
    await _parcel_with_comps(db_session, "ovr", "ovr:subject")

    at_market = await analyze_parcel_deal(db_session, "ovr:subject")
    at_platform = await analyze_parcel_deal(
        db_session, "ovr:subject", construction_cost_per_sqft=PLATFORM_COST_PER_SQFT
    )
    at_override = await analyze_parcel_deal(
        db_session, "ovr:subject", construction_cost_per_sqft=OVERRIDE_COST_PER_SQFT
    )

    assert at_market is not None
    assert at_override is not None
    assert at_platform is not None
    assert at_platform.max_allowable_offer != at_override.max_allowable_offer
    assert at_market.max_allowable_offer == at_override.max_allowable_offer


async def test_an_explicit_request_value_still_beats_the_market_override(
    db_session: AsyncSession,
) -> None:
    await _market_with_override(db_session, "ovr2", '{"construction_cost_per_sqft": 145.0}')
    await _parcel_with_comps(db_session, "ovr2", "ovr2:subject")

    requested = await analyze_parcel_deal(
        db_session, "ovr2:subject", construction_cost_per_sqft=PLATFORM_COST_PER_SQFT
    )
    market = await analyze_parcel_deal(db_session, "ovr2:subject")

    assert requested is not None
    assert market is not None
    assert requested.max_allowable_offer != market.max_allowable_offer


async def test_underwriting_computes_from_the_market_override_not_only_displays_it(
    db_session: AsyncSession,
) -> None:
    await _market_with_override(db_session, "ovr3", '{"construction_cost_per_sqft": 145.0}')
    await _parcel_with_comps(db_session, "ovr3", "ovr3:subject")
    await db_session.execute(
        text(
            "INSERT INTO app_user (email, hashed_password, role, tier, is_active) "
            "VALUES ('ovr@example.com', 'x', 'user', 'pro', true)"
        )
    )
    await db_session.flush()
    owner = int(
        await db_session.scalar(text("SELECT id FROM app_user WHERE email='ovr@example.com'"))
    )

    analysis = await build_underwriting(
        db_session,
        "ovr3:subject",
        owner_id=owner,
        market_code="ovr3",
        base_zoning_code="RSA-5",
        market_value=90000.0,
        buildability=None,
        land_value=None,
    )

    origins = {item["name"]: item["origin"] for item in analysis.assumptions}
    values = {item["name"]: item["value"] for item in analysis.assumptions}
    assert origins["construction_cost_per_sqft"] == "market_default"
    assert values["construction_cost_per_sqft"] == OVERRIDE_COST_PER_SQFT


def test_only_canonical_keys_survive_normalisation() -> None:
    resolved = normalize_overrides(
        {
            "construction_cost_per_sqft": 145.0,
            "deal_construction_cost_per_sqft": 999.0,
            "soft_cost_pct": 0.12,
            "calibrated": True,
            "nonsense": 1.0,
            "target_margin": "not a number",
        }
    )

    assert resolved == {"construction_cost_per_sqft": 145.0, "soft_cost_pct": 0.12}


def test_a_non_dict_or_empty_override_normalises_to_nothing() -> None:
    assert normalize_overrides(None) == {}
    assert normalize_overrides({}) == {}
    assert normalize_overrides("nope") == {}


def test_the_calibrated_marker_is_orthogonal_to_values() -> None:
    assert assumptions_source({"calibrated": True, "construction_cost_per_sqft": 145.0}) == (
        "calibrated"
    )
    assert assumptions_source({"construction_cost_per_sqft": 145.0}) == "market_default"
    assert normalize_overrides({"calibrated": True}) == {}


def test_precedence_is_request_then_market_then_platform() -> None:
    market = {"construction_cost_per_sqft": 145.0, "soft_cost_pct": 0.11}

    from_market = _assumptions(market_overrides=market)
    from_request = _assumptions(construction_cost_per_sqft=200.0, market_overrides=market)
    from_platform = _assumptions(market_overrides={})

    assert from_market.construction_cost_per_sqft == 145.0
    assert from_market.soft_cost_pct == 0.11
    assert from_request.construction_cost_per_sqft == 200.0
    assert from_request.soft_cost_pct == 0.11
    assert from_platform.construction_cost_per_sqft == PLATFORM_COST_PER_SQFT


def test_an_empty_override_set_is_identical_to_no_override_set() -> None:
    assert _assumptions(market_overrides={}) == _assumptions()
    assert _assumptions(market_overrides=None) == _assumptions()
