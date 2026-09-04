from datetime import UTC, datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.ai.derivation import PHILLYCODE_SOURCE
from lotscope.api.deps import get_redis, get_session
from lotscope.core.config import Settings, get_settings
from lotscope.corpus.service import (
    EXPECTED_TITLES,
    MINIMUM_DOCUMENTS,
    MINIMUM_REPRESENTED_PCT,
    corpus_health,
)
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


class CorpusTitleCoverage(BaseModel):
    title_number: str
    provisions: int
    represented: int
    documents: int
    embedded: int
    coverage_pct: float
    represented_pct: float


class CorpusHealthResponse(BaseModel):
    status: Literal["ok", "incomplete"]
    source: str
    titles: list[CorpusTitleCoverage]
    total_provisions: int
    total_represented: int
    total_documents: int
    total_embedded: int
    coverage_pct: float
    represented_pct: float
    expected_titles: int
    minimum_documents: int
    minimum_represented_pct: float
    failures: list[str]
    last_loaded_at: datetime | None
    computed_at: datetime


@router.get("/health/corpus", response_model=CorpusHealthResponse)
async def corpus_liveness(
    session: Annotated[AsyncSession, Depends(get_session)],
) -> JSONResponse:
    health = await corpus_health(session)
    body = CorpusHealthResponse(
        status="ok" if health.healthy else "incomplete",
        source=PHILLYCODE_SOURCE,
        titles=[
            CorpusTitleCoverage(
                title_number=title.title_number,
                provisions=title.provisions,
                represented=title.represented,
                documents=title.documents,
                embedded=title.embedded,
                coverage_pct=round(title.coverage_pct, 2),
                represented_pct=round(title.represented_pct, 2),
            )
            for title in health.titles
        ],
        total_provisions=health.total_provisions,
        total_represented=health.total_represented,
        total_documents=health.total_documents,
        total_embedded=health.total_embedded,
        coverage_pct=round(health.coverage_pct, 2),
        represented_pct=round(health.represented_pct, 2),
        expected_titles=EXPECTED_TITLES,
        minimum_documents=MINIMUM_DOCUMENTS,
        minimum_represented_pct=MINIMUM_REPRESENTED_PCT,
        failures=health.failures,
        last_loaded_at=health.last_loaded_at,
        computed_at=datetime.now(UTC),
    )
    return JSONResponse(
        status_code=200 if health.healthy else 503,
        content=jsonable_encoder(body),
    )


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
