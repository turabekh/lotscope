from collections.abc import AsyncIterator
from typing import cast

from fastapi import Request
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lotscope.ai.client import AnthropicGenerator, StructuredGenerator
from lotscope.ai.embeddings import Embedder, VoyageEmbedder
from lotscope.core.config import Settings


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
