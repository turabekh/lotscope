from dataclasses import dataclass
from datetime import datetime

from lotscope.deal.analysis import DealAssumptions, DealInputs, analyze_deal
from lotscope.deal.cases import CASE_VERSION, CaseDeltas, ScenarioCase, all_cases


@dataclass(frozen=True)
class CaseResult:
    case: ScenarioCase
    label: str
    rationale: str
    arv: float | None
    total_cost: float | None
    profit: float | None
    margin: float | None
    max_allowable_offer: float | None
    infeasible: bool


@dataclass(frozen=True)
class CaseAnalysis:
    results: tuple[CaseResult, ...]
    case_version: str
    profile_version: int | None
    computed_at: datetime


def _apply(inputs: DealInputs, assumptions: DealAssumptions, deltas: CaseDeltas) -> CaseResult:
    adjusted_prices = [
        price * deltas.exit_value_multiplier for price in inputs.finished_comp_prices
    ]
    adjusted_inputs = DealInputs(
        units=inputs.units,
        buildable_area_sqft=inputs.buildable_area_sqft,
        estimated_floors=inputs.estimated_floors,
        finished_comp_prices=adjusted_prices,
        land_value=inputs.land_value,
        acquisition_price=inputs.acquisition_price,
    )
    adjusted_assumptions = DealAssumptions(
        construction_cost_per_sqft=assumptions.construction_cost_per_sqft
        * deltas.construction_cost_multiplier,
        soft_cost_pct=assumptions.soft_cost_pct,
        selling_cost_pct=assumptions.selling_cost_pct,
        target_margin=assumptions.target_margin,
        default_unit_sqft=assumptions.default_unit_sqft,
        max_unit_sqft=assumptions.max_unit_sqft,
    )
    result = analyze_deal(adjusted_inputs, adjusted_assumptions)
    return CaseResult(
        case=deltas.case,
        label=deltas.label,
        rationale=deltas.rationale,
        arv=result.arv,
        total_cost=result.total_cost,
        profit=result.profit,
        margin=result.margin,
        max_allowable_offer=result.max_allowable_offer,
        infeasible=result.infeasible,
    )


def analyze_cases(
    inputs: DealInputs,
    assumptions: DealAssumptions,
    *,
    computed_at: datetime,
    profile_version: int | None = None,
) -> CaseAnalysis:
    return CaseAnalysis(
        results=tuple(_apply(inputs, assumptions, deltas) for deltas in all_cases()),
        case_version=CASE_VERSION,
        profile_version=profile_version,
        computed_at=computed_at,
    )
