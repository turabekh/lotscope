from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import feed_access
from lotscope.api.deps import get_current_user, get_session
from lotscope.core.errors import QuotaExceededError
from lotscope.feed.schemas import FeedResponse
from lotscope.feed.service import get_feed
from lotscope.savedsearch.schemas import SearchCriteria
from lotscope.savedsearch.service import criteria_for

router = APIRouter(prefix="/feed", tags=["feed"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]

_MAX_LOOKBACK_DAYS = 30
_DEFAULT_LOOKBACK_DAYS = 1


@router.get("", response_model=FeedResponse)
async def feed(
    session: SessionDep,
    current_user: CurrentUserDep,
    days: Annotated[int, Query(ge=1, le=_MAX_LOOKBACK_DAYS)] = _DEFAULT_LOOKBACK_DAYS,
    saved_search_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> FeedResponse:
    if not feed_access(current_user.tier):
        raise QuotaExceededError(
            "The Deal Feed is a Pro feature — upgrade to see citywide changes."
        )
    since = datetime.now(UTC) - timedelta(days=days)
    criteria = (
        await criteria_for(session, current_user.id, saved_search_id)
        if saved_search_id is not None
        else SearchCriteria()
    )
    return await get_feed(session, criteria=criteria, since=since, limit=limit)
