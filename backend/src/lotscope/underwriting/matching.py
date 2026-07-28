from dataclasses import dataclass
from typing import Any, Literal

from lotscope.underwriting.schemas import BuyBox

MATCH_VERSION = "m1"

CriterionStatus = Literal["met", "not_met", "not_evaluated"]

RISK_CEILINGS: dict[str, float] = {"low": 30.0, "medium": 60.0, "high": 100.0}

_UNKNOWN_OFFER = "No maximum allowable offer could be calculated, so affordability is unconfirmed."
_UNKNOWN_MARGIN = "No estimated margin is available, so the return target is unconfirmed."
_UNKNOWN_UNITS = "No by-right unit count is available, so the unit range is unconfirmed."
_UNKNOWN_RISK = "No risk score is available, so risk tolerance is unconfirmed."
_UNKNOWN_TOLERANCE = "Risk tolerance is not one of low, medium, or high, so it cannot be applied."


@dataclass(frozen=True)
class MatchCandidate:
    parcel_number: str
    max_allowable_offer: float | None
    est_margin: float | None
    by_right_units: int | None
    risk_score: float | None


@dataclass(frozen=True)
class CriterionOutcome:
    name: str
    status: CriterionStatus
    detail: str


@dataclass(frozen=True)
class MatchResult:
    matched: bool
    criteria: list[CriterionOutcome]


def _price_outcome(candidate: MatchCandidate, ceiling: float) -> CriterionOutcome:
    if candidate.max_allowable_offer is None:
        return CriterionOutcome("max_acquisition_price", "not_evaluated", _UNKNOWN_OFFER)
    if candidate.max_allowable_offer <= ceiling:
        return CriterionOutcome(
            "max_acquisition_price",
            "met",
            f"Maximum allowable offer ${candidate.max_allowable_offer:,.0f} "
            f"is within your ${ceiling:,.0f} ceiling.",
        )
    return CriterionOutcome(
        "max_acquisition_price",
        "not_met",
        f"Maximum allowable offer ${candidate.max_allowable_offer:,.0f} "
        f"exceeds your ${ceiling:,.0f} ceiling.",
    )


def _margin_outcome(candidate: MatchCandidate, target: float) -> CriterionOutcome:
    if candidate.est_margin is None:
        return CriterionOutcome("min_margin", "not_evaluated", _UNKNOWN_MARGIN)
    if candidate.est_margin >= target:
        return CriterionOutcome(
            "min_margin",
            "met",
            f"Estimated margin {candidate.est_margin:.1%} meets your {target:.1%} target.",
        )
    return CriterionOutcome(
        "min_margin",
        "not_met",
        f"Estimated margin {candidate.est_margin:.1%} is below your {target:.1%} target.",
    )


def _units_outcome(
    candidate: MatchCandidate, minimum: int | None, maximum: int | None
) -> CriterionOutcome:
    if candidate.by_right_units is None:
        return CriterionOutcome("units", "not_evaluated", _UNKNOWN_UNITS)
    units = candidate.by_right_units
    if minimum is not None and units < minimum:
        return CriterionOutcome(
            "units", "not_met", f"{units} by-right units is below your minimum of {minimum}."
        )
    if maximum is not None and units > maximum:
        return CriterionOutcome(
            "units", "not_met", f"{units} by-right units is above your maximum of {maximum}."
        )
    return CriterionOutcome("units", "met", f"{units} by-right units is within your range.")


def _risk_outcome(candidate: MatchCandidate, tolerance: str) -> CriterionOutcome:
    ceiling = RISK_CEILINGS.get(tolerance.lower())
    if ceiling is None:
        return CriterionOutcome("risk_tolerance", "not_evaluated", _UNKNOWN_TOLERANCE)
    if candidate.risk_score is None:
        return CriterionOutcome("risk_tolerance", "not_evaluated", _UNKNOWN_RISK)
    if candidate.risk_score <= ceiling:
        return CriterionOutcome(
            "risk_tolerance",
            "met",
            f"Risk score {candidate.risk_score:.0f} is within your {tolerance} tolerance.",
        )
    return CriterionOutcome(
        "risk_tolerance",
        "not_met",
        f"Risk score {candidate.risk_score:.0f} exceeds your {tolerance} tolerance.",
    )


def evaluate_buy_box(candidate: MatchCandidate, buy_box: BuyBox) -> MatchResult:
    criteria: list[CriterionOutcome] = []
    if buy_box.max_acquisition_price is not None:
        criteria.append(_price_outcome(candidate, buy_box.max_acquisition_price))
    if buy_box.min_margin is not None:
        criteria.append(_margin_outcome(candidate, buy_box.min_margin))
    if buy_box.min_units is not None or buy_box.max_units is not None:
        criteria.append(_units_outcome(candidate, buy_box.min_units, buy_box.max_units))
    if buy_box.risk_tolerance is not None:
        criteria.append(_risk_outcome(candidate, buy_box.risk_tolerance))
    return MatchResult(
        matched=all(outcome.status == "met" for outcome in criteria),
        criteria=criteria,
    )


def match_conditions(buy_box: BuyBox) -> tuple[list[str], dict[str, Any]]:
    conditions: list[str] = []
    params: dict[str, Any] = {}
    if buy_box.max_acquisition_price is not None:
        conditions.append("v.max_allowable_offer <= :max_acquisition_price")
        params["max_acquisition_price"] = buy_box.max_acquisition_price
    if buy_box.min_margin is not None:
        conditions.append("v.est_margin >= :min_margin")
        params["min_margin"] = buy_box.min_margin
    if buy_box.min_units is not None:
        conditions.append("v.by_right_units >= :min_units")
        params["min_units"] = buy_box.min_units
    if buy_box.max_units is not None:
        conditions.append("v.by_right_units <= :max_units")
        params["max_units"] = buy_box.max_units
    ceiling = RISK_CEILINGS.get((buy_box.risk_tolerance or "").lower())
    if ceiling is not None:
        conditions.append("v.risk_score <= :risk_ceiling")
        params["risk_ceiling"] = ceiling
    return conditions, params
