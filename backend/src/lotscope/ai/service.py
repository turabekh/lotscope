from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.client import StructuredGenerator
from lotscope.ai.embeddings import Embedder
from lotscope.ai.errors import GenerationError, UngroundedAnswerError
from lotscope.ai.prompts import (
    REPORT_SYSTEM_PROMPT,
    SUMMARY_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    build_report_prompt,
    build_summary_prompt,
    build_user_prompt,
    for_market,
)
from lotscope.ai.retrieval import (
    embed_and_search,
    fetch_district_documents,
    search_parcel_documents,
)
from lotscope.ai.schemas import (
    ParcelAnswer,
    ParcelReport,
    ParcelReportResult,
    ParcelSummary,
    ParcelSummaryResult,
)
from lotscope.assessment.schemas import AssessmentResult
from lotscope.assessment.service import analyze_parcel_assessment
from lotscope.distress.schemas import DistressResult
from lotscope.distress.service import assess_parcel_distress
from lotscope.markets.capabilities import market_display_name, risk_coverage_note
from lotscope.parcels.schemas import ParcelDetail
from lotscope.parcels.service import get_parcel_detail
from lotscope.verdict.schemas import VerdictResult
from lotscope.verdict.service import get_verdict
from lotscope.zoning.service import assess_parcel as assess_zoning

TITLE_14_SOURCE = "title14"
ZONING_SOURCE = "zoning"
DEED_SOURCE = "deed"


def zoning_retrieval_scope(market_code: str) -> tuple[str, str | None]:
    if market_code == "phl":
        return TITLE_14_SOURCE, None
    return ZONING_SOURCE, market_code


_HIGH_COVERAGE_MIN = 3
_MEDIUM_COVERAGE_MIN = 2

_SUMMARY_SOURCES: list[dict[str, Any]] = [
    {"source": "parcel"},
    {"source": "parcel_verdict"},
    {"source": "parcel_distress"},
    {"source": "assessment"},
]

_REPORT_SOURCES: list[dict[str, Any]] = [
    {"source": "parcel"},
    {"source": "parcel_verdict"},
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
            f"Verdict ({verdict.verdict_version}): {verdict.summary}. "
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
    ratio = detail.assessment_ratio
    if detail.market_value is not None and ratio is not None and ratio != 1.0:
        implied = detail.market_value / ratio
        return (
            f"Assessed value: {detail.market_value} — this is a base-year assessment at the "
            f"county common level ratio ({ratio:.4f}), NOT market value; the implied market "
            f"value is about {implied:.0f}. Never present the raw assessment as market value."
        )
    return f"Assessed value: {detail.market_value}."


def _summary_facts(
    detail: ParcelDetail,
    verdict: VerdictResult | None,
    distress: DistressResult | None,
    assessment: AssessmentResult | None,
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
                "new construction is NOT economically feasible (estimated build cost exceeds "
                "achievable finished value; do not present a negative offer or margin)"
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
        flags = [str(flag.get("label", "")) for flag in verdict.risk_flags][:4]
        if flags:
            lines.append(f"Top risk flags: {', '.join(flags)}.")
        coverage = risk_coverage_note(detail.market_code)
        if coverage is not None:
            lines.append(
                f"Risk coverage: the risk read is {coverage}; some feeds present in other "
                "markets are absent here, so no flags does not prove a clean parcel."
            )
    if distress is not None and distress.factors:
        factors = ", ".join(factor.label for factor in distress.factors[:4])
        lines.append(f"Distress score {distress.score}/100 ({distress.tier}): {factors}.")
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

    facts = _summary_facts(detail, verdict, distress, assessment)
    raw = await generator.generate(
        system=for_market(SUMMARY_SYSTEM_PROMPT, market_display_name(detail.market_code)),
        user=build_summary_prompt(facts),
        schema=ParcelSummary,
    )
    try:
        summary = ParcelSummary.model_validate(raw)
    except ValidationError as error:
        raise GenerationError(f"The model returned an invalid summary: {error}") from error

    return ParcelSummaryResult(
        parcel_number=parcel_number,
        verdict_version=verdict.verdict_version if verdict is not None else "none",
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
) -> str:
    facts = _summary_facts(detail, verdict, distress, assessment)
    if verdict is not None and verdict.arv is not None:
        if _deal_is_infeasible(verdict):
            facts += (
                f"\nDeal model: ARV {verdict.arv}, but estimated build cost exceeds it — new "
                "construction is not economically feasible here; do not cite a specific negative "
                "profit or margin."
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

    facts = _report_facts(detail, verdict, distress, assessment, cited_section)
    raw = await generator.generate(
        system=for_market(REPORT_SYSTEM_PROMPT, market_display_name(detail.market_code)),
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


async def ask_the_parcel(
    session: AsyncSession,
    parcel_number: str,
    question: str,
    *,
    embedder: Embedder,
    generator: StructuredGenerator,
    document_limit: int = 5,
) -> ParcelAnswer | None:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        return None

    verdict = await get_verdict(session, parcel_number)
    zoning_source, zoning_market = zoning_retrieval_scope(detail.market_code)
    documents = await embed_and_search(
        session,
        embedder,
        question,
        limit=document_limit,
        source=zoning_source,
        market=zoning_market,
    )
    if detail.base_zoning_code:
        pinned = await fetch_district_documents(
            session, detail.base_zoning_code, source=zoning_source, market=zoning_market
        )
        if pinned:
            seen = {document.id for document in pinned}
            documents = (pinned + [d for d in documents if d.id not in seen])[
                : max(document_limit, len(pinned))
            ]

    deeds = await search_parcel_documents(
        session, embedder, question, parcel_number, source=DEED_SOURCE, limit=3
    )
    documents = documents + deeds
    user_prompt = build_user_prompt(question, _parcel_facts(detail, verdict), documents)

    raw = await generator.generate(
        system=for_market(SYSTEM_PROMPT, market_display_name(detail.market_code)),
        user=user_prompt,
        schema=ParcelAnswer,
    )
    try:
        answer = ParcelAnswer.model_validate(raw)
    except ValidationError as error:
        raise GenerationError(f"The model returned an invalid answer: {error}") from error

    if not answer.citations:
        raise UngroundedAnswerError
    return answer
