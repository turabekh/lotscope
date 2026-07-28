from lotscope.deal.analysis import DealAssumptions
from lotscope.deal.scenarios import ScenarioInputs, build_scenarios

_ASSUMPTIONS = DealAssumptions(
    construction_cost_per_sqft=200.0,
    soft_cost_pct=0.15,
    selling_cost_pct=0.06,
    target_margin=0.20,
    default_unit_sqft=1200.0,
    max_unit_sqft=2000.0,
)


def _inputs(**overrides: object) -> ScenarioInputs:
    base: dict[str, object] = {
        "by_right_units": 3,
        "buildable_area_sqft": 1500.0,
        "estimated_floors": 3,
        "finished_comp_prices": [400000.0, 420000.0, 410000.0, 405000.0, 415000.0],
        "land_value": 150000.0,
        "acquisition_price": 150000.0,
    }
    base.update(overrides)
    return ScenarioInputs(**base)  # type: ignore[arg-type]


def test_models_by_right_and_variance_scenarios() -> None:
    result = build_scenarios(_inputs(), _ASSUMPTIONS, max_variance_units=2)
    units = [s.units for s in result.scenarios]
    assert units == [1, 2, 3, 4, 5]
    assert [s.by_right for s in result.scenarios] == [True, True, True, False, False]
    assert result.by_right_units == 3


def test_recommends_a_by_right_scenario_by_profit() -> None:
    result = build_scenarios(_inputs(), _ASSUMPTIONS)
    assert result.recommended_units is not None
    chosen = next(s for s in result.scenarios if s.units == result.recommended_units)
    assert chosen.by_right is True
    profits = [s.profit for s in result.scenarios if s.by_right and s.profit is not None]
    assert chosen.profit == max(profits)


def test_arv_scales_with_units() -> None:
    result = build_scenarios(_inputs(), _ASSUMPTIONS)
    arvs = [s.arv for s in result.scenarios]
    assert arvs[0] is not None
    assert arvs[2] is not None
    assert arvs[2] > arvs[0]


def test_no_by_right_units_yields_no_scenarios() -> None:
    result = build_scenarios(_inputs(by_right_units=None), _ASSUMPTIONS)
    assert result.scenarios == []
    assert result.recommended_units is None


def test_without_acquisition_recommends_by_mao() -> None:
    result = build_scenarios(_inputs(acquisition_price=None, land_value=None), _ASSUMPTIONS)
    assert all(s.profit is None for s in result.scenarios)
    assert result.recommended_units is not None


def test_unknown_by_right_units_is_reported_as_undetermined() -> None:
    result = build_scenarios(_inputs(by_right_units=None), _ASSUMPTIONS)
    assert result.scenarios == []
    assert result.by_right_units is None
    assert result.reasons == [
        "No by-right unit count could be determined; cannot model build scenarios."
    ]


def test_zero_by_right_units_is_not_reported_as_undetermined() -> None:
    result = build_scenarios(_inputs(by_right_units=0), _ASSUMPTIONS)
    assert result.scenarios == []
    assert result.by_right_units == 0
    assert result.reasons == [
        "Zoning permits no units by right on this parcel; cannot model build scenarios."
    ]
