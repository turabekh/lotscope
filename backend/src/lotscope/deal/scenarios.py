from dataclasses import dataclass

from lotscope.deal.analysis import Confidence, DealAssumptions, DealInputs, analyze_deal

MAX_VARIANCE_UNITS = 2


@dataclass(frozen=True)
class ScenarioInputs:
    by_right_units: int | None
    buildable_area_sqft: float | None
    estimated_floors: int | None
    finished_comp_prices: list[float]
    land_value: float | None
    acquisition_price: float | None
    land_value_is_assessed: bool = False


@dataclass(frozen=True)
class Scenario:
    units: int
    by_right: bool
    arv: float | None
    total_cost: float | None
    profit: float | None
    margin: float | None
    roi: float | None
    max_allowable_offer: float | None
    deal_score: float | None
    infeasible: bool


@dataclass(frozen=True)
class ScenariosAnalysis:
    scenarios: list[Scenario]
    by_right_units: int | None
    recommended_units: int | None
    confidence: Confidence
    reasons: list[str]


def _recommend(scenarios: list[Scenario]) -> int | None:
    pool = [s for s in scenarios if s.by_right] or scenarios
    with_profit = [s for s in pool if s.profit is not None]
    if with_profit:
        return max(with_profit, key=lambda s: s.profit or 0.0).units
    with_mao = [s for s in pool if s.max_allowable_offer is not None]
    if with_mao:
        return max(with_mao, key=lambda s: s.max_allowable_offer or 0.0).units
    return pool[0].units if pool else None


def build_scenarios(
    inputs: ScenarioInputs,
    assumptions: DealAssumptions,
    *,
    max_variance_units: int = MAX_VARIANCE_UNITS,
) -> ScenariosAnalysis:
    by_right = inputs.by_right_units
    if by_right is None:
        return ScenariosAnalysis(
            scenarios=[],
            by_right_units=None,
            recommended_units=None,
            confidence="low",
            reasons=["No by-right unit count could be determined; cannot model build scenarios."],
        )
    if by_right <= 0:
        return ScenariosAnalysis(
            scenarios=[],
            by_right_units=by_right,
            recommended_units=None,
            confidence="low",
            reasons=[
                "Zoning permits no units by right on this parcel; cannot model build scenarios."
            ],
        )

    scenarios: list[Scenario] = []
    confidence: Confidence = "low"
    for units in range(1, by_right + max_variance_units + 1):
        analysis = analyze_deal(
            DealInputs(
                units=units,
                buildable_area_sqft=inputs.buildable_area_sqft,
                estimated_floors=inputs.estimated_floors,
                finished_comp_prices=inputs.finished_comp_prices,
                land_value=inputs.land_value,
                land_value_is_assessed=inputs.land_value_is_assessed,
                acquisition_price=inputs.acquisition_price,
            ),
            assumptions,
        )
        confidence = analysis.confidence
        scenarios.append(
            Scenario(
                units=units,
                by_right=units <= by_right,
                arv=analysis.arv,
                total_cost=analysis.total_cost,
                profit=analysis.profit,
                margin=analysis.margin,
                roi=analysis.roi,
                max_allowable_offer=analysis.max_allowable_offer,
                deal_score=analysis.deal_score,
                infeasible=analysis.infeasible,
            )
        )

    recommended = _recommend(scenarios)
    reasons = [
        f"By-right allows up to {by_right} unit(s); modeled 1-{by_right + max_variance_units} "
        "units (counts above by-right would need a variance or special exception).",
    ]
    if recommended is not None:
        chosen = next(s for s in scenarios if s.units == recommended)
        basis = "profit" if chosen.profit is not None else "max allowable offer"
        path = "by-right" if chosen.by_right else "with a variance"
        reasons.append(f"{recommended} unit(s) {path} maximizes {basis} among the scenarios.")
    return ScenariosAnalysis(
        scenarios=scenarios,
        by_right_units=by_right,
        recommended_units=recommended,
        confidence=confidence,
        reasons=reasons,
    )
