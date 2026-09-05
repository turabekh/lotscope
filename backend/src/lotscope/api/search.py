from typing import Annotated

from fastapi import APIRouter, Depends, Query
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.core.market import MARKET_CODE
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
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ParcelSearchResponse:
    results = await search_parcels(session, q, market_code=MARKET_CODE, limit=limit, offset=offset)
    return ParcelSearchResponse(query=q, market=MARKET_CODE, results=results)


@router.post("/search/area", response_model=AreaSearchResponse)
async def search_within_area(
    request: AreaSearchRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> AreaSearchResponse:
    scoped = request.model_copy(update={"market": MARKET_CODE})
    results, total = await search_area(session, scoped)
    return AreaSearchResponse(
        count=len(results),
        total=total,
        truncated=total > len(results),
        results=results,
    )
