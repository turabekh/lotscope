from dataclasses import dataclass
from datetime import datetime

from lotscope.deal.analysis import DealAssumptions, DealInputs, analyze_deal

SENSITIVITY_VERSION = "s1"

EXIT_STEPS: tuple[float, ...] = (0.85, 0.925, 1.0, 1.075, 1.15)
COST_STEPS: tuple[float, ...] = (0.90, 0.95, 1.0, 1.05, 1.10)


@dataclass(frozen=True)
class SensitivityCell:
    exit_multiplier: float
    cost_multiplier: float
    margin: float | None
    profit: float | None
    infeasible: bool


@dataclass(frozen=True)
class SensitivityGrid:
    row_label: str
    column_label: str
    exit_multipliers: tuple[float, ...]
    cost_multipliers: tuple[float, ...]
    cells: tuple[SensitivityCell, ...]
    sensitivity_version: str
    computed_at: datetime
    unavailable_reason: str | None = None

    @property
    def available(self) -> bool:
        return self.unavailable_reason is None


def _cell(
    inputs: DealInputs,
    assumptions: DealAssumptions,
    exit_multiplier: float,
    cost_multiplier: float,
) -> SensitivityCell:
    adjusted_inputs = DealInputs(
        units=inputs.units,
        buildable_area_sqft=inputs.buildable_area_sqft,
        estimated_floors=inputs.estimated_floors,
        finished_comp_prices=[price * exit_multiplier for price in inputs.finished_comp_prices],
        land_value=inputs.land_value,
        acquisition_price=inputs.acquisition_price,
    )
    adjusted_assumptions = DealAssumptions(
        construction_cost_per_sqft=assumptions.construction_cost_per_sqft * cost_multiplier,
        soft_cost_pct=assumptions.soft_cost_pct,
        selling_cost_pct=assumptions.selling_cost_pct,
        target_margin=assumptions.target_margin,
        default_unit_sqft=assumptions.default_unit_sqft,
        max_unit_sqft=assumptions.max_unit_sqft,
    )
    result = analyze_deal(adjusted_inputs, adjusted_assumptions)
    return SensitivityCell(
        exit_multiplier=exit_multiplier,
        cost_multiplier=cost_multiplier,
        margin=result.margin,
        profit=result.profit,
        infeasible=result.infeasible,
    )


def build_grid(
    inputs: DealInputs, assumptions: DealAssumptions, *, computed_at: datetime
) -> SensitivityGrid:
    empty = SensitivityGrid(
        row_label="Finished value",
        column_label="Construction cost",
        exit_multipliers=EXIT_STEPS,
        cost_multipliers=COST_STEPS,
        cells=(),
        sensitivity_version=SENSITIVITY_VERSION,
        computed_at=computed_at,
    )
    if not inputs.finished_comp_prices:
        return SensitivityGrid(
            **{
                **empty.__dict__,
                "unavailable_reason": "No comparable finished sales were available, so the "
                "sensitivity of this deal to exit value cannot be modelled.",
            }
        )
    if inputs.buildable_area_sqft is None:
        return SensitivityGrid(
            **{
                **empty.__dict__,
                "unavailable_reason": "No buildable area was derived for this parcel, so "
                "construction cost cannot be varied.",
            }
        )

    cells = tuple(
        _cell(inputs, assumptions, exit_multiplier, cost_multiplier)
        for exit_multiplier in EXIT_STEPS
        for cost_multiplier in COST_STEPS
    )
    return SensitivityGrid(**{**empty.__dict__, "cells": cells})
