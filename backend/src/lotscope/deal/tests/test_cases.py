from datetime import UTC, datetime

from lotscope.deal.analysis import DealAssumptions, DealInputs
from lotscope.deal.case_analysis import analyze_cases
from lotscope.deal.cases import CASE_VERSION, CASES, all_cases, deltas_for

_NOW = datetime(2026, 7, 28, tzinfo=UTC)


def _assumptions() -> DealAssumptions:
    return DealAssumptions(
        construction_cost_per_sqft=175.0,
        soft_cost_pct=0.15,
        selling_cost_pct=0.07,
        target_margin=0.20,
        default_unit_sqft=1200.0,
        max_unit_sqft=3000.0,
    )


def _inputs(**kw: object) -> DealInputs:
    return DealInputs(
        units=kw.get("units", 2),  # type: ignore[arg-type]
        buildable_area_sqft=kw.get("buildable_area_sqft", 2400.0),  # type: ignore[arg-type]
        estimated_floors=kw.get("estimated_floors", 3),  # type: ignore[arg-type]
        finished_comp_prices=kw.get("finished_comp_prices", [1_150_000.0, 1_180_000.0]),  # type: ignore[arg-type]
        land_value=kw.get("land_value", 120000.0),  # type: ignore[arg-type]
        acquisition_price=kw.get("acquisition_price", 130000.0),  # type: ignore[arg-type]
    )


def test_all_three_cases_are_produced_in_a_stable_order() -> None:
    analysis = analyze_cases(_inputs(), _assumptions(), computed_at=_NOW)
    assert [r.case for r in analysis.results] == list(CASES)
    assert [r.case for r in analysis.results] == ["downside", "base", "upside"]


def test_the_base_case_matches_the_unadjusted_analysis() -> None:
    base = next(
        r
        for r in analyze_cases(_inputs(), _assumptions(), computed_at=_NOW).results
        if r.case == "base"
    )
    assert deltas_for("base").exit_value_multiplier == 1.0
    assert deltas_for("base").construction_cost_multiplier == 1.0
    assert base.arv is not None


def test_downside_is_never_better_than_base_and_upside_never_worse() -> None:
    results = {
        r.case: r for r in analyze_cases(_inputs(), _assumptions(), computed_at=_NOW).results
    }
    assert results["downside"].profit is not None
    assert results["base"].profit is not None
    assert results["upside"].profit is not None
    assert results["downside"].profit < results["base"].profit < results["upside"].profit


def test_downside_offers_less_than_base_so_a_user_cannot_overbid_on_optimism() -> None:
    results = {
        r.case: r for r in analyze_cases(_inputs(), _assumptions(), computed_at=_NOW).results
    }
    assert results["downside"].max_allowable_offer is not None
    assert results["base"].max_allowable_offer is not None
    assert results["downside"].max_allowable_offer < results["base"].max_allowable_offer


def test_the_same_inputs_reproduce_the_same_results() -> None:
    first = analyze_cases(_inputs(), _assumptions(), computed_at=_NOW)
    second = analyze_cases(_inputs(), _assumptions(), computed_at=_NOW)
    assert first.results == second.results


def test_the_analysis_records_what_produced_it() -> None:
    analysis = analyze_cases(_inputs(), _assumptions(), computed_at=_NOW, profile_version=3)
    assert analysis.case_version == CASE_VERSION
    assert analysis.profile_version == 3
    assert analysis.computed_at == _NOW


def test_an_analysis_without_a_profile_records_no_profile_version() -> None:
    assert analyze_cases(_inputs(), _assumptions(), computed_at=_NOW).profile_version is None


def test_missing_comps_do_not_manufacture_a_case_result() -> None:
    analysis = analyze_cases(_inputs(finished_comp_prices=[]), _assumptions(), computed_at=_NOW)
    for result in analysis.results:
        assert result.arv is None
        assert result.profit is None
        assert result.max_allowable_offer is None


def test_every_case_states_its_rationale() -> None:
    for deltas in all_cases():
        assert deltas.rationale.strip()
        assert deltas.label.strip()


def test_the_case_axis_is_independent_of_the_unit_axis() -> None:
    one_unit = analyze_cases(_inputs(units=1), _assumptions(), computed_at=_NOW)
    three_units = analyze_cases(_inputs(units=3), _assumptions(), computed_at=_NOW)
    assert [r.case for r in one_unit.results] == [r.case for r in three_units.results]
    assert one_unit.results != three_units.results
