from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Annotated, cast

import jwt
from arq.connections import ArqRedis
from fastapi import Depends, Path, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.accounts.security import decode_access_token
from lotscope.accounts.service import get_user_by_id
from lotscope.ai.client import AnthropicGenerator, StructuredGenerator
from lotscope.ai.embeddings import Embedder, VoyageEmbedder
from lotscope.core.config import Settings
from lotscope.core.errors import AuthError, EmailUnverifiedError, ForbiddenError
from lotscope.ingestion.extract import ExtractClient
from lotscope.ingestion.loaders.sheriff_civilview import CivilViewSheriffSource
from lotscope.notifications.email import EmailSender, get_email_sender

_bearer_scheme = HTTPBearer(auto_error=False)

_MARKET_KEY_SEP = ":"
_DEFAULT_MARKET = "phl"


def canonicalize_parcel_key(parcel_number: str) -> str:
    if _MARKET_KEY_SEP in parcel_number:
        return parcel_number
    return f"{_DEFAULT_MARKET}{_MARKET_KEY_SEP}{parcel_number}"


def _resolve_parcel_key(parcel_number: Annotated[str, Path()]) -> str:
    return canonicalize_parcel_key(parcel_number)


ParcelKeyDep = Annotated[str, Depends(_resolve_parcel_key)]


def get_app_settings(request: Request) -> Settings:
    return cast(Settings, request.app.state.settings)


def get_session_factory(request: Request) -> async_sessionmaker[AsyncSession]:
    return cast("async_sessionmaker[AsyncSession]", request.app.state.session_factory)


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    factory = get_session_factory(request)
    async with factory() as session:
        yield session


def get_redis(request: Request) -> Redis:
    return cast(Redis, request.app.state.redis)


def get_arq_pool(request: Request) -> ArqRedis:
    return cast(ArqRedis, request.app.state.arq_pool)


SourceFetcher = Callable[[str], Awaitable[bytes]]


def get_source_fetcher(request: Request) -> SourceFetcher:
    settings = get_app_settings(request)

    async def _fetch(url: str) -> bytes:
        async with ExtractClient(settings) as extract:
            download = await extract.download(url)
        return download.content

    return _fetch


def get_sheriff_coverage_source(request: Request) -> CivilViewSheriffSource:
    return CivilViewSheriffSource(get_app_settings(request))


def get_embedder(request: Request) -> Embedder:
    return VoyageEmbedder(get_app_settings(request))


def get_generator(request: Request) -> StructuredGenerator:
    return AnthropicGenerator(get_app_settings(request))


def get_summary_generator(request: Request) -> StructuredGenerator:
    settings = get_app_settings(request)
    return AnthropicGenerator(settings, model=settings.anthropic_summary_model, max_tokens=512)


_VERIFICATION_EXEMPT_PREFIXES = ("/auth/", "/health", "/legal")


def _is_verification_exempt(request: Request) -> bool:
    path = request.url.path
    for prefix in _VERIFICATION_EXEMPT_PREFIXES:
        if path.startswith(prefix) or path.startswith(f"/api{prefix}"):
            return True
    return False


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User:
    if credentials is None:
        raise AuthError("Not authenticated.")
    try:
        payload = decode_access_token(settings, credentials.credentials)
    except jwt.PyJWTError as error:
        raise AuthError("Invalid or expired token.") from error
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        raise AuthError("Invalid token subject.")
    user = await get_user_by_id(session, int(subject))
    if user is None or not user.is_active:
        raise AuthError("Account not found or inactive.")
    if user.email_verified_at is None and not _is_verification_exempt(request):
        raise EmailUnverifiedError("Confirm your email address to finish setting up your account.")
    # So an unhandled 500 can say whose request it was without re-decoding the token.
    request.state.user_id = user.id
    return user


async def get_optional_user(
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_app_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer_scheme)],
) -> User | None:
    if credentials is None:
        return None
    try:
        payload = decode_access_token(settings, credentials.credentials)
    except jwt.PyJWTError:
        return None
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject.isdigit():
        return None
    user = await get_user_by_id(session, int(subject))
    if user is None or not user.is_active:
        return None
    return user


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise ForbiddenError("Administrator access is required.")
    return user


def get_email_sender_dep(
    settings: Annotated[Settings, Depends(get_app_settings)],
) -> EmailSender | None:
    return get_email_sender(settings)
