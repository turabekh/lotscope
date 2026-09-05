from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_redis, get_session
from lotscope.api.exports import EXPORT_ROW_LIMIT
from lotscope.core.errors import NotFoundError
from lotscope.outreach.schemas import MailMergeRequest, WatchlistMailRequest
from lotscope.outreach.service import (
    render_letter_campaign,
    render_saved_search_campaign,
    render_watchlist_campaign,
)
from lotscope.reports.mailer import letters_filename

router = APIRouter(prefix="/outreach", tags=["outreach"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
RedisDep = Annotated[Redis, Depends(get_redis)]


@router.post("/letters")
async def outreach_letters(
    request: MailMergeRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> Response:
    pdf = await render_letter_campaign(session, request, row_limit=EXPORT_ROW_LIMIT)
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
    pdf = await render_watchlist_campaign(session, current_user.id, request)
    if pdf is None:
        raise NotFoundError("No mailable owners on your watchlist yet.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{letters_filename()}"'},
    )


@router.post("/letters/saved-search/{search_id}")
async def outreach_saved_search_letters(
    search_id: int,
    request: WatchlistMailRequest,
    session: SessionDep,
    current_user: CurrentUserDep,
    redis: RedisDep,
) -> Response:
    pdf = await render_saved_search_campaign(
        session,
        current_user.id,
        search_id,
        request,
        row_limit=EXPORT_ROW_LIMIT,
    )
    if pdf is None:
        raise NotFoundError("No mailable owners matched this saved search.")
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{letters_filename()}"'},
    )
