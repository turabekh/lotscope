from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.deps import get_session
from lotscope.neighborhoods.schemas import NeighborhoodListResponse
from lotscope.neighborhoods.service import list_neighborhoods

router = APIRouter(tags=["neighborhoods"])


@router.get("/neighborhoods", response_model=NeighborhoodListResponse)
async def get_neighborhoods(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> NeighborhoodListResponse:
    return NeighborhoodListResponse(neighborhoods=await list_neighborhoods(session))
