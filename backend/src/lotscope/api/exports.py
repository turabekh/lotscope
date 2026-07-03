from collections.abc import Iterable, Sequence
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import export_monthly_limit, export_row_limit
from lotscope.accounts.usage import reserve_export
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.core.errors import QuotaExceededError
from lotscope.distress.service import LEADS_EXPORT_HEADER, export_leads
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
