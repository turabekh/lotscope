from lotscope.underwriting.matching import (
    MatchCandidate,
    evaluate_buy_box,
)
from lotscope.underwriting.schemas import BuyBox


def _candidate(**overrides: object) -> MatchCandidate:
    base: dict[str, object] = {
        "parcel_number": "phl:1",
        "max_allowable_offer": 120_000.0,
        "est_margin": 0.25,
        "by_right_units": 3,
        "risk_score": 20.0,
    }
    base.update(overrides)
    return MatchCandidate(**base)  # type: ignore[arg-type]


def test_empty_buy_box_matches_with_no_criteria() -> None:
    result = evaluate_buy_box(_candidate(), BuyBox())
    assert result.matched is True
    assert result.criteria == []


def test_all_criteria_met() -> None:
    buy_box = BuyBox(
        max_acquisition_price=150_000.0,
        min_margin=0.20,
        min_units=2,
        max_units=4,
        risk_tolerance="low",
    )
    result = evaluate_buy_box(_candidate(), buy_box)
    assert result.matched is True
    assert {c.status for c in result.criteria} == {"met"}


def test_price_above_ceiling_does_not_match() -> None:
    result = evaluate_buy_box(
        _candidate(max_allowable_offer=200_000.0), BuyBox(max_acquisition_price=150_000.0)
    )
    assert result.matched is False
    assert result.criteria[0].status == "not_met"


def test_unknown_offer_is_not_evaluated_never_a_match() -> None:
    result = evaluate_buy_box(
        _candidate(max_allowable_offer=None), BuyBox(max_acquisition_price=150_000.0)
    )
    assert result.matched is False
    assert result.criteria[0].status == "not_evaluated"
    assert "unconfirmed" in result.criteria[0].detail.lower()


def test_unknown_margin_is_not_evaluated_never_a_match() -> None:
    result = evaluate_buy_box(_candidate(est_margin=None), BuyBox(min_margin=0.20))
    assert result.matched is False
    assert result.criteria[0].status == "not_evaluated"


def test_unknown_units_is_not_evaluated_never_a_match() -> None:
    result = evaluate_buy_box(_candidate(by_right_units=None), BuyBox(min_units=2))
    assert result.matched is False
    assert result.criteria[0].status == "not_evaluated"


def test_unknown_risk_is_not_evaluated_never_a_match() -> None:
    result = evaluate_buy_box(_candidate(risk_score=None), BuyBox(risk_tolerance="low"))
    assert result.matched is False
    assert result.criteria[0].status == "not_evaluated"


def test_zero_margin_is_evaluated_not_treated_as_unknown() -> None:
    result = evaluate_buy_box(_candidate(est_margin=0.0), BuyBox(min_margin=0.20))
    assert result.matched is False
    assert result.criteria[0].status == "not_met"


def test_unit_range_is_inclusive_at_both_ends() -> None:
    buy_box = BuyBox(min_units=3, max_units=3)
    assert evaluate_buy_box(_candidate(by_right_units=3), buy_box).matched is True
    assert evaluate_buy_box(_candidate(by_right_units=2), buy_box).matched is False
    assert evaluate_buy_box(_candidate(by_right_units=4), buy_box).matched is False


def test_risk_tolerance_widens_the_ceiling() -> None:
    candidate = _candidate(risk_score=55.0)
    assert evaluate_buy_box(candidate, BuyBox(risk_tolerance="low")).matched is False
    assert evaluate_buy_box(candidate, BuyBox(risk_tolerance="medium")).matched is True
    assert evaluate_buy_box(candidate, BuyBox(risk_tolerance="high")).matched is True


def test_unrecognised_risk_tolerance_is_not_evaluated() -> None:
    result = evaluate_buy_box(_candidate(), BuyBox(risk_tolerance="aggressive"))
    assert result.matched is False
    assert result.criteria[0].status == "not_evaluated"


def test_every_specified_criterion_is_reported_even_when_one_fails() -> None:
    buy_box = BuyBox(max_acquisition_price=150_000.0, min_margin=0.90, min_units=2)
    result = evaluate_buy_box(_candidate(), buy_box)
    assert result.matched is False
    assert [c.name for c in result.criteria] == [
        "max_acquisition_price",
        "min_margin",
        "units",
    ]
    assert [c.status for c in result.criteria] == ["met", "not_met", "met"]
