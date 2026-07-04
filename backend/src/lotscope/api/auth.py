import contextlib
from typing import Annotated

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import (
    DigestPreference,
    LoginRequest,
    TokenResponse,
    UsageMetric,
    UsageResponse,
    UserCreate,
    UserRead,
)
from lotscope.accounts.security import create_access_token
from lotscope.accounts.service import authenticate_user, register_user
from lotscope.accounts.tiers import ask_daily_limit, parcel_view_daily_limit
from lotscope.accounts.usage import get_ask_usage, get_parcel_views
from lotscope.api.deps import get_app_settings, get_current_user, get_redis, get_session
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


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    user: Annotated[User, Depends(get_current_user)], settings: SettingsDep
) -> TokenResponse:
    token = create_access_token(settings, subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token)


@router.get("/me", response_model=UserRead)
async def me(user: Annotated[User, Depends(get_current_user)]) -> UserRead:
    return UserRead.model_validate(user)


@router.patch("/digest", response_model=UserRead)
async def set_digest_preference(
    data: DigestPreference,
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    user.digest_frequency = data.frequency
    await session.commit()
    return UserRead.model_validate(user)


def _metric(limit: int | None, used: int) -> UsageMetric:
    remaining = None if limit is None else max(0, limit - used)
    return UsageMetric(limit=limit, used=used, remaining=remaining)


@router.get("/usage", response_model=UsageResponse)
async def usage(
    user: Annotated[User, Depends(get_current_user)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> UsageResponse:
    ask_used = 0
    views_used = 0
    with contextlib.suppress(RedisError):
        ask_used = await get_ask_usage(redis, user.id)
        views_used = await get_parcel_views(redis, user.id)
    return UsageResponse(
        tier=user.tier,
        ask=_metric(ask_daily_limit(user.tier), ask_used),
        parcel_views=_metric(parcel_view_daily_limit(user.tier), views_used),
    )
