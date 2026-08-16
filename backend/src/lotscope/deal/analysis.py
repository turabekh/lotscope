from dataclasses import dataclass
from statistics import mean, median, pstdev
from typing import Literal

Confidence = Literal["high", "medium", "low"]

_HIGH_MIN_COMPS = 5
_HIGH_MAX_CV = 0.25
_MEDIUM_MIN_COMPS = 3
_MEDIUM_MAX_CV = 0.5


@dataclass(frozen=True)
class DealAssumptions:
    construction_cost_per_sqft: float
    soft_cost_pct: float
    selling_cost_pct: float
    target_margin: float
    default_unit_sqft: float
    max_unit_sqft: float


@dataclass(frozen=True)
class DealInputs:
    units: int | None
    buildable_area_sqft: float | None
    estimated_floors: int | None
    finished_comp_prices: list[float]
    land_value: float | None
    acquisition_price: float | None
    land_value_is_assessed: bool = False


@dataclass(frozen=True)
class DealAnalysis:
    arv: float | None
    per_unit_value: float | None
    gross_floor_area_sqft: float | None
    acquisition_cost: float | None
    construction_cost: float | None
    soft_cost: float | None
    selling_cost: float | None
    total_cost: float | None
    profit: float | None
    margin: float | None
    roi: float | None
    max_allowable_offer: float | None
    is_underpriced: bool | None
    deal_score: float | None
    infeasible: bool
    comp_count: int
    confidence: Confidence
    reasons: list[str]


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _finished_value_confidence(prices: list[float]) -> tuple[float | None, Confidence]:
    usable = [price for price in prices if price > 0]
    if not usable:
        return None, "low"
    per_unit = median(usable)
    average = mean(usable)
    cv = pstdev(usable) / average if len(usable) > 1 and average else 0.0
    if len(usable) >= _HIGH_MIN_COMPS and cv < _HIGH_MAX_CV:
        confidence: Confidence = "high"
    elif len(usable) >= _MEDIUM_MIN_COMPS and cv < _MEDIUM_MAX_CV:
        confidence = "medium"
    else:
        confidence = "low"
    return per_unit, confidence


def _unknown(comp_count: int, reason: str) -> DealAnalysis:
    return DealAnalysis(
        arv=None,
        per_unit_value=None,
        gross_floor_area_sqft=None,
        acquisition_cost=None,
        construction_cost=None,
        soft_cost=None,
        selling_cost=None,
        total_cost=None,
        profit=None,
        margin=None,
        roi=None,
        max_allowable_offer=None,
        is_underpriced=None,
        deal_score=None,
        infeasible=False,
        comp_count=comp_count,
        confidence="low",
        reasons=[reason],
    )


