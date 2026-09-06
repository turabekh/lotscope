from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.client import StructuredGenerator
from lotscope.ai.context import (
    ContextBudget,
    dedupe,
    expand_refs,
    expand_to_windows,
    fit_to_budget,
)
from lotscope.ai.districts import district_anchor_cites
from lotscope.ai.embeddings import Embedder
from lotscope.ai.errors import GenerationError
from lotscope.ai.prompts import (
    REPORT_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    build_report_prompt,
    build_summary_prompt,
)
from lotscope.ai.query_terms import extract_cites, extract_districts
from lotscope.ai.retrieval import (
    embed_and_search,
    fetch_documents_by_cite,
)
from lotscope.ai.schemas import (
    ParcelReport,
    ParcelReportResult,
    ParcelSummary,
    ParcelSummaryResult,
    RetrievedDocument,
)
from lotscope.ai.scope import (
    RetrievalScope,
    zoning_retrieval_scope,
)
from lotscope.assessment.schemas import AssessmentResult
from lotscope.assessment.service import analyze_parcel_assessment
from lotscope.core.market import MARKET_CODE
from lotscope.distress.schemas import DistressResult
from lotscope.distress.service import assess_parcel_distress
from lotscope.parcels.schemas import ParcelDetail
from lotscope.parcels.service import get_parcel_detail
from lotscope.risk.schemas import ViolationPosture
from lotscope.risk.service import get_violation_posture
from lotscope.verdict.schemas import VerdictResult
from lotscope.verdict.service import get_verdict
from lotscope.zoning.service import assess_parcel as assess_zoning

DEED_SOURCE = "deed"

_HIGH_COVERAGE_MIN = 3
_MEDIUM_COVERAGE_MIN = 2

_SUMMARY_SOURCES: list[dict[str, Any]] = [
    {"source": "parcel"},
    {"source": "lotscope_verdict"},
    {"source": "parcel_distress"},
    {"source": "assessment"},
]

_REPORT_SOURCES: list[dict[str, Any]] = [
    {"source": "parcel"},
    {"source": "lotscope_verdict"},
    {"source": "parcel_distress"},
    {"source": "assessment"},
    {"source": "zoning"},
]


def _parcel_facts(detail: ParcelDetail, verdict: VerdictResult | None) -> str:
    lines = [
        f"Parcel {detail.parcel_number}; address {detail.address}; "
        f"zoning {detail.resolved_zoning_code or detail.base_zoning_code or 'unknown'}; "
        f"lot area {detail.lot_area_sqft} sqft; "
        f"vacant={detail.is_vacant}; city-owned={detail.is_city_owned}."
    ]
    if verdict is not None:
        lines.append(
            f"Verdict: {verdict.summary}. "
            f"can_build_by_right={verdict.can_build_by_right}; "
            f"by_right_units={verdict.by_right_units}; risk_score={verdict.risk_score}."
        )
    return "\n".join(lines)


def _data_coverage(
    verdict: VerdictResult | None, assessment: AssessmentResult | None
) -> Literal["high", "medium", "low"]:
    present = 0
    if verdict is not None:
        present += 1
    if verdict is not None and verdict.value_estimate_low is not None:
        present += 1
    if assessment is not None and assessment.status != "unknown":
        present += 1
    if present >= _HIGH_COVERAGE_MIN:
        return "high"
    if present >= _MEDIUM_COVERAGE_MIN:
        return "medium"
    return "low"


def _deal_is_infeasible(verdict: VerdictResult) -> bool:
    return verdict.max_allowable_offer is not None and verdict.max_allowable_offer <= 0


def _assessed_value_fact(detail: ParcelDetail) -> str:
    return f"Assessed value: {detail.market_value}."


_RISK_FLAG_LIMIT = 4
_DISTRESS_FACTOR_LIMIT = 4

_SEVERITY_READING = {
    "info": "informational context, not a live burden on the current owner",
    "low": "low severity",
    "medium": "medium severity",
    "high": "high severity",
}


