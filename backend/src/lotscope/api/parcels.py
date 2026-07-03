import contextlib
import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, Response, UploadFile
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import ask_daily_limit, parcel_view_daily_limit
from lotscope.accounts.usage import (
    get_ask_usage,
    increment_ask_usage,
    register_parcel_view,
)
from lotscope.ai.client import StructuredGenerator
from lotscope.ai.embeddings import Embedder
from lotscope.ai.schemas import ParcelAnswer
from lotscope.ai.service import ask_the_parcel
from lotscope.api.deps import (
    get_app_settings,
    get_current_user,
    get_embedder,
    get_generator,
    get_redis,
    get_session,
)
from lotscope.appeal.schemas import AppealPacketStatus
from lotscope.appeal.service import has_entitlement, packet_status, redeem_packet
from lotscope.assemblage.schemas import AssemblageResult
from lotscope.assemblage.service import compute_assemblage
from lotscope.assessment.schemas import AssessmentResult
from lotscope.assessment.service import analyze_parcel_assessment
from lotscope.checklist.schemas import ParcelChecklist
from lotscope.checklist.service import build_parcel_checklist
from lotscope.compare.schemas import ParcelCompareResponse
from lotscope.compare.service import MAX_COMPARE_PARCELS, compare_parcels
from lotscope.core.config import Settings
from lotscope.core.errors import ForbiddenError, NotFoundError, QuotaExceededError
from lotscope.deal.schemas import DealResult, ScenariosResult
from lotscope.deal.service import analyze_parcel_deal, analyze_parcel_scenarios
from lotscope.distress.schemas import DistressResult
from lotscope.distress.service import assess_parcel_distress
from lotscope.documents.schemas import DeedRestrictionsResponse
from lotscope.documents.service import analyze_uploaded_deed, get_deed_restrictions
from lotscope.documents.storage import LocalBlobStore
from lotscope.historic.schemas import HistoricResult
from lotscope.historic.service import get_parcel_historic
from lotscope.market.schemas import MarketContext
from lotscope.market.service import get_parcel_market
from lotscope.owners.schemas import OwnerPortfolio
from lotscope.owners.service import get_owner_portfolio
from lotscope.parcels.schemas import ParcelDetail
from lotscope.parcels.service import get_parcel_detail
from lotscope.reports.appeal_packet import appeal_packet_filename
from lotscope.reports.dossier import dossier_filename
from lotscope.reports.service import build_appeal_packet, build_parcel_dossier
from lotscope.subdivision.schemas import SubdivisionResult
from lotscope.subdivision.service import analyze_parcel_subdivision
from lotscope.valuation.schemas import ValuationResult
from lotscope.valuation.service import value_parcel
from lotscope.verdict.schemas import VerdictResult
from lotscope.verdict.service import compute_verdict, get_verdict
from lotscope.zoning.schemas import EnvelopeResult
from lotscope.zoning.service import compute_envelope

