from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import pipeline_limit
from lotscope.api.deps import ParcelKeyDep, canonicalize_parcel_key, get_current_user, get_session
from lotscope.core.errors import NotFoundError
from lotscope.pipeline.schemas import (
    DealActivityItem,
    DealCreate,
    DealItem,
    DealUpdate,
    PipelineResponse,
    TodayResponse,
)
from lotscope.pipeline.service import (
    add_deal,
    deals_due,
    get_deal,
    list_activity,
    list_deals,
    remove_deal,
    update_deal,
)

router = APIRouter(prefix="/pipeline", tags=["pipeline"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=PipelineResponse)
async def get_pipeline(session: SessionDep, user: CurrentUserDep) -> PipelineResponse:
    deals = await list_deals(session, user.id)
    return PipelineResponse(limit=pipeline_limit(user.tier), used=len(deals), deals=deals)


@router.get("/today", response_model=TodayResponse)
async def get_pipeline_today(session: SessionDep, user: CurrentUserDep) -> TodayResponse:
    today = datetime.now(UTC).date()
    return TodayResponse(deals=await deals_due(session, user.id, today))


@router.get("/{parcel_number}/activity", response_model=list[DealActivityItem])
async def get_pipeline_activity(
    parcel_number: ParcelKeyDep, session: SessionDep, user: CurrentUserDep
) -> list[DealActivityItem]:
    return await list_activity(session, user.id, parcel_number)


@router.get("/{parcel_number}", response_model=DealItem)
async def get_pipeline_deal(
    parcel_number: ParcelKeyDep, session: SessionDep, user: CurrentUserDep
) -> DealItem:
    deal = await get_deal(session, user.id, parcel_number)
    if deal is None:
        raise NotFoundError(f"Parcel {parcel_number} is not in your pipeline.")
    return deal


@router.post("", response_model=DealItem, status_code=201)
async def add_to_pipeline(data: DealCreate, session: SessionDep, user: CurrentUserDep) -> DealItem:
    data = data.model_copy(update={"parcel_number": canonicalize_parcel_key(data.parcel_number)})
    await add_deal(session, user.id, data, limit=pipeline_limit(user.tier))
    await session.commit()
    deal = await get_deal(session, user.id, data.parcel_number)
    assert deal is not None
    return deal


@router.patch("/{parcel_number}", response_model=DealItem)
async def update_pipeline_deal(
    parcel_number: ParcelKeyDep, data: DealUpdate, session: SessionDep, user: CurrentUserDep
) -> DealItem:
    await update_deal(session, user.id, parcel_number, data)
    await session.commit()
    deal = await get_deal(session, user.id, parcel_number)
    assert deal is not None
    return deal


@router.delete("/{parcel_number}", status_code=204)
async def remove_from_pipeline(
    parcel_number: ParcelKeyDep, session: SessionDep, user: CurrentUserDep
) -> None:
    await remove_deal(session, user.id, parcel_number)
    await session.commit()
