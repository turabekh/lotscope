from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import watchlist_limit
from lotscope.api.deps import get_current_user, get_session
from lotscope.watchlist.schemas import (
    SavedParcelCreate,
    SavedParcelUpdate,
    WatchlistItem,
    WatchlistResponse,
)
from lotscope.watchlist.service import (
    acknowledge,
    add_saved,
    is_saved,
    list_saved,
    remove_saved,
    update_saved,
)

router = APIRouter(prefix="/watchlist", tags=["watchlist"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=WatchlistResponse)
async def get_watchlist(session: SessionDep, user: CurrentUserDep) -> WatchlistResponse:
    items = await list_saved(session, user.id)
    return WatchlistResponse(
        limit=watchlist_limit(user.tier),
        used=len(items),
        alerts=sum(1 for item in items if item.has_alerts),
        items=items,
    )


@router.get("/{parcel_number}")
async def get_saved_state(
    parcel_number: str, session: SessionDep, user: CurrentUserDep
) -> dict[str, bool]:
    return {"saved": await is_saved(session, user.id, parcel_number)}


@router.post("", response_model=WatchlistItem, status_code=201)
async def add_to_watchlist(
    data: SavedParcelCreate, session: SessionDep, user: CurrentUserDep
) -> WatchlistItem:
    saved = await add_saved(session, user.id, data, limit=watchlist_limit(user.tier))
    await session.commit()
    return WatchlistItem(
        parcel_number=saved.parcel_number,
        address=None,
        owner=None,
        base_zoning_code=None,
        is_vacant=None,
        market_value=None,
        opportunity_score=None,
        tags=list(saved.tags),
        note=saved.note,
        created_at=saved.created_at,
    )


@router.patch("/{parcel_number}", response_model=WatchlistItem)
async def update_watchlist_item(
    parcel_number: str, data: SavedParcelUpdate, session: SessionDep, user: CurrentUserDep
) -> WatchlistItem:
    saved = await update_saved(session, user.id, parcel_number, data)
    await session.commit()
    return WatchlistItem(
        parcel_number=saved.parcel_number,
        address=None,
        owner=None,
        base_zoning_code=None,
        is_vacant=None,
        market_value=None,
        opportunity_score=None,
        tags=list(saved.tags),
        note=saved.note,
        created_at=saved.created_at,
    )


@router.post("/{parcel_number}/seen", status_code=204)
async def mark_seen(parcel_number: str, session: SessionDep, user: CurrentUserDep) -> None:
    await acknowledge(session, user.id, parcel_number)
    await session.commit()


@router.delete("/{parcel_number}", status_code=204)
async def remove_from_watchlist(
    parcel_number: str, session: SessionDep, user: CurrentUserDep
) -> None:
    await remove_saved(session, user.id, parcel_number)
    await session.commit()
