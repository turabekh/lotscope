import contextlib
import hashlib
from typing import Annotated, Any

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile, status
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.agent.envelope import ToolResult
from lotscope.agent.tools import REGISTRY
from lotscope.agent.tools.registry import ToolContext
from lotscope.ai.client import StructuredGenerator
from lotscope.ai.embeddings import Embedder
from lotscope.ai.prompts import (
    PROMPT_VERSION,
    REPORT_PROMPT_VERSION,
    SUMMARY_PROMPT_VERSION,
)
from lotscope.ai.schemas import ParcelReportResult, ParcelSummaryResult
from lotscope.ai.service import draft_parcel_report, summarize_parcel
from lotscope.api.deps import (
    ParcelKeyDep,
    get_app_settings,
    get_current_user,
    get_embedder,
    get_generator,
    get_redis,
    get_session,
    get_summary_generator,
)
from lotscope.assemblage.schemas import AssemblageResult
from lotscope.assemblage.service import compute_assemblage
from lotscope.assessment.schemas import AssessmentResult
from lotscope.assessment.service import analyze_parcel_assessment
from lotscope.checklist.schemas import ParcelChecklist
from lotscope.checklist.service import build_parcel_checklist
from lotscope.compare.schemas import ParcelCompareResponse
from lotscope.compare.service import MAX_COMPARE_PARCELS, compare_parcels
from lotscope.core.config import Settings
from lotscope.core.errors import NotFoundError
from lotscope.corrections.schemas import CorrectionCreate, CorrectionRead
from lotscope.corrections.service import report_correction
from lotscope.deal.schemas import DealResult, ScenariosResult
from lotscope.deal.service import analyze_parcel_deal, analyze_parcel_scenarios
from lotscope.deal.underwriting import build_underwriting
from lotscope.distress.schemas import DistressResult
from lotscope.distress.service import assess_parcel_distress
from lotscope.documents.schemas import DeedRestrictionsResponse
from lotscope.documents.service import analyze_uploaded_deed, get_deed_restrictions
from lotscope.documents.storage import LocalBlobStore
from lotscope.historic.schemas import HistoricResult
from lotscope.historic.service import get_parcel_historic
from lotscope.ingestion.service import source_freshness
from lotscope.market.schemas import MarketContext
from lotscope.market.service import get_parcel_market
from lotscope.owners.schemas import OwnerPortfolio
from lotscope.owners.service import get_owner_portfolio
from lotscope.parcels.schemas import ParcelDetail, SourceFreshness
from lotscope.parcels.service import get_parcel_detail, parcel_market_code
from lotscope.reports.dossier import dossier_filename
from lotscope.reports.service import build_parcel_dossier
from lotscope.risk.schemas import NextSheriffSale, SheriffSaleChange
from lotscope.risk.service import get_next_sheriff_sale, recent_sheriff_changes
from lotscope.subdivision.schemas import SubdivisionResult
from lotscope.subdivision.service import analyze_parcel_subdivision
from lotscope.valuation.schemas import ValuationResult
from lotscope.valuation.service import value_parcel
from lotscope.verdict import cache as verdict_cache
from lotscope.verdict.schemas import VerdictResult
from lotscope.verdict.service import get_verdict
from lotscope.zba.schemas import VarianceOutlook
from lotscope.zba.service import variance_outlook
from lotscope.zoning.schemas import EnvelopeResult
from lotscope.zoning.service import assess_parcel as assess_zoning
from lotscope.zoning.service import compute_envelope

