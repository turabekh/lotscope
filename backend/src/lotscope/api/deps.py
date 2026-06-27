from collections.abc import AsyncIterator
from typing import Annotated, cast

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.accounts.models import User
from lotscope.accounts.security import decode_access_token
from lotscope.accounts.service import get_user_by_id
from lotscope.ai.client import AnthropicGenerator, StructuredGenerator
from lotscope.ai.embeddings import Embedder, VoyageEmbedder
from lotscope.core.config import Settings
from lotscope.core.errors import AuthError, ForbiddenError

_bearer_scheme = HTTPBearer(auto_error=False)


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


def get_embedder(request: Request) -> Embedder:
    return VoyageEmbedder(get_app_settings(request))


def get_generator(request: Request) -> StructuredGenerator:
    return AnthropicGenerator(get_app_settings(request))


async def get_current_user(
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
    return user


async def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role != "admin":
        raise ForbiddenError("Administrator access is required.")
    return user
