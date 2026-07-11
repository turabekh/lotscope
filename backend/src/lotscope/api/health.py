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

router = APIRouter(tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]
    version: str


class ReadinessResponse(BaseModel):
    status: Literal["ready", "degraded"]
    database: bool
    redis: bool


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
    status: Literal["ready", "degraded"] = "ready" if database_ok and redis_ok else "degraded"
    return ReadinessResponse(status=status, database=database_ok, redis=redis_ok)


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