def analyze_deal(inputs: DealInputs, assumptions: DealAssumptions) -> DealAnalysis:
    comp_count = len(inputs.finished_comp_prices)
    if not inputs.units or inputs.units <= 0:
        return _unknown(
            comp_count, "No by-right units could be determined; cannot model a build scenario."
        )
    per_unit_value, finished_confidence = _finished_value_confidence(inputs.finished_comp_prices)
    if per_unit_value is None:
        return _unknown(
            comp_count, "No comparable improved sales were found to estimate a finished value."
        )

    units = inputs.units
    arv = round(per_unit_value * units)

    footprint = inputs.buildable_area_sqft
    floors = inputs.estimated_floors
    unit_cap = units * assumptions.max_unit_sqft
    if footprint and footprint > 0 and floors:
        envelope_gfa = footprint * floors
        gross_floor_area = min(envelope_gfa, unit_cap)
        if gross_floor_area < envelope_gfa:
            gfa_reason = (
                f"Gross floor area ~{gross_floor_area:,.0f} sqft "
                f"(capped at {units} unit(s) x {assumptions.max_unit_sqft:,.0f} sqft; "
                f"envelope allows ~{envelope_gfa:,.0f} sqft)."
            )
        else:
            gfa_reason = (
                f"Gross floor area ~{gross_floor_area:,.0f} sqft "
                f"({footprint:,.0f} sqft footprint x {floors} floor(s))."
            )
    else:
        gross_floor_area = units * assumptions.default_unit_sqft
        gfa_reason = (
            f"Gross floor area ~{gross_floor_area:,.0f} sqft "
            f"({units} unit(s) x {assumptions.default_unit_sqft:,.0f} sqft default)."
        )

    construction_cost = round(assumptions.construction_cost_per_sqft * gross_floor_area)
    soft_cost = round(assumptions.soft_cost_pct * construction_cost)
    selling_cost = round(assumptions.selling_cost_pct * arv)

    acquisition_cost = inputs.acquisition_price
    acquisition_reason: str
    if acquisition_cost is None:
        if inputs.land_value is not None:
            acquisition_cost = inputs.land_value
            if inputs.land_value_is_assessed:
                acquisition_reason = (
                    f"Acquisition assumed at the assessed value ${acquisition_cost:,.0f}; "
                    "no comparable land sales were available to estimate a market price."
                )
            else:
                acquisition_reason = (
                    f"Acquisition assumed at the modelled land value ${acquisition_cost:,.0f}."
                )
        else:
            acquisition_reason = "No acquisition price or land value available."
    else:
        acquisition_reason = f"Acquisition price ${acquisition_cost:,.0f} (as supplied)."

    max_allowable_offer = round(
        arv * (1.0 - assumptions.target_margin) - construction_cost - soft_cost - selling_cost
    )
    infeasible = max_allowable_offer < 0
    if infeasible:
        max_allowable_offer = 0

    reasons = [
        f"ARV ${arv:,.0f} from {comp_count} improved comp(s); "
        f"${per_unit_value:,.0f}/unit x {units} unit(s).",
        gfa_reason,
        (
            f"Construction ${construction_cost:,.0f}; soft ${soft_cost:,.0f}; "
            f"selling ${selling_cost:,.0f}."
        ),
        acquisition_reason,
    ]
    if infeasible:
        reasons.append(
            f"Build cost does not leave a {assumptions.target_margin:.0%} margin even at a "
            "land price of $0, so there is no acquisition price that reaches the target "
            "(max allowable offer floored to $0)."
        )
    else:
        reasons.append(
            f"Max allowable offer ${max_allowable_offer:,.0f} "
            f"at a {assumptions.target_margin:.0%} target margin."
        )

    if acquisition_cost is None:
        return DealAnalysis(
            arv=float(arv),
            per_unit_value=round(per_unit_value, 2),
            gross_floor_area_sqft=round(gross_floor_area, 1),
            acquisition_cost=None,
            construction_cost=float(construction_cost),
            soft_cost=float(soft_cost),
            selling_cost=float(selling_cost),
            total_cost=None,
            profit=None,
            margin=None,
            roi=None,
            max_allowable_offer=float(max_allowable_offer),
            is_underpriced=None,
            deal_score=None,
            infeasible=infeasible,
            comp_count=comp_count,
            confidence=finished_confidence,
            reasons=reasons,
        )

    total_cost = round(acquisition_cost + construction_cost + soft_cost + selling_cost)
    profit = round(arv - total_cost)
    margin = profit / arv if arv > 0 else None
    cost_basis = acquisition_cost + construction_cost + soft_cost
    roi = profit / cost_basis if cost_basis > 0 else None
    is_underpriced = not infeasible and acquisition_cost <= max_allowable_offer
    deal_score = (
        round(_clamp(margin / (2.0 * assumptions.target_margin) * 100.0, 0.0, 100.0), 1)
        if margin is not None and assumptions.target_margin > 0
        else None
    )

    reasons.append(
        f"Profit ${profit:,.0f} on ${total_cost:,.0f} all-in"
        + (f"; margin {margin:.1%}." if margin is not None else ".")
    )
    if is_underpriced:
        reasons.append("Acquisition is at or below the max allowable offer: looks underpriced.")

    return DealAnalysis(
        arv=float(arv),
        per_unit_value=round(per_unit_value, 2),
        gross_floor_area_sqft=round(gross_floor_area, 1),
        acquisition_cost=round(acquisition_cost, 2),
        construction_cost=float(construction_cost),
        soft_cost=float(soft_cost),
        selling_cost=float(selling_cost),
        total_cost=float(total_cost),
        profit=float(profit),
        margin=round(margin, 4) if margin is not None else None,
        roi=round(roi, 4) if roi is not None else None,
        max_allowable_offer=float(max_allowable_offer),
        is_underpriced=is_underpriced,
        deal_score=deal_score,
        infeasible=infeasible,
        comp_count=comp_count,
        confidence=finished_confidence,
        reasons=reasons,
    )
