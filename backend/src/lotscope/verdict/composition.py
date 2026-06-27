from dataclasses import dataclass
from typing import Any

from lotscope.risk.schemas import RiskResult
from lotscope.valuation.schemas import ValuationResult
from lotscope.zoning.schemas import BuildabilityResult

VERDICT_VERSION = "v1"

_CONFIDENCE_SCORE = {"high": 0.9, "medium": 0.6, "low": 0.3}
_BUILDABILITY_WEIGHT = 0.6
_RISK_WEIGHT = 0.4


@dataclass(frozen=True)
class ComposedVerdict:
    verdict_version: str
    buildability_score: float | None
    opportunity_score: float
    summary: str
    can_build_by_right: bool | None
    by_right_units: int | None
    max_height_ft: float | None
    needs_variance: bool | None
    buildable_area_sqft: float | None
    value_estimate_low: float | None
    value_estimate_high: float | None
    value_confidence: float | None
    assessment_market_gap: float | None
    risk_score: float | None
    risk_flags: list[dict[str, Any]]
    sources: list[dict[str, Any]]


def _opportunity_score(buildability_score: float, risk_score: float) -> float:
    blended = _BUILDABILITY_WEIGHT * buildability_score + _RISK_WEIGHT * (100.0 - risk_score)
    return round(max(0.0, min(100.0, blended)), 1)


def _assessment_market_gap(
    valuation: ValuationResult | None, assessed_market_value: float | None
) -> float | None:
    if valuation is None or valuation.estimate is None or assessed_market_value is None:
        return None
    return round(valuation.estimate - assessed_market_value, 0)


def _value_confidence(valuation: ValuationResult | None) -> float | None:
    if valuation is None or valuation.estimate is None:
        return None
    return _CONFIDENCE_SCORE.get(valuation.confidence)


def _merge_sources(
    buildability: BuildabilityResult | None,
    valuation: ValuationResult | None,
    risk: RiskResult | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    if buildability is not None:
        merged.append({"dimension": "buildability", "sources": buildability.sources})
    if valuation is not None:
        merged.append({"dimension": "valuation", "sources": valuation.sources})
    if risk is not None:
        merged.append({"dimension": "risk", "sources": risk.sources})
    return merged


def _summary(
    buildability: BuildabilityResult | None,
    valuation: ValuationResult | None,
    risk: RiskResult | None,
) -> str:
    parts: list[str] = []
    if buildability is not None and buildability.district_code:
        if buildability.requires_master_plan:
            status = "master plan required"
        elif buildability.can_build_by_right:
            status = "buildable by-right"
        elif buildability.needs_variance:
            status = "variance likely"
        else:
            status = "buildability uncertain"
        units = f" ({buildability.by_right_units} unit)" if buildability.by_right_units else ""
        parts.append(f"{buildability.district_code}: {status}{units}")
    elif buildability is not None:
        parts.append("zoning unresolved")

    if (
        valuation is not None
        and valuation.estimate is not None
        and valuation.low is not None
        and valuation.high is not None
    ):
        parts.append(f"est. ${valuation.low:,.0f}-${valuation.high:,.0f}")

    if risk is not None:
        parts.append(f"{len(risk.flags)} risk flag(s)" if risk.flags else "no major risk flags")

    return "; ".join(parts) if parts else "Insufficient data for a verdict."


def compose_verdict(
    buildability: BuildabilityResult | None,
    valuation: ValuationResult | None,
    risk: RiskResult | None,
    *,
    assessed_market_value: float | None,
    verdict_version: str = VERDICT_VERSION,
) -> ComposedVerdict:
    buildability_score = buildability.buildability_score if buildability is not None else None
    risk_score = risk.risk_score if risk is not None else None
    opportunity_score = _opportunity_score(buildability_score or 0.0, risk_score or 0.0)

    return ComposedVerdict(
        verdict_version=verdict_version,
        buildability_score=buildability_score,
        opportunity_score=opportunity_score,
        summary=_summary(buildability, valuation, risk),
        can_build_by_right=buildability.can_build_by_right if buildability is not None else None,
        by_right_units=buildability.by_right_units if buildability is not None else None,
        max_height_ft=buildability.max_height_ft if buildability is not None else None,
        needs_variance=buildability.needs_variance if buildability is not None else None,
        buildable_area_sqft=buildability.buildable_area_sqft if buildability is not None else None,
        value_estimate_low=valuation.low if valuation is not None else None,
        value_estimate_high=valuation.high if valuation is not None else None,
        value_confidence=_value_confidence(valuation),
        assessment_market_gap=_assessment_market_gap(valuation, assessed_market_value),
        risk_score=risk_score,
        risk_flags=[flag.model_dump() for flag in risk.flags] if risk is not None else [],
        sources=_merge_sources(buildability, valuation, risk),
    )