def _risk_flag_lines(risk_flags: list[dict[str, Any]]) -> list[str]:
    shown = risk_flags[:_RISK_FLAG_LIMIT]
    header = (
        f"Risk flags ({len(shown)} of {len(risk_flags)} shown), each as severity - label - detail:"
        if len(risk_flags) > len(shown)
        else f"Risk flags (all {len(risk_flags)}), each as severity - label - detail:"
    )
    lines = [header]
    for flag in shown:
        severity = str(flag.get("severity", "")).strip()
        reading = _SEVERITY_READING.get(severity, severity or "unrated")
        lines.append(f"- {reading} - {flag.get('label', '')} - {flag.get('detail', '')}".rstrip())
    return lines


def _violation_posture_fact(posture: ViolationPosture) -> str:
    if posture.violations_on_record == 0:
        return "L&I violations: none on record."
    if posture.open_violations == 0:
        return (
            f"L&I violations: {posture.violations_on_record} on record, "
            "0 currently open - every violation on record has been complied with or closed. "
            "This is history, not an active violation."
        )
    return (
        f"L&I violations: {posture.violations_on_record} on record, "
        f"{posture.open_violations} currently open and unresolved."
    )


def _distress_fact(distress: DistressResult) -> str:
    shown = distress.factors[:_DISTRESS_FACTOR_LIMIT]
    named = ", ".join(f"{factor.label} (+{factor.weight})" for factor in shown)
    if len(shown) < len(distress.factors):
        completeness = (
            f"These are the {len(shown)} largest of {len(distress.factors)} signals present."
        )
    else:
        completeness = "No other distress signal was found on this parcel."
    return (
        f"Distress score {distress.score}/100 ({distress.tier}). The score is the sum of the "
        f"distress signals PRESENT on this parcel, and each signal listed here ADDS to it: "
        f"{named}. {completeness} The score is {distress.score} because these are the only "
        "signals found, not because the listed signals are absent."
    )


def _summary_facts(
    detail: ParcelDetail,
    verdict: VerdictResult | None,
    distress: DistressResult | None,
    assessment: AssessmentResult | None,
    violations: ViolationPosture | None = None,
) -> str:
    lines = [
        f"Address: {detail.address or 'unknown'}; parcel {detail.parcel_number}.",
        f"Zoning: {detail.resolved_zoning_code or detail.base_zoning_code or 'unknown'}; "
        f"land use: {detail.land_use or 'unknown'}.",
        f"Lot area: {detail.lot_area_sqft} sqft; vacant: {detail.is_vacant}; "
        f"city-owned: {detail.is_city_owned}.",
        _assessed_value_fact(detail),
    ]
    if verdict is not None:
        if _deal_is_infeasible(verdict):
            deal_read = (
                "the modelled build does not reach the target margin at any land price, so "
                "there is no acquisition price that hits the target (do not present a negative "
                "offer; the deal may still show a positive margin at the modelled land price)"
            )
        else:
            deal_read = (
                f"max allowable offer {verdict.max_allowable_offer}; deal score "
                f"{verdict.deal_score}; underpriced: {verdict.is_underpriced}"
            )
        lines.append(
            f"Verdict: opportunity score {verdict.opportunity_score}/100; "
            f"buildable by-right: {verdict.can_build_by_right}; by-right units: "
            f"{verdict.by_right_units}; estimated land value "
            f"{verdict.value_estimate_low}-{verdict.value_estimate_high}; "
            f"{deal_read}; risk score {verdict.risk_score}."
        )
        if verdict.risk_flags:
            lines.extend(_risk_flag_lines(verdict.risk_flags))
    if violations is not None:
        lines.append(_violation_posture_fact(violations))
    if distress is not None and distress.factors:
        lines.append(_distress_fact(distress))
    if assessment is not None and assessment.status != "unknown":
        lines.append(
            f"Assessment: {assessment.status.replace('_', ' ')}; modeled market value "
            f"{assessment.market_estimate}; estimated annual tax savings if appealed "
            f"{assessment.estimated_annual_tax_savings}."
        )
    return "\n".join(lines)


