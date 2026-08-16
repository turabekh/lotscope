from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.deps import get_redis, get_session
from lotscope.core.config import Settings, get_settings
from lotscope.ops.service import stale_automated_datasets

router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    database: bool
    redis: bool
    ingestion: bool
    stale_datasets: list[str] = []


@router.get("/health", response_model=LivenessResponse)
async def liveness(
    settings: Annotated[Settings, Depends(get_settings)],
) -> LivenessResponse:
    return LivenessResponse(status="ok", version=settings.git_sha)


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(
    session: Annotated[AsyncSession, Depends(get_session)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> ReadinessResponse:
    database_ok = await _check_database(session)
    redis_ok = await _check_redis(redis)
    stale = await _stale_datasets(session) if database_ok else []
    ingestion_ok = not stale
    healthy = database_ok and redis_ok and ingestion_ok
    status: Literal["ready", "degraded"] = "ready" if healthy else "degraded"
    return ReadinessResponse(
        status=status,
        database=database_ok,
        redis=redis_ok,
        ingestion=ingestion_ok,
        stale_datasets=stale,
    )


_UNCHECKABLE = "ingestion freshness could not be read, so staleness is unknown"


async def _stale_datasets(session: AsyncSession) -> list[str]:
    try:
        stale = await stale_automated_datasets(session)
    except SQLAlchemyError:
        return [_UNCHECKABLE]
    return [f"{item.market_code}/{item.dataset}: {item.reason}" for item in stale]


async def _check_database(session: AsyncSession) -> bool:
    try:
        await session.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return False
    return True


async def _check_redis(redis: Redis) -> bool:
    try:
        return bool(await redis.ping())
    except RedisError:
        return False
