from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import LoginRequest, TokenResponse, UserCreate, UserRead
from lotscope.accounts.security import create_access_token
from lotscope.accounts.service import authenticate_user, register_user
from lotscope.api.deps import get_app_settings, get_current_user, get_session
from lotscope.core.config import Settings

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


@router.post("/register", response_model=UserRead, status_code=201)
async def register(data: UserCreate, session: SessionDep) -> UserRead:
    user = await register_user(session, data)
    await session.commit()
    return UserRead.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(data: LoginRequest, session: SessionDep, settings: SettingsDep) -> TokenResponse:
    user = await authenticate_user(session, data.email, data.password)
    token = create_access_token(settings, subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return UserRead.model_validate(user)
