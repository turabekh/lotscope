from typing import Annotated

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_session
from lotscope.core.markets import market_code
from lotscope.underwriting.schemas import BuyBoxMatches, ProfileRead, ProfileWrite
from lotscope.underwriting.service import (
    create_profile,
    delete_profile,
    find_buy_box_matches,
    get_profile,
    list_profiles,
    update_profile,
)

router = APIRouter(prefix="/underwriting", tags=["underwriting"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/profiles", response_model=list[ProfileRead])
async def list_own_profiles(session: SessionDep, user: CurrentUserDep) -> list[ProfileRead]:
    return await list_profiles(session, user.id)


@router.post("/profiles", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
async def create_own_profile(
    data: ProfileWrite, session: SessionDep, user: CurrentUserDep
) -> ProfileRead:
    profile = await create_profile(session, user.id, data)
    await session.commit()
    return profile


@router.get("/profiles/{profile_id}", response_model=ProfileRead)
async def read_own_profile(
    profile_id: int, session: SessionDep, user: CurrentUserDep
) -> ProfileRead:
    return await get_profile(session, profile_id, user.id)


@router.put("/profiles/{profile_id}", response_model=ProfileRead)
async def update_own_profile(
    profile_id: int, data: ProfileWrite, session: SessionDep, user: CurrentUserDep
) -> ProfileRead:
    profile = await update_profile(session, profile_id, user.id, data)
    await session.commit()
    return profile


@router.delete("/profiles/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_own_profile(profile_id: int, session: SessionDep, user: CurrentUserDep) -> None:
    await delete_profile(session, profile_id, user.id)
    await session.commit()


@router.get("/matches", response_model=BuyBoxMatches)
async def read_buy_box_matches(
    session: SessionDep,
    user: CurrentUserDep,
    market: Annotated[str, Query(max_length=40)] = "philadelphia",
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BuyBoxMatches:
    return await find_buy_box_matches(session, user.id, market=market_code(market), limit=limit)
