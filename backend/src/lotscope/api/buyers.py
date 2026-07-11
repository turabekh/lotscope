from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import buyer_intel_access
from lotscope.api.deps import get_current_user, get_session
from lotscope.buyers.schemas import BuyerProfileDetail, BuyerRoster, BuyersNearby
from lotscope.buyers.service import (
    BUYER_NEAR_RADIUS_FT,
    buyers_near_parcel,
    get_buyer,
    list_buyers,
    parcel_market,
)
from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.markets.capabilities import hidden_surfaces

router = APIRouter(tags=["buyers"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]

_BUYER_NAMES_SURFACE = "buyer_names"
_INVESTOR_UPGRADE = (
    "Cash-buyer intelligence is an Investor-tier feature — upgrade to see who is buying lots "
    "near your parcels."
)
_GATED_NOTE = "Buyer identities are not available for this market."


def _require_investor(user: User) -> None:
    if not buyer_intel_access(user.tier):
        raise QuotaExceededError(_INVESTOR_UPGRADE)


def _names_gated(market_code: str) -> bool:
    return _BUYER_NAMES_SURFACE in hidden_surfaces(market_code)


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
    if _names_gated(market_code):
        return BuyersNearby(
            market_code=market_code,
            available=False,
            note=_GATED_NOTE,
            radius_ft=BUYER_NEAR_RADIUS_FT,
            buyers=[],
        )
    return await buyers_near_parcel(session, parcel_number, market_code, limit=limit)


@router.get("/buyers", response_model=BuyerRoster)
async def buyers_roster(
    session: SessionDep,
    current_user: CurrentUserDep,
    market: Annotated[str, Query(max_length=10)] = "phl",
    min_purchases: Annotated[int, Query(ge=1, le=100)] = 3,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> BuyerRoster:
    _require_investor(current_user)
    if _names_gated(market):
        return BuyerRoster(
            market_code=market, available=False, note=_GATED_NOTE, total=0, returned=0, buyers=[]
        )
    return await list_buyers(
        session, market, min_purchases=min_purchases, limit=limit, offset=offset
    )


@router.get("/buyers/{buyer_key}", response_model=BuyerProfileDetail)
async def buyer_profile(
    buyer_key: str,
    session: SessionDep,
    current_user: CurrentUserDep,
    market: Annotated[str, Query(max_length=10)] = "phl",
) -> BuyerProfileDetail:
    _require_investor(current_user)
    if _names_gated(market):
        raise NotFoundError("Buyer identities are not available for this market.")
    profile = await get_buyer(session, market, buyer_key)
    if profile is None:
        raise NotFoundError(f"Buyer {buyer_key!r} was not found in {market!r}.")
    return profile
