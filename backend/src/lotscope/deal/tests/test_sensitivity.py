from datetime import UTC, datetime

from lotscope.deal.analysis import DealAssumptions, DealInputs
from lotscope.deal.sensitivity import (
    COST_STEPS,
    EXIT_STEPS,
    SENSITIVITY_VERSION,
    build_grid,
)

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


def _inputs(*, comps: list[float] | None = None, buildable: float | None = 2400.0) -> DealInputs:
    return DealInputs(
        units=2,
        buildable_area_sqft=buildable,
        estimated_floors=3,
        finished_comp_prices=[1_150_000.0, 1_180_000.0] if comps is None else comps,
        land_value=120000.0,
        acquisition_price=130000.0,
    )


def test_the_grid_is_two_dimensional_and_complete() -> None:
    grid = build_grid(_inputs(), _assumptions(), computed_at=_NOW)
    assert grid.available
    assert len(grid.cells) == len(EXIT_STEPS) * len(COST_STEPS)
    assert grid.row_label == "Finished value"
    assert grid.column_label == "Construction cost"


def test_margin_improves_with_exit_value_and_worsens_with_cost() -> None:
    grid = build_grid(_inputs(), _assumptions(), computed_at=_NOW)
    by_key = {(c.exit_multiplier, c.cost_multiplier): c for c in grid.cells}

    low_exit = by_key[(min(EXIT_STEPS), 1.0)].margin
    high_exit = by_key[(max(EXIT_STEPS), 1.0)].margin
    assert low_exit is not None
    assert high_exit is not None
    assert low_exit < high_exit

    cheap_build = by_key[(1.0, min(COST_STEPS))].margin
    dear_build = by_key[(1.0, max(COST_STEPS))].margin
    assert cheap_build is not None
    assert dear_build is not None
    assert dear_build < cheap_build


def test_the_centre_cell_is_the_unadjusted_case() -> None:
    grid = build_grid(_inputs(), _assumptions(), computed_at=_NOW)
    centre = next(c for c in grid.cells if c.exit_multiplier == 1.0 and c.cost_multiplier == 1.0)
    assert centre.margin is not None


def test_no_comps_yields_no_grid_and_says_why() -> None:
    grid = build_grid(_inputs(comps=[]), _assumptions(), computed_at=_NOW)
    assert not grid.available
    assert grid.cells == ()
    assert grid.unavailable_reason is not None
    assert "comparable" in grid.unavailable_reason


def test_no_buildable_area_yields_no_grid_and_says_why() -> None:
    grid = build_grid(_inputs(buildable=None), _assumptions(), computed_at=_NOW)
    assert not grid.available
    assert grid.unavailable_reason is not None
    assert "buildable area" in grid.unavailable_reason


def test_an_unavailable_grid_never_reports_zero_margin_cells() -> None:
    grid = build_grid(_inputs(comps=[]), _assumptions(), computed_at=_NOW)
    assert all(cell.margin is None for cell in grid.cells)


def test_the_grid_is_reproducible_and_versioned() -> None:
    first = build_grid(_inputs(), _assumptions(), computed_at=_NOW)
    second = build_grid(_inputs(), _assumptions(), computed_at=_NOW)
    assert first.cells == second.cells
    assert first.sensitivity_version == SENSITIVITY_VERSION


def test_the_steps_bracket_the_unadjusted_case_symmetrically_enough_to_be_useful() -> None:
    assert min(EXIT_STEPS) < 1.0 < max(EXIT_STEPS)
    assert min(COST_STEPS) < 1.0 < max(COST_STEPS)
    assert 1.0 in EXIT_STEPS
    assert 1.0 in COST_STEPS
