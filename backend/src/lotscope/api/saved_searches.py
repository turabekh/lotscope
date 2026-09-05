from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_session
from lotscope.savedsearch.schemas import (
    SavedSearchCreate,
    SavedSearchDetail,
    SavedSearchListResponse,
    SavedSearchUpdate,
)
from lotscope.savedsearch.service import (
    create_search,
    delete_search,
    get_search,
    list_searches,
    refresh_search,
    update_search,
)

router = APIRouter(prefix="/saved-searches", tags=["saved-searches"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=SavedSearchListResponse)
async def get_saved_searches(session: SessionDep, user: CurrentUserDep) -> SavedSearchListResponse:
    searches = await list_searches(session, user.id)
    return SavedSearchListResponse(
        limit=None,
        used=len(searches),
        searches=searches,
    )


@router.post("", response_model=SavedSearchDetail, status_code=201)
async def create_saved_search(
    data: SavedSearchCreate, session: SessionDep, user: CurrentUserDep
) -> SavedSearchDetail:
    search = await create_search(session, user.id, data, limit=None)
    detail = await get_search(session, user.id, search.id)
    await session.commit()
    return detail


@router.get("/{search_id}", response_model=SavedSearchDetail)
async def get_saved_search(
    search_id: int, session: SessionDep, user: CurrentUserDep
) -> SavedSearchDetail:
    return await get_search(session, user.id, search_id)


@router.patch("/{search_id}", response_model=SavedSearchDetail)
async def update_saved_search(
    search_id: int, data: SavedSearchUpdate, session: SessionDep, user: CurrentUserDep
) -> SavedSearchDetail:
    await update_search(session, user.id, search_id, data)
    detail = await get_search(session, user.id, search_id)
    await session.commit()
    return detail


@router.post("/{search_id}/run", response_model=SavedSearchDetail)
async def run_saved_search(
    search_id: int, session: SessionDep, user: CurrentUserDep
) -> SavedSearchDetail:
    detail = await refresh_search(session, user.id, search_id)
    await session.commit()
    return detail


@router.delete("/{search_id}", status_code=204)
async def delete_saved_search(search_id: int, session: SessionDep, user: CurrentUserDep) -> None:
    await delete_search(session, user.id, search_id)
    await session.commit()
