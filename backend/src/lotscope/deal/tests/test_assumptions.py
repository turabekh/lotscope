from datetime import UTC, datetime
from decimal import Decimal

import pytest

from lotscope.core.config import Settings
from lotscope.deal.assumptions import (
    Assumption,
    AssumptionSet,
    UnavailableInputError,
    fraction,
    money,
)
from lotscope.deal.inventory import (
    MAO_EXCLUSIONS,
    build_assumption_set,
    guard_required,
    mao_disclosure,
    missing_required,
)

_NOW = datetime(2026, 7, 28, tzinfo=UTC)


def _settings() -> Settings:
    return Settings(_env_file=None)


def test_money_is_exact_to_the_cent_not_a_float_approximation() -> None:
    assert money(0.1) + money(0.2) == Decimal("0.30")
    assert money(175.005) == Decimal("175.01")


def test_a_percentage_outside_zero_to_one_is_rejected() -> None:
    assert fraction(0.15) == 0.15
    for bad in (-0.01, 1.5, 15.0):
        with pytest.raises(ValueError, match="fraction in"):
            fraction(bad)


def test_user_override_beats_market_default_beats_platform_default() -> None:
    settings = _settings()
    platform = build_assumption_set(settings=settings)
    assert platform.get("construction_cost_per_sqft").origin == "platform_default"

    market = build_assumption_set(
        settings=settings, market_overrides={"construction_cost_per_sqft": 210.0}
    )
    assert market.get("construction_cost_per_sqft").origin == "market_default"
    assert market.get("construction_cost_per_sqft").value == Decimal("210.00")

    user = build_assumption_set(
        settings=settings,
        market_overrides={"construction_cost_per_sqft": 210.0},
        user_overrides={"construction_cost_per_sqft": 260.0},
    )
    assert user.get("construction_cost_per_sqft").origin == "user_override"
    assert user.get("construction_cost_per_sqft").value == Decimal("260.00")


def test_financing_and_time_are_unavailable_rather_than_zero() -> None:
    assumptions = build_assumption_set(settings=_settings())
    for name in ("interest_rate", "loan_points", "construction_months", "entitlement_months"):
        item = assumptions.get(name)
        assert item.value is None, f"{name} must not carry an invented default"
        assert item.value != 0
        assert item.limitations, f"{name} must say why it is unavailable"


def test_an_unavailable_input_refuses_rather_than_returning_zero() -> None:
    assumptions = build_assumption_set(settings=_settings())
    with pytest.raises(UnavailableInputError, match="interest_rate"):
        assumptions.get("interest_rate").require()


def test_guard_names_every_missing_required_input() -> None:
    assumptions = build_assumption_set(settings=_settings())
    required = ("construction_cost_per_sqft", "interest_rate", "construction_months")
    assert missing_required(assumptions, required) == ("interest_rate", "construction_months")
    with pytest.raises(UnavailableInputError, match="interest_rate, construction_months"):
        guard_required(assumptions, required)


def test_a_group_total_declines_when_any_line_item_is_unavailable() -> None:
    partial = AssumptionSet(
        items={
            "a": Assumption(
                name="a",
                group="construction",
                value=Decimal("10.00"),
                origin="platform_default",
                unit="money",
            ),
            "b": Assumption(
                name="b", group="construction", value=None, origin="platform_default", unit="money"
            ),
        }
    )
    assert partial.group_total("construction") is None


def test_a_complete_group_totals_to_the_cent() -> None:
    complete = AssumptionSet(
        items={
            "a": Assumption(
                name="a",
                group="construction",
                value=Decimal("10.10"),
                origin="platform_default",
                unit="money",
            ),
            "b": Assumption(
                name="b",
                group="construction",
                value=Decimal("20.25"),
                origin="user_override",
                unit="money",
            ),
        }
    )
    assert complete.group_total("construction") == Decimal("30.35")


def test_the_mao_disclosure_names_its_formula_and_what_it_excludes() -> None:
    disclosure = mao_disclosure(build_assumption_set(settings=_settings()), _NOW)
    assert "max_allowable_offer" in disclosure.formula
    assert disclosure.target_margin == 0.20
    assert "financing interest" in " ".join(disclosure.exclusions)
    assert len(disclosure.exclusions) == len(MAO_EXCLUSIONS)
    assert disclosure.computed_at == _NOW


def test_the_mao_disclosure_names_the_inputs_it_could_not_obtain() -> None:
    disclosure = mao_disclosure(build_assumption_set(settings=_settings()), _NOW)
    assert "interest_rate" in disclosure.unavailable_inputs
    assert "construction_cost_per_sqft" not in disclosure.unavailable_inputs


def test_every_input_reports_its_origin_in_the_disclosure() -> None:
    disclosure = mao_disclosure(
        build_assumption_set(settings=_settings(), user_overrides={"target_margin": 0.25}), _NOW
    )
    assert "user_override" in disclosure.inputs["target_margin"]


def test_overridden_assumptions_are_listed_for_the_user() -> None:
    assumptions = build_assumption_set(
        settings=_settings(), user_overrides={"target_margin": 0.25, "soft_cost_pct": 0.18}
    )
    assert assumptions.overridden() == ["soft_cost_pct", "target_margin"]