async def summarize_parcel(
    session: AsyncSession,
    parcel_number: str,
    *,
    generator: StructuredGenerator,
) -> ParcelSummaryResult | None:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        return None

    verdict = await get_verdict(session, parcel_number)
    distress = await assess_parcel_distress(session, parcel_number)
    assessment = await analyze_parcel_assessment(session, parcel_number)

    violations = await get_violation_posture(session, parcel_number)

    facts = _summary_facts(detail, verdict, distress, assessment, violations)
    raw = await generator.generate(
        system=SUMMARY_SYSTEM_PROMPT,
        user=build_summary_prompt(facts),
        schema=ParcelSummary,
    )
    try:
        summary = ParcelSummary.model_validate(raw)
    except ValidationError as error:
        raise GenerationError(f"The model returned an invalid summary: {error}") from error

    return ParcelSummaryResult(
        parcel_number=parcel_number,
        summary=summary.summary,
        data_coverage=_data_coverage(verdict, assessment),
        is_informational=summary.is_informational,
        sources=_SUMMARY_SOURCES,
        computed_at=datetime.now(UTC),
    )


def _report_facts(
    detail: ParcelDetail,
    verdict: VerdictResult | None,
    distress: DistressResult | None,
    assessment: AssessmentResult | None,
    cited_section: str | None,
    violations: ViolationPosture | None = None,
) -> str:
    facts = _summary_facts(detail, verdict, distress, assessment, violations)
    if verdict is not None and verdict.arv is not None:
        if _deal_is_infeasible(verdict):
            facts += (
                f"\nDeal model: ARV {verdict.arv}, but the build does not reach the target "
                "margin at any land price; do not cite a negative max allowable offer."
            )
        else:
            facts += (
                f"\nDeal model: ARV {verdict.arv}; estimated profit {verdict.est_profit}; "
                f"estimated margin {verdict.est_margin}."
            )
    if cited_section:
        facts += f"\nBuildability basis: LotScope zoning analysis cites Title 14 § {cited_section}."
    return facts


async def draft_parcel_report(
    session: AsyncSession,
    parcel_number: str,
    *,
    generator: StructuredGenerator,
) -> ParcelReportResult | None:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        return None

    verdict = await get_verdict(session, parcel_number)
    distress = await assess_parcel_distress(session, parcel_number)
    assessment = await analyze_parcel_assessment(session, parcel_number)
    buildability = await assess_zoning(session, parcel_number)
    cited_section = buildability.cited_section if buildability is not None else None

    violations = await get_violation_posture(session, parcel_number)

    facts = _report_facts(detail, verdict, distress, assessment, cited_section, violations)
    raw = await generator.generate(
        system=REPORT_SYSTEM_PROMPT,
        user=build_report_prompt(facts),
        schema=ParcelReport,
    )
    try:
        report = ParcelReport.model_validate(raw)
    except ValidationError as error:
        raise GenerationError(f"The model returned an invalid report: {error}") from error

    return ParcelReportResult(
        parcel_number=parcel_number,
        headline=report.headline,
        sections=report.sections,
        recommendation=report.recommendation,
        confidence=report.confidence,
        is_informational=report.is_informational,
        sources=_REPORT_SOURCES,
        computed_at=datetime.now(UTC),
    )


async def _canonical_context(
    session: AsyncSession,
    embedder: Embedder,
    question: str,
    *,
    scope: RetrievalScope,
    market_code: str,
    zoning_code: str | None,
    document_limit: int,
) -> list[RetrievedDocument]:
    anchor_cites = list(extract_cites(question))
    for district in [*extract_districts(question), *([zoning_code] if zoning_code else [])]:
        for cite in await district_anchor_cites(
            session, district, market_code=market_code, titles=scope.titles
        ):
            if cite not in anchor_cites:
                anchor_cites.append(cite)

    anchors = await fetch_documents_by_cite(
        session,
        anchor_cites,
        source=scope.source,
        market=scope.market,
        titles=scope.titles,
    )
    matched = await embed_and_search(
        session,
        embedder,
        question,
        limit=document_limit,
        source=scope.source,
        market=scope.market,
        titles=scope.titles,
    )
    leads = dedupe(anchors + matched)
    windows = await expand_to_windows(session, leads, market_code=market_code, scope=scope)
    referenced = await expand_refs(session, leads, market_code=market_code, scope=scope)
    return fit_to_budget(leads + windows + referenced, ContextBudget())


async def retrieve_code_context(
    session: AsyncSession,
    embedder: Embedder,
    question: str,
    *,
    zoning_code: str | None = None,
    document_limit: int = 5,
) -> list[RetrievedDocument]:
    return await _canonical_context(
        session,
        embedder,
        question,
        scope=zoning_retrieval_scope(),
        market_code=MARKET_CODE,
        zoning_code=zoning_code,
        document_limit=document_limit,
    )
