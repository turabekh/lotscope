from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from redis.asyncio import Redis
from redis.exceptions import RedisError
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import export_monthly_limit, export_row_limit
from lotscope.accounts.usage import reserve_export
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.outreach.schemas import MailMergeRequest, WatchlistMailRequest
from lotscope.outreach.service import render_letter_campaign, render_watchlist_campaign
from lotscope.reports.mailer import letters_filename

router = APIRouter(prefix="/outreach", tags=["outreach"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]


async def _reserve(redis: Redis, user: User) -> None:
    monthly_limit = export_monthly_limit(user.tier)
    if monthly_limit is not None and monthly_limit <= 0:
        raise QuotaExceededError(
            "Outreach mailers are a paid feature — upgrade to generate direct-mail letters."
        )
    try:
        allowed = await reserve_export(redis, user.id, monthly_limit)
    except RedisError:
        allowed = True
    if not allowed:
        raise QuotaExceededError("Monthly export limit reached — upgrade for more outreach.")


@router.post("/letters")
async def outreach_letters(
    request: MailMergeRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> Response:
    await _reserve(redis, current_user)
    pdf = await render_letter_campaign(
        session, request, row_limit=export_row_limit(current_user.tier)
    )
    if pdf is None:
        raise NotFoundError("No mailable leads matched these filters.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{letters_filename()}"'},
    )


@router.post("/letters/watchlist")
async def outreach_watchlist_letters(
    request: WatchlistMailRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> Response:
    await _reserve(redis, current_user)
    pdf = await render_watchlist_campaign(session, current_user.id, request)
    if pdf is None:
        raise NotFoundError("No mailable owners on your watchlist yet.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{letters_filename()}"'},
    )
