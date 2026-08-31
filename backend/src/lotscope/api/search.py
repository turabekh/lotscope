from typing import Annotated

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import area_search_daily_parcel_limit
from lotscope.accounts.usage import register_area_search_parcels
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.core.errors import QuotaExceededError
from lotscope.core.markets import DEFAULT_MARKET, Market, market_code
from lotscope.search.schemas import (
    AreaSearchRequest,
    AreaSearchResponse,
    ParcelSearchResponse,
)
from lotscope.search.service import search_parcels
from lotscope.search.spatial import search_area

router = APIRouter(tags=["search"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]


@router.get("/search", response_model=ParcelSearchResponse)
async def search(
    session: SessionDep,
    current_user: CurrentUserDep,
    q: Annotated[str, Query(min_length=1)],
    market: Annotated[Market, Query()] = DEFAULT_MARKET,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ParcelSearchResponse:
    results = await search_parcels(
        session, q, market_code=market_code(market), limit=limit, offset=offset
    )
    return ParcelSearchResponse(query=q, market=market, results=results)


@router.post("/search/area", response_model=AreaSearchResponse)
async def search_within_area(
    request: AreaSearchRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> AreaSearchResponse:
    scoped = request.model_copy(update={"market": market_code(request.market)})
    results, total = await search_area(session, scoped)
    within_quota = await register_area_search_parcels(
        redis,
        current_user.id,
        [result.parcel_number for result in results],
        area_search_daily_parcel_limit(current_user.tier),
    )
    if not within_quota:
        raise QuotaExceededError(
            "You have reached today's limit for parcels returned by area search. "
            "The limit resets tomorrow, and higher tiers raise it."
        )
    return AreaSearchResponse(
        count=len(results),
        total=total,
        truncated=total > len(results),
        results=results,
    )
