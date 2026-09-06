from collections.abc import Iterable, Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.buyers.service import BUYERS_EXPORT_HEADER, export_buyers
from lotscope.core.market import MARKET_CODE
from lotscope.distress.service import LEADS_EXPORT_HEADER, export_leads
from lotscope.pipeline.service import PIPELINE_EXPORT_HEADER, export_deals
from lotscope.reports.csv_export import EXPORT_DISCLAIMER, stream_csv

EXPORT_ROW_LIMIT = 10_000
# The pipeline export computes every figure it prints, so its ceiling is what a request
# can carry rather than what a file can hold.
PIPELINE_EXPORT_ROW_LIMIT = 2_000

router = APIRouter(tags=["exports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]


def _csv_response(
    header: Sequence[str], rows: Iterable[Sequence[Any]], filename: str
) -> StreamingResponse:
    return StreamingResponse(
        stream_csv(header, rows, EXPORT_DISCLAIMER),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/leads/export")
async def export_leads_csv(
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
    min_score: Annotated[int, Query(ge=1, le=100)] = 30,
    vacant_only: bool = False,
    zip_code: Annotated[str | None, Query(max_length=10)] = None,
) -> StreamingResponse:
    rows = await export_leads(
        session,
        row_limit=EXPORT_ROW_LIMIT,
        min_score=min_score,
        vacant_only=vacant_only,
        zip_code=zip_code,
    )
    return _csv_response(LEADS_EXPORT_HEADER, rows, "lotscope-leads.csv")


@router.get("/buyers/export")
async def export_buyers_csv(
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
    min_purchases: Annotated[int, Query(ge=1, le=100)] = 3,
) -> StreamingResponse:
    code = MARKET_CODE
    rows: list[Any] = await export_buyers(
        session,
        code,
        min_purchases=min_purchases,
        row_limit=EXPORT_ROW_LIMIT,
    )
    return _csv_response(BUYERS_EXPORT_HEADER, rows, f"lotscope-buyers-{code}.csv")


@router.get("/pipeline/export")
async def export_pipeline_csv(
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> StreamingResponse:
    rows = await export_deals(
        session, current_user.id, row_limit=PIPELINE_EXPORT_ROW_LIMIT, redis=redis
    )
    return _csv_response(PIPELINE_EXPORT_HEADER, rows, "lotscope-pipeline.csv")