router = APIRouter(prefix="/parcels", tags=["parcels"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]

_ASK_CACHE_TTL_SECONDS = 86_400


def _ask_cache_key(parcel_number: str, question: str) -> str:
    normalized = " ".join(question.lower().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"ask:{parcel_number}:{digest}"


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
    parcel_number: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> ParcelDetail:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    limit = parcel_view_daily_limit(current_user.tier)
    if limit is not None:
        allowed = True
        with contextlib.suppress(RedisError):
            allowed = await register_parcel_view(redis, current_user.id, parcel_number, limit)
        if not allowed:
            raise QuotaExceededError(
                f"You've reached your {current_user.tier} plan's limit of {limit} parcels per "
                "day. Upgrade to explore more lots."
            )
    return detail


@router.get("/{parcel_number}/verdict", response_model=VerdictResult)
async def parcel_verdict(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> VerdictResult:
    verdict = await get_verdict(session, parcel_number)
    if verdict is None:
        raise NotFoundError(
            f"No verdict has been computed for parcel {parcel_number}; refresh it first."
        )
    return verdict


@router.post("/{parcel_number}/verdict/refresh", response_model=VerdictResult)
async def refresh_parcel_verdict(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> VerdictResult:
    verdict = await compute_verdict(session, parcel_number)
    if verdict is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    await session.commit()
    return verdict


@router.get("/{parcel_number}/envelope", response_model=EnvelopeResult)
async def parcel_envelope(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> EnvelopeResult:
    envelope = await compute_envelope(session, parcel_number)
    if envelope is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return envelope


@router.get("/{parcel_number}/assemblage", response_model=AssemblageResult)
async def parcel_assemblage(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> AssemblageResult:
    result = await compute_assemblage(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/distress", response_model=DistressResult)
async def parcel_distress(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> DistressResult:
    result = await assess_parcel_distress(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/owner-portfolio", response_model=OwnerPortfolio)
async def parcel_owner_portfolio(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> OwnerPortfolio:
    result = await get_owner_portfolio(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/deed-restrictions", response_model=DeedRestrictionsResponse)
async def parcel_deed_restrictions(
    parcel_number: str,
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
    parcel_number: str,
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


@router.get("/{parcel_number}/assessment", response_model=AssessmentResult)
async def parcel_assessment(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> AssessmentResult:
    result = await analyze_parcel_assessment(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/subdivision", response_model=SubdivisionResult)
async def parcel_subdivision(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> SubdivisionResult:
    result = await analyze_parcel_subdivision(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/historic", response_model=HistoricResult)
async def parcel_historic(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> HistoricResult:
    result = await get_parcel_historic(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/market", response_model=MarketContext)
async def parcel_market(
    parcel_number: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    radius_ft: Annotated[float, Query(gt=0, le=10000)] = 1500.0,
    years: Annotated[int, Query(ge=1, le=20)] = 3,
) -> MarketContext:
    result = await get_parcel_market(session, parcel_number, radius_ft=radius_ft, years=years)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/checklist", response_model=ParcelChecklist)
async def parcel_checklist(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> ParcelChecklist:
    result = await build_parcel_checklist(session, parcel_number)
    if result is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return result


@router.get("/{parcel_number}/dossier")
async def parcel_dossier(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> Response:
    pdf = await build_parcel_dossier(session, parcel_number)
    if pdf is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{dossier_filename(parcel_number)}"'
        },
    )


@router.get("/{parcel_number}/appeal-packet", response_model=AppealPacketStatus)
async def parcel_appeal_packet_status(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> AppealPacketStatus:
    return await packet_status(session, current_user.id, parcel_number)


@router.post("/{parcel_number}/appeal-packet", response_model=AppealPacketStatus)
async def redeem_parcel_appeal_packet(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> AppealPacketStatus:
    detail = await get_parcel_detail(session, parcel_number)
    if detail is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    status = await redeem_packet(session, current_user.id, parcel_number)
    await session.commit()
    return status


@router.get("/{parcel_number}/appeal-packet.pdf")
async def download_parcel_appeal_packet(
    parcel_number: str, session: SessionDep, current_user: CurrentUserDep
) -> Response:
    if not await has_entitlement(session, current_user.id, parcel_number):
        raise ForbiddenError("Purchase or redeem the Assessment Review Packet to download it.")
    pdf = await build_appeal_packet(session, parcel_number)
    if pdf is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{appeal_packet_filename(parcel_number)}"'
        },
    )


@router.get("/{parcel_number}/comps", response_model=ValuationResult)
async def parcel_comps(
    parcel_number: str,
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
    parcel_number: str,
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
    parcel_number: str,
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


@router.post("/{parcel_number}/ask", response_model=ParcelAnswer)
async def ask_parcel(
    parcel_number: str,
    body: AskRequest,
    session: SessionDep,
    embedder: Annotated[Embedder, Depends(get_embedder)],
    generator: Annotated[StructuredGenerator, Depends(get_generator)],
    redis: Annotated[Redis, Depends(get_redis)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ParcelAnswer:
    cache_key = _ask_cache_key(parcel_number, body.question)
    try:
        cached = await redis.get(cache_key)
    except RedisError:
        cached = None
    if cached is not None:
        return ParcelAnswer.model_validate_json(cached)

    limit = ask_daily_limit(current_user.tier)
    if limit is not None:
        used = 0
        with contextlib.suppress(RedisError):
            used = await get_ask_usage(redis, current_user.id)
        if used >= limit:
            raise QuotaExceededError(
                f"You've reached your {current_user.tier} plan's daily limit of "
                f"{limit} AI questions. It resets tomorrow."
            )

    answer = await ask_the_parcel(
        session, parcel_number, body.question, embedder=embedder, generator=generator
    )
    if answer is None:
        raise NotFoundError(f"Parcel {parcel_number} was not found.")
    with contextlib.suppress(RedisError):
        await increment_ask_usage(redis, current_user.id)
        await redis.set(cache_key, answer.model_dump_json(), ex=_ASK_CACHE_TTL_SECONDS)
    return answer
