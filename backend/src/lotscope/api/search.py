from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.deps import get_session
from lotscope.search.schemas import ParcelSearchResponse
from lotscope.search.service import search_parcels

router = APIRouter(tags=["search"])


@router.get("/search", response_model=ParcelSearchResponse)
async def search(
    session: Annotated[AsyncSession, Depends(get_session)],
    q: Annotated[str, Query(min_length=1)],
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> ParcelSearchResponse:
    results = await search_parcels(session, q, limit=limit, offset=offset)
    return ParcelSearchResponse(query=q, results=results)
