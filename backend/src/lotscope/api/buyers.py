from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import buyer_intel_access
from lotscope.api.deps import get_current_user, get_session
from lotscope.buyers.schemas import BuyerProfileDetail, BuyerRoster, BuyersNearby
from lotscope.buyers.service import (
    buyers_near_parcel,
    get_buyer,
    list_buyers,
    parcel_market,
)
from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.core.market import MARKET_CODE

router = APIRouter(tags=["buyers"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]

_INVESTOR_UPGRADE = (
    "Cash-buyer intelligence is an Investor-tier feature — upgrade to see who is buying lots "
    "near your parcels."
)


def _require_investor(user: User) -> None:
    if not buyer_intel_access(user.tier):
        raise QuotaExceededError(_INVESTOR_UPGRADE)


@router.get("/parcels/{parcel_number}/buyers", response_model=BuyersNearby)
async def parcel_buyers(
    parcel_number: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
) -> BuyersNearby:
    _require_investor(current_user)
    market_code = await parcel_market(session, parcel_number)
    if market_code is None:
        raise NotFoundError(f"Parcel {parcel_number!r} was not found.")
    return await buyers_near_parcel(session, parcel_number, market_code, limit=limit)


@router.get("/buyers", response_model=BuyerRoster)
async def buyers_roster(
    session: SessionDep,
    current_user: CurrentUserDep,
    min_purchases: Annotated[int, Query(ge=1, le=100)] = 3,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BuyerRoster:
    _require_investor(current_user)
    code = MARKET_CODE
    return await list_buyers(session, code, min_purchases=min_purchases, limit=limit, offset=offset)


@router.get("/buyers/{buyer_key}", response_model=BuyerProfileDetail)
async def buyer_profile(
    buyer_key: str,
    session: SessionDep,
    current_user: CurrentUserDep,
) -> BuyerProfileDetail:
    _require_investor(current_user)
    code = MARKET_CODE
    profile = await get_buyer(session, code, buyer_key)
    if profile is None:
        raise NotFoundError(f"Buyer {buyer_key!r} was not found in {code!r}.")
    return profile