router = APIRouter(prefix="/parcels", tags=["parcels"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]

_ASK_CACHE_TTL_SECONDS = 86_400
_SUMMARY_CACHE_TTL_SECONDS = 604_800
_REPORT_CACHE_TTL_SECONDS = 604_800


async def _resolve_report(
    session: AsyncSession,
    parcel_number: str,
    *,
    redis: Redis,
    generator: StructuredGenerator,
    model: str,
    git_sha: str,
) -> ParcelReportResult | None:
    inputs = await verdict_cache.input_fingerprint(session, parcel_number, git_sha=git_sha)
    scope = _generation_scope(REPORT_PROMPT_VERSION, model)
    cache_key = f"report:{scope}:{parcel_number}:{inputs or 'none'}"

    with contextlib.suppress(RedisError):
        cached = await redis.get(cache_key)
        if cached is not None:
            return ParcelReportResult.model_validate_json(cached)

    result = await draft_parcel_report(session, parcel_number, generator=generator)
    if result is None:
        return None

    with contextlib.suppress(RedisError):
        await redis.set(cache_key, result.model_dump_json(), ex=_REPORT_CACHE_TTL_SECONDS)
    return result


def _generation_scope(prompt_version: str, model: str) -> str:
    return f"{prompt_version}:{model}"


def _ask_cache_key(parcel_number: str, question: str, source: str, model: str) -> str:
    normalized = " ".join(question.lower().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    scope = _generation_scope(PROMPT_VERSION, model)
    return f"ask:{scope}:{parcel_number}:{source}:{digest}"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


@router.get("/compare", response_model=ParcelCompareResponse)
async def parcels_compare(
    session: SessionDep,
    current_user: CurrentUserDep,
    parcels: Annotated[list[str], Query(min_length=2, max_length=MAX_COMPARE_PARCELS)],
) -> ParcelCompareResponse:
    return await compare_parcels(session, parcels)


@router.get("/{parcel_number}", response_model=ParcelDetail)
async def parcel_detail(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> ParcelDetail:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return detail


@router.get("/{parcel_number}/verdict", response_model=VerdictResult)
async def parcel_verdict(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> VerdictResult:
    verdict = await get_verdict(session, parcel_number, redis=redis)
    if verdict is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return verdict


@router.get("/{parcel_number}/envelope", response_model=EnvelopeResult)
async def parcel_envelope(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> EnvelopeResult:
    envelope = await compute_envelope(session, parcel_number)
    if envelope is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return envelope


@router.get("/{parcel_number}/assemblage", response_model=AssemblageResult)
async def parcel_assemblage(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> AssemblageResult:
    result = await compute_assemblage(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/distress", response_model=DistressResult)
async def parcel_distress(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> DistressResult:
    result = await assess_parcel_distress(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/next-sheriff-sale", response_model=NextSheriffSale | None)
async def parcel_next_sheriff_sale(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> NextSheriffSale | None:
    return await get_next_sheriff_sale(session, parcel_number)


@router.get("/{parcel_number}/sheriff-changes", response_model=list[SheriffSaleChange])
async def parcel_sheriff_changes(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> list[SheriffSaleChange]:
    return await recent_sheriff_changes(session, parcel_number)


@router.get("/{parcel_number}/variance-outlook", response_model=VarianceOutlook)
async def parcel_variance_outlook(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> VarianceOutlook:
    result = await variance_outlook(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/owner-portfolio", response_model=OwnerPortfolio)
async def parcel_owner_portfolio(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> OwnerPortfolio:
    result = await get_owner_portfolio(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/deed-restrictions", response_model=DeedRestrictionsResponse)
async def parcel_deed_restrictions(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> DeedRestrictionsResponse:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return await get_deed_restrictions(
        session, parcel_number, record_url_template=settings.philadox_document_url_template
    )


@router.post(
    "/{parcel_number}/deeds/{document_id}/analyze", response_model=DeedRestrictionsResponse
)
async def analyze_parcel_deed(
    parcel_number: ParcelKeyDep,
    document_id: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    settings: SettingsDep,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    generator: Annotated[StructuredGenerator, Depends(get_generator)],
    file: Annotated[UploadFile, File()],
) -> DeedRestrictionsResponse:
    data = await file.read()
    return await analyze_uploaded_deed(
        session,
        parcel_number,
        document_id,
        data,
        file.content_type,
        embedder=embedder,
        generator=generator,
        blob_store=LocalBlobStore(settings.deed_blob_root),
        record_url_template=settings.philadox_document_url_template,
    )


@router.get("/{parcel_number}/summary", response_model=ParcelSummaryResult)
async def parcel_summary(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
    settings: SettingsDep,
    generator: Annotated[StructuredGenerator, Depends(get_summary_generator)],
) -> ParcelSummaryResult:
    if not settings.anthropic_api_key:
        raise NotFoundError("The AI summary is not available.")

    inputs = await verdict_cache.input_fingerprint(session, parcel_number, git_sha=settings.git_sha)
    scope = _generation_scope(SUMMARY_PROMPT_VERSION, settings.anthropic_summary_model)
    cache_key = f"summary:{scope}:{parcel_number}:{inputs or 'none'}"

    with contextlib.suppress(RedisError):
        cached = await redis.get(cache_key)
        if cached is not None:
            return ParcelSummaryResult.model_validate_json(cached)

    result = await summarize_parcel(session, parcel_number, generator=generator)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")

    with contextlib.suppress(RedisError):
        await redis.set(cache_key, result.model_dump_json(), ex=_SUMMARY_CACHE_TTL_SECONDS)
    return result


@router.get("/{parcel_number}/report", response_model=ParcelReportResult)
async def parcel_report(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
    settings: SettingsDep,
    generator: Annotated[StructuredGenerator, Depends(get_generator)],
) -> ParcelReportResult:
    if not settings.anthropic_api_key:
        raise NotFoundError("The AI report is not available.")

    result = await _resolve_report(
        session,
        parcel_number,
        redis=redis,
        generator=generator,
        model=settings.anthropic_model,
        git_sha=settings.git_sha,
    )
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/assessment", response_model=AssessmentResult)
async def parcel_assessment(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> AssessmentResult:
    result = await analyze_parcel_assessment(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/subdivision", response_model=SubdivisionResult)
async def parcel_subdivision(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> SubdivisionResult:
    result = await analyze_parcel_subdivision(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/historic", response_model=HistoricResult)
async def parcel_historic(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> HistoricResult:
    result = await get_parcel_historic(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/market", response_model=MarketContext)
async def parcel_market(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    radius_ft: Annotated[float, Query(gt=0, le=10000)] = 1500.0,
    years: Annotated[int, Query(ge=1, le=20)] = 3,
) -> MarketContext:
    result = await get_parcel_market(session, parcel_number, radius_ft=radius_ft, years=years)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.post(
    "/{parcel_number}/corrections",
    response_model=CorrectionRead,
    status_code=status.HTTP_201_CREATED,
)
async def report_parcel_correction(
    parcel_number: ParcelKeyDep,
    data: CorrectionCreate,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> CorrectionRead:
    market_code = await parcel_market_code(session, parcel_number)
    if market_code is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    verdict = await get_verdict(session, parcel_number)
    result = await report_correction(
        session,
        parcel_number=parcel_number,
        market_code=market_code,
        reported_by=current_user.id,
        request=data,
        verdict=verdict,
    )
    await session.commit()
    return result


@router.get("/{parcel_number}/underwriting")
async def parcel_underwriting(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    acquisition_price: Annotated[float | None, Query(ge=0)] = None,
    construction_cost_per_sqft: Annotated[float | None, Query(gt=0, le=2000)] = None,
    soft_cost_pct: Annotated[float | None, Query(ge=0, le=1)] = None,
    selling_cost_pct: Annotated[float | None, Query(ge=0, le=1)] = None,
    target_margin: Annotated[float | None, Query(ge=0, lt=1)] = None,
) -> dict[str, Any]:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    buildability = await assess_zoning(session, parcel_number)
    valuation = await value_parcel(session, parcel_number)
    analysis = await build_underwriting(
        session,
        parcel_number,
        owner_id=current_user.id,
        market_code=detail.market_code,
        base_zoning_code=detail.base_zoning_code,
        market_value=detail.market_value,
        buildability=buildability,
        land_value=valuation.estimate if valuation is not None else None,
        acquisition_price=acquisition_price,
        construction_cost_per_sqft=construction_cost_per_sqft,
        soft_cost_pct=soft_cost_pct,
        selling_cost_pct=selling_cost_pct,
        target_margin=target_margin,
    )
    return {
        "parcel_number": parcel_number,
        "assumptions": analysis.assumptions,
        "mao": analysis.mao,
        "cases": [
            {
                "case": result.case,
                "label": result.label,
                "rationale": result.rationale,
                "arv": result.arv,
                "total_cost": result.total_cost,
                "profit": result.profit,
                "margin": result.margin,
                "max_allowable_offer": result.max_allowable_offer,
                "infeasible": result.infeasible,
            }
            for result in analysis.cases.results
        ],
        "case_version": analysis.cases.case_version,
        "sensitivity": {
            "available": analysis.sensitivity.available,
            "unavailable_reason": analysis.sensitivity.unavailable_reason,
            "row_label": analysis.sensitivity.row_label,
            "column_label": analysis.sensitivity.column_label,
            "exit_multipliers": list(analysis.sensitivity.exit_multipliers),
            "cost_multipliers": list(analysis.sensitivity.cost_multipliers),
            "cells": [
                {
                    "exit_multiplier": cell.exit_multiplier,
                    "cost_multiplier": cell.cost_multiplier,
                    "margin": cell.margin,
                    "profit": cell.profit,
                    "infeasible": cell.infeasible,
                }
                for cell in analysis.sensitivity.cells
            ],
        },
        "computed_at": analysis.computed_at,
    }


@router.get("/{parcel_number}/freshness", response_model=list[SourceFreshness])
async def parcel_source_freshness(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> list[SourceFreshness]:
    market_code = await parcel_market_code(session, parcel_number)
    if market_code is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    rows = await source_freshness(session, market_code)
    return [SourceFreshness.model_validate(row) for row in rows]


# A Lot-page evidence section and the tool that answers it. The page reads the same tool
# the Analyst does, so a section and an answer in the conversation cannot disagree about
# what the record says — and the envelope's sources are the section's "Show me".
EVIDENCE_TOOLS = {
    "sheriff": "get_sheriff_listing",
    "deeds": "get_deed_chain",
    "violations": "get_violations",
    "delinquency": "get_delinquency",
}


@router.get("/{parcel_number}/evidence/{section}", response_model=ToolResult)
async def parcel_evidence(
    parcel_number: ParcelKeyDep,
    section: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> ToolResult:
    tool_name = EVIDENCE_TOOLS.get(section)
    if tool_name is None:
        raise NotFoundError(f"No evidence section is named {section!r}.")
    registered = REGISTRY.get(tool_name)
    if registered is None:
        raise NotFoundError(f"No tool named {tool_name!r} is registered.")
    payload = registered.input_model.model_validate({"parcel": parcel_number})
    return await registered.handler(session, ToolContext(user_id=current_user.id), payload)


@router.get("/{parcel_number}/checklist", response_model=ParcelChecklist)
async def parcel_checklist(
    parcel_number: ParcelKeyDep, session: SessionDep, current_user: CurrentUserDep
) -> ParcelChecklist:
    result = await build_parcel_checklist(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/dossier")
async def parcel_dossier(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
    settings: SettingsDep,
    generator: Annotated[StructuredGenerator, Depends(get_generator)],
) -> Response:
    report = None
    if settings.anthropic_api_key:
        report = await _resolve_report(
            session,
            parcel_number,
            redis=redis,
            generator=generator,
            model=settings.anthropic_model,
            git_sha=settings.git_sha,
        )
    pdf = await build_parcel_dossier(session, parcel_number, report=report)
    if pdf is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{dossier_filename(parcel_number)}"'
        },
    )


@router.get("/{parcel_number}/comps", response_model=ValuationResult)
async def parcel_comps(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    radius_ft: Annotated[float, Query(gt=0, le=10000)] = 1500.0,
    years: Annotated[int, Query(ge=1, le=20)] = 3,
) -> ValuationResult:
    result = await value_parcel(session, parcel_number, radius_ft=radius_ft, years=years)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/deal", response_model=DealResult)
async def parcel_deal(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    acquisition_price: Annotated[float | None, Query(ge=0)] = None,
    construction_cost_per_sqft: Annotated[float | None, Query(gt=0, le=2000)] = None,
    soft_cost_pct: Annotated[float | None, Query(ge=0, le=1)] = None,
    selling_cost_pct: Annotated[float | None, Query(ge=0, le=1)] = None,
    target_margin: Annotated[float | None, Query(ge=0, lt=1)] = None,
    radius_ft: Annotated[float, Query(gt=0, le=10000)] = 1500.0,
    years: Annotated[int, Query(ge=1, le=20)] = 3,
) -> DealResult:
    result = await analyze_parcel_deal(
        session,
        parcel_number,
        user_id=current_user.id,
        acquisition_price=acquisition_price,
        construction_cost_per_sqft=construction_cost_per_sqft,
        soft_cost_pct=soft_cost_pct,
        selling_cost_pct=selling_cost_pct,
        target_margin=target_margin,
        radius_ft=radius_ft,
        years=years,
    )
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/scenarios", response_model=ScenariosResult)
async def parcel_scenarios(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    current_user: CurrentUserDep,
    acquisition_price: Annotated[float | None, Query(ge=0)] = None,
    construction_cost_per_sqft: Annotated[float | None, Query(gt=0, le=2000)] = None,
    soft_cost_pct: Annotated[float | None, Query(ge=0, le=1)] = None,
    selling_cost_pct: Annotated[float | None, Query(ge=0, le=1)] = None,
    target_margin: Annotated[float | None, Query(ge=0, lt=1)] = None,
    radius_ft: Annotated[float, Query(gt=0, le=10000)] = 1500.0,
    years: Annotated[int, Query(ge=1, le=20)] = 3,
) -> ScenariosResult:
    result = await analyze_parcel_scenarios(
        session,
        parcel_number,
        user_id=current_user.id,
        acquisition_price=acquisition_price,
        construction_cost_per_sqft=construction_cost_per_sqft,
        soft_cost_pct=soft_cost_pct,
        selling_cost_pct=selling_cost_pct,
        target_margin=target_margin,
        radius_ft=radius_ft,
        years=years,
    )
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result
