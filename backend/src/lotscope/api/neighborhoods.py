import contextlib
from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.core.market import MARKET_CODE
from lotscope.neighborhoods.schemas import (
    NeighborhoodListResponse,
    NeighborhoodMarketResponse,
)
from lotscope.neighborhoods.service import list_neighborhoods, neighborhood_market_stats

router = APIRouter(tags=["neighborhoods"])

_MARKET_CACHE_KEY_PREFIX = "neighborhoods:market"
_MARKET_CACHE_TTL_SECONDS = 3_600


@router.get("/neighborhoods", response_model=NeighborhoodListResponse)
async def get_neighborhoods(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NeighborhoodListResponse:
    return NeighborhoodListResponse(neighborhoods=await list_neighborhoods(session, MARKET_CODE))


@router.get("/neighborhoods/market", response_model=NeighborhoodMarketResponse)
async def get_neighborhood_market(
    session: Annotated[AsyncSession, Depends(get_session)],
    current_user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> NeighborhoodMarketResponse:

    code = MARKET_CODE
    cache_key = f"{_MARKET_CACHE_KEY_PREFIX}:{code}"
    with contextlib.suppress(RedisError):
        cached = await redis.get(cache_key)
        if cached is not None:
            return NeighborhoodMarketResponse.model_validate_json(cached)

    result = await neighborhood_market_stats(session, code)

    with contextlib.suppress(RedisError):
        await redis.set(cache_key, result.model_dump_json(), ex=_MARKET_CACHE_TTL_SECONDS)
    return result
