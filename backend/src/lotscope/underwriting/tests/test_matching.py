from datetime import UTC, datetime

from lotscope.buybox.schemas import BuyBoxRead, BuyBoxWrite
from lotscope.underwriting.matching import (
    MatchCandidate,
    evaluate_buy_box,
    match_conditions,
    required_margin,
)

PLATFORM_TARGET_MARGIN = 0.20


def _buy_box(**overrides: object) -> BuyBoxRead:
    written = BuyBoxWrite(**overrides)
    now = datetime.now(UTC)
    return BuyBoxRead.model_validate(
        {**written.model_dump(), "user_id": 1, "created_at": now, "updated_at": now}
    )


def _candidate(**overrides: object) -> MatchCandidate:
    base: dict[str, object] = {
        "parcel_number": "phl:1",
        "max_allowable_offer": 120_000.0,
        "est_margin": 0.25,
        "lot_area_sqft": 1_200.0,
        "base_zoning_code": "RSA-5",
    }
    base.update(overrides)
    return MatchCandidate(**base)  # type: ignore[arg-type]


def test_a_default_buy_box_still_screens_on_the_platform_target_margin() -> None:
    result = evaluate_buy_box(_candidate(), _buy_box())

    assert result.matched is True
    assert [outcome.name for outcome in result.criteria] == ["target_margin", "min_lot_sqft"]


def test_the_margin_target_comes_from_the_buy_box_when_it_sets_one() -> None:
    assert required_margin(_buy_box()) == PLATFORM_TARGET_MARGIN
    assert required_margin(_buy_box(assumptions={"target_margin": 0.35})) == 0.35


def test_every_criterion_met() -> None:
    buy_box = _buy_box(
        max_bid=150_000.0,
        min_lot_sqft=640,
        zoning_codes=["rsa-5", "cmx-2"],
        assumptions={"target_margin": 0.20},
    )

    result = evaluate_buy_box(_candidate(), buy_box)

    assert result.matched is True
    assert all(outcome.status == "met" for outcome in result.criteria)


def test_an_offer_above_the_ceiling_does_not_match() -> None:
    result = evaluate_buy_box(_candidate(max_allowable_offer=200_000.0), _buy_box(max_bid=150_000))

    assert result.matched is False
    price = next(o for o in result.criteria if o.name == "max_bid")
    assert price.status == "not_met"
    assert "$150,000" in price.detail


def test_a_margin_below_the_target_does_not_match() -> None:
    result = evaluate_buy_box(
        _candidate(est_margin=0.05), _buy_box(assumptions={"target_margin": 0.25})
    )

    assert result.matched is False
    assert next(o for o in result.criteria if o.name == "target_margin").status == "not_met"


def test_a_lot_below_the_floor_does_not_match() -> None:
    result = evaluate_buy_box(_candidate(lot_area_sqft=400.0), _buy_box(min_lot_sqft=640))

    assert result.matched is False
    assert next(o for o in result.criteria if o.name == "min_lot_sqft").status == "not_met"


def test_a_district_outside_the_list_does_not_match() -> None:
    result = evaluate_buy_box(_candidate(base_zoning_code="I-2"), _buy_box(zoning_codes=["RSA-5"]))

    assert result.matched is False
    assert next(o for o in result.criteria if o.name == "zoning_codes").status == "not_met"


def test_a_missing_input_is_not_evaluated_rather_than_silently_passed() -> None:
    result = evaluate_buy_box(
        _candidate(max_allowable_offer=None, est_margin=None, lot_area_sqft=None),
        _buy_box(max_bid=150_000, min_lot_sqft=640),
    )

    assert result.matched is False
    assert {o.status for o in result.criteria} == {"not_evaluated"}


def test_the_sql_conditions_mirror_the_criteria() -> None:
    conditions, params = match_conditions(
        _buy_box(max_bid=150_000, min_lot_sqft=640, zoning_codes=["rsa-5"])
    )

    assert "v.max_allowable_offer <= :max_bid" in conditions
    assert "v.est_margin >= :target_margin" in conditions
    assert "p.lot_area_sqft >= :min_lot_sqft" in conditions
    assert "upper(p.base_zoning_code) = ANY(:zoning_codes)" in conditions
    assert params["zoning_codes"] == ["RSA-5"]
    assert params["target_margin"] == PLATFORM_TARGET_MARGIN


def test_the_exclusions_become_sql_only_when_switched_on() -> None:
    on, _ = match_conditions(_buy_box(exclude_historic=True, exclude_flood=True))
    off, _ = match_conditions(_buy_box(exclude_historic=False, exclude_flood=False))

    assert any("historic_district" in condition for condition in on)
    assert any("flood_zone" in condition for condition in on)
    assert not any("historic_district" in condition for condition in off)
    assert not any("flood_zone" in condition for condition in off)
