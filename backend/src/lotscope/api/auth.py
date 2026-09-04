import contextlib
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.schemas import (
    _EMAIL_PATTERN,
    DigestPreference,
    LoginRequest,
    SignerProfile,
    TokenResponse,
    UsageMetric,
    UsageResponse,
    UserCreate,
    UserRead,
)
from lotscope.accounts.security import (
    create_access_token,
    create_email_verification_token,
    verify_email_verification_token,
)
from lotscope.accounts.service import (
    authenticate_user,
    get_user_by_email,
    register_user,
    rotate_verification_nonce,
    verify_email,
)
from lotscope.accounts.tiers import ask_daily_limit, parcel_view_daily_limit
from lotscope.accounts.usage import claim_resend_slot, get_ask_usage, get_parcel_views
from lotscope.api.deps import (
    get_app_settings,
    get_current_user,
    get_email_sender_dep,
    get_redis,
    get_session,
)
from lotscope.core.config import Settings
from lotscope.core.errors import QuotaExceededError, ValidationError
from lotscope.core.logging import get_logger
from lotscope.notifications.email import EmailSender
from lotscope.notifications.verification import send_verification_email

_logger = get_logger("api.auth")

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


class VerificationRequest(BaseModel):
    token: str


class ResendRequest(BaseModel):
    email: str = Field(pattern=_EMAIL_PATTERN, max_length=255)


class VerificationPending(BaseModel):
    email: str
    verification_required: bool = True
    detail: str = "Check your email for a confirmation link."


async def _send_verification(
    settings: Settings, sender: EmailSender | None, *, user_id: int, email: str, nonce: str
) -> None:
    if sender is None:
        _logger.warning("verification_email_not_sent_no_transport", user_id=user_id)
        return
    token = create_email_verification_token(settings, user_id=user_id, nonce=nonce)
    with contextlib.suppress(Exception):
        await send_verification_email(sender, settings, to=email, token=token)


@router.post("/register", response_model=VerificationPending, status_code=202)
async def register(
    data: UserCreate,
    session: SessionDep,
    settings: SettingsDep,
    sender: Annotated[EmailSender | None, Depends(get_email_sender_dep)],
) -> VerificationPending:
    user = await register_user(session, data)
    await session.commit()
    await _send_verification(
        settings,
        sender,
        user_id=user.id,
        email=user.email,
        nonce=user.email_verification_nonce or "",
    )
    return VerificationPending(email=user.email)


@router.post("/verify", response_model=TokenResponse)
async def verify(
    data: VerificationRequest, session: SessionDep, settings: SettingsDep
) -> TokenResponse:
    decoded = verify_email_verification_token(settings, data.token)
    if decoded is None:
        raise ValidationError("This verification link is invalid or has expired.")
    user_id, nonce = decoded
    user = await verify_email(session, user_id, nonce)
    await session.commit()
    return TokenResponse(
        access_token=create_access_token(settings, subject=str(user.id), role=user.role)
    )


@router.post("/resend-verification", response_model=VerificationPending, status_code=202)
async def resend_verification(
    data: ResendRequest,
    session: SessionDep,
    settings: SettingsDep,
    redis: Annotated[Redis, Depends(get_redis)],
    sender: Annotated[EmailSender | None, Depends(get_email_sender_dep)],
) -> VerificationPending:
    email = data.email.lower()
    if not await claim_resend_slot(redis, email):
        raise QuotaExceededError(
            "Too many verification emails for this address. Try again within the hour."
        )
    user = await get_user_by_email(session, email)
    if user is not None and user.email_verified_at is None:
        nonce = await rotate_verification_nonce(session, user)
        await session.commit()
        await _send_verification(settings, sender, user_id=user.id, email=user.email, nonce=nonce)
    return VerificationPending(email=email)


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


@router.patch("/signer", response_model=UserRead)
async def set_signer_profile(
    data: SignerProfile,
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    user.entity_name = data.entity_name
    user.signer_name = data.signer_name
    user.signer_phone = data.signer_phone
    user.signer_email = data.signer_email
    await session.commit()
    return UserRead.model_validate(user)


@router.post("/onboarded", response_model=UserRead)
async def mark_onboarded(
    session: SessionDep,
    user: Annotated[User, Depends(get_current_user)],
) -> UserRead:
    if user.onboarded_at is None:
        user.onboarded_at = datetime.now(UTC)
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
