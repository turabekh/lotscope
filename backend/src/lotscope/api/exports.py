from collections.abc import Iterable, Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import buyer_intel_access, export_monthly_limit, export_row_limit
from lotscope.accounts.usage import reserve_export
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.buyers.service import BUYERS_EXPORT_HEADER, export_buyers
from lotscope.core.errors import QuotaExceededError
from lotscope.core.markets import market_code
from lotscope.distress.service import LEADS_EXPORT_HEADER, export_leads
from lotscope.markets.capabilities import hidden_surfaces
from lotscope.pipeline.service import PIPELINE_EXPORT_HEADER, export_deals
from lotscope.reports.csv_export import EXPORT_DISCLAIMER, stream_csv
from lotscope.savedsearch.service import SAVED_SEARCH_EXPORT_HEADER, export_search_matches

router = APIRouter(tags=["exports"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]


async def _reserve_export(redis: Redis, user: User) -> None:
    monthly_limit = export_monthly_limit(user.tier)
    if monthly_limit is not None and monthly_limit <= 0:
        raise QuotaExceededError("Exports are a paid feature — upgrade to export leads and lists.")
    try:
        allowed = await reserve_export(redis, user.id, monthly_limit)
    except RedisError:
        allowed = True
    if not allowed:
        raise QuotaExceededError("Monthly export limit reached — upgrade for more exports.")


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
    await _reserve_export(redis, current_user)
    rows = await export_leads(
        session,
        row_limit=export_row_limit(current_user.tier),
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
    market: Annotated[str, Query(max_length=20)] = "phl",
    min_purchases: Annotated[int, Query(ge=1, le=100)] = 3,
) -> StreamingResponse:
    if not buyer_intel_access(current_user.tier):
        raise QuotaExceededError(
            "Cash-buyer exports are an Investor-tier feature — upgrade to export the buyer list."
        )
    await _reserve_export(redis, current_user)
    code = market_code(market)
    rows: list[Any] = []
    if "buyers" not in hidden_surfaces(code):
        rows = await export_buyers(
            session,
            code,
            min_purchases=min_purchases,
            row_limit=export_row_limit(current_user.tier),
        )
    return _csv_response(BUYERS_EXPORT_HEADER, rows, f"lotscope-buyers-{code}.csv")


@router.get("/pipeline/export")
async def export_pipeline_csv(
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> StreamingResponse:
    await _reserve_export(redis, current_user)
    rows = await export_deals(
        session, current_user.id, row_limit=export_row_limit(current_user.tier)
    )
    return _csv_response(PIPELINE_EXPORT_HEADER, rows, "lotscope-pipeline.csv")


@router.get("/saved-searches/{search_id}/export")
async def export_saved_search_csv(
    search_id: int,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> StreamingResponse:
    rows = await export_search_matches(
        session, current_user.id, search_id, row_limit=export_row_limit(current_user.tier)
    )
    await _reserve_export(redis, current_user)
    return _csv_response(SAVED_SEARCH_EXPORT_HEADER, rows, f"lotscope-search-{search_id}.csv")
