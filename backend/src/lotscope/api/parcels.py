import contextlib
import hashlib
from typing import Annotated

from fastapi import APIRouter, Depends, Query
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
    get_current_user,
    get_embedder,
    get_generator,
    get_redis,
    get_session,
)
from lotscope.assemblage.schemas import AssemblageResult
from lotscope.assemblage.service import compute_assemblage
from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.distress.schemas import DistressResult
from lotscope.distress.service import assess_parcel_distress
from lotscope.parcels.schemas import ParcelDetail
from lotscope.parcels.service import get_parcel_detail
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

_ASK_CACHE_TTL_SECONDS = 86_400


def _ask_cache_key(parcel_number: str, question: str) -> str:
    normalized = " ".join(question.lower().split())
    digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
    return f"ask:{parcel_number}:{digest}"


class AskRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)


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
