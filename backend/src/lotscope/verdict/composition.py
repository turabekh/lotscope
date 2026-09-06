from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from lotscope.core.provenance import FieldProvenance
from lotscope.deal.schemas import DealResult
from lotscope.risk.schemas import RiskResult
from lotscope.valuation.confidence import CONFIDENCE_SCORE
from lotscope.valuation.schemas import ValuationResult
from lotscope.verdict.decision import STRONG_MARGIN, VIABLE_MARGIN, decide
from lotscope.verdict.trust import compose_field_trust
from lotscope.zoning.schemas import BuildabilityResult

_BUILDABILITY_WEIGHT = 0.6
_RISK_WEIGHT = 0.4

_ECONOMICS_FLOOR = 0.4
_ECONOMICS_CEILING = 1.0


@dataclass(frozen=True)
class ComposedVerdict:
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
    arv: float | None
    est_profit: float | None
    est_margin: float | None
    max_allowable_offer: float | None
    deal_score: float | None
    is_underpriced: bool | None
    risk_score: float | None
    risk_flags: list[dict[str, Any]]
    sources: list[dict[str, Any]]
    field_trust: dict[str, FieldProvenance] = field(default_factory=dict)
    recommendation: str | None = None
    recommendation_reason: str | None = None


def economics_factor(est_margin: float | None, deal_infeasible: bool) -> float:
    if deal_infeasible:
        return _ECONOMICS_FLOOR
    if est_margin is None:
        return _margin_factor(VIABLE_MARGIN)
    return _margin_factor(est_margin)


def _margin_factor(margin: float) -> float:
    if margin <= 0.0:
        return _ECONOMICS_FLOOR
    if margin >= STRONG_MARGIN:
        return _ECONOMICS_CEILING
    span = _ECONOMICS_CEILING - _ECONOMICS_FLOOR
    return _ECONOMICS_FLOOR + span * (margin / STRONG_MARGIN)


def _opportunity_score(
    buildability_score: float,
    risk_score: float,
    est_margin: float | None,
    deal_infeasible: bool,
) -> float:
    blended = _BUILDABILITY_WEIGHT * buildability_score + _RISK_WEIGHT * (100.0 - risk_score)
    scaled = blended * economics_factor(est_margin, deal_infeasible)
    return round(max(0.0, min(100.0, scaled)), 1)


def _assessment_market_gap(
    valuation: ValuationResult | None, assessed_market_value: float | None
) -> float | None:
    if valuation is None or valuation.estimate is None or assessed_market_value is None:
        return None
    return round(valuation.estimate - assessed_market_value, 0)


def _value_confidence(valuation: ValuationResult | None) -> float | None:
    if valuation is None or valuation.estimate is None:
        return None
    return CONFIDENCE_SCORE.get(valuation.confidence)


def _merge_sources(
    buildability: BuildabilityResult | None,
    valuation: ValuationResult | None,
    risk: RiskResult | None,
    deal: DealResult | None,
) -> list[dict[str, Any]]:
    merged: list[dict[str, Any]] = []
    if buildability is not None:
        merged.append({"dimension": "buildability", "sources": buildability.sources})
    if valuation is not None:
        merged.append({"dimension": "valuation", "sources": valuation.sources})
    if risk is not None:
        merged.append({"dimension": "risk", "sources": risk.sources})
    if deal is not None:
        merged.append({"dimension": "deal", "sources": deal.sources})
    return merged


def _summary(
    buildability: BuildabilityResult | None,
    valuation: ValuationResult | None,
    risk: RiskResult | None,
    deal: DealResult | None,
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
        count = buildability.by_right_units
        units = f" ({count} unit{'' if count == 1 else 's'})" if count else ""
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

    if deal is not None and deal.infeasible:
        parts.append("no land price reaches the target margin")
    elif deal is not None and deal.max_allowable_offer is not None:
        mao = f"MAO ${deal.max_allowable_offer:,.0f}"
        parts.append(f"{mao} (underpriced)" if deal.is_underpriced else mao)

    return "; ".join(parts) if parts else "Insufficient data for a verdict."


def compose_verdict(
    buildability: BuildabilityResult | None,
    valuation: ValuationResult | None,
    risk: RiskResult | None,
    deal: DealResult | None = None,
    *,
    assessed_market_value: float | None,
    source_ages: dict[str, datetime | None] | None = None,
) -> ComposedVerdict:
    buildability_score = buildability.buildability_score if buildability is not None else None
    risk_score = risk.risk_score if risk is not None else None
    est_margin = deal.margin if deal is not None else None
    deal_infeasible = deal.infeasible if deal is not None else False
    opportunity_score = _opportunity_score(
        buildability_score or 0.0, risk_score or 0.0, est_margin, deal_infeasible
    )
    assessment_market_gap = _assessment_market_gap(valuation, assessed_market_value)

    field_trust = compose_field_trust(
        buildability,
        valuation,
        deal,
        assessment_market_gap=assessment_market_gap,
        source_ages=source_ages or {},
    )
    screening = decide(
        field_trust=field_trust,
        can_build_by_right=buildability.can_build_by_right if buildability is not None else None,
        needs_variance=buildability.needs_variance if buildability is not None else None,
        requires_master_plan=(
            buildability.requires_master_plan if buildability is not None else False
        ),
        est_margin=est_margin,
        deal_infeasible=deal_infeasible,
        risk_score=risk_score,
        land_value_modelled=valuation is not None and valuation.estimate is not None,
        land_value_is_wide_area=valuation is not None
        and valuation.estimate is not None
        and valuation.wide_area,
        risk_flag_count=len(risk.flags) if risk is not None else 0,
    )

    return ComposedVerdict(
        field_trust=field_trust,
        recommendation=screening.recommendation,
        recommendation_reason=screening.reason,
        buildability_score=buildability_score,
        opportunity_score=opportunity_score,
        summary=_summary(buildability, valuation, risk, deal),
        can_build_by_right=buildability.can_build_by_right if buildability is not None else None,
        by_right_units=buildability.by_right_units if buildability is not None else None,
        max_height_ft=buildability.max_height_ft if buildability is not None else None,
        needs_variance=buildability.needs_variance if buildability is not None else None,
        buildable_area_sqft=buildability.buildable_area_sqft if buildability is not None else None,
        value_estimate_low=valuation.low if valuation is not None else None,
        value_estimate_high=valuation.high if valuation is not None else None,
        value_confidence=_value_confidence(valuation),
        assessment_market_gap=assessment_market_gap,
        arv=deal.arv if deal is not None else None,
        est_profit=deal.profit if deal is not None else None,
        est_margin=deal.margin if deal is not None else None,
        max_allowable_offer=deal.max_allowable_offer if deal is not None else None,
        deal_score=deal.deal_score if deal is not None else None,
        is_underpriced=deal.is_underpriced if deal is not None else None,
        risk_score=risk_score,
        risk_flags=[flag.model_dump() for flag in risk.flags] if risk is not None else [],
        sources=_merge_sources(buildability, valuation, risk, deal),
    )
