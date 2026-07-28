from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_session
from lotscope.underwriting.schemas import ProfileRead, ProfileWrite
from lotscope.underwriting.service import (
    create_profile,
    delete_profile,
    get_profile,
    list_profiles,
    update_profile,
)

router = APIRouter(prefix="/underwriting/profiles", tags=["underwriting"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=list[ProfileRead])
async def list_own_profiles(session: SessionDep, user: CurrentUserDep) -> list[ProfileRead]:
    return await list_profiles(session, user.id)


@router.post("", response_model=ProfileRead, status_code=status.HTTP_201_CREATED)
async def create_own_profile(
    data: ProfileWrite, session: SessionDep, user: CurrentUserDep
) -> ProfileRead:
    profile = await create_profile(session, user.id, data)
    await session.commit()
    return profile


@router.get("/{profile_id}", response_model=ProfileRead)
async def read_own_profile(
    profile_id: int, session: SessionDep, user: CurrentUserDep
) -> ProfileRead:
    return await get_profile(session, profile_id, user.id)


@router.put("/{profile_id}", response_model=ProfileRead)
async def update_own_profile(
    profile_id: int, data: ProfileWrite, session: SessionDep, user: CurrentUserDep
) -> ProfileRead:
    profile = await update_profile(session, profile_id, user.id, data)
    await session.commit()
    return profile


@router.delete("/{profile_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_own_profile(profile_id: int, session: SessionDep, user: CurrentUserDep) -> None:
    await delete_profile(session, profile_id, user.id)
    await session.commit()
