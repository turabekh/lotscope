import contextlib
from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import market_stats_access
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.core.errors import QuotaExceededError
from lotscope.neighborhoods.schemas import (
    NeighborhoodListResponse,
    NeighborhoodMarketResponse,
)
from lotscope.neighborhoods.service import list_neighborhoods, neighborhood_market_stats

router = APIRouter(tags=["neighborhoods"])

_MARKET_CACHE_KEY = "neighborhoods:market"
_MARKET_CACHE_TTL_SECONDS = 3_600


@router.get("/neighborhoods", response_model=NeighborhoodListResponse)
async def get_neighborhoods(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NeighborhoodListResponse:
    return NeighborhoodListResponse(neighborhoods=await list_neighborhoods(session))


@router.get("/neighborhoods/market", response_model=NeighborhoodMarketResponse)
async def get_neighborhood_market(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> NeighborhoodMarketResponse:
    if not market_stats_access(current_user.tier):
        raise QuotaExceededError(
            "Market intelligence is a Pro feature — upgrade to see neighborhood opportunity stats."
        )

    with contextlib.suppress(RedisError):
        cached = await redis.get(_MARKET_CACHE_KEY)
        if cached is not None:
            return NeighborhoodMarketResponse.model_validate_json(cached)

    result = await neighborhood_market_stats(session)

    with contextlib.suppress(RedisError):
        await redis.set(_MARKET_CACHE_KEY, result.model_dump_json(), ex=_MARKET_CACHE_TTL_SECONDS)
    return result
