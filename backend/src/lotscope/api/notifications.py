"""Unsubscribe, which every email we send links to.

The path stays /digests/unsubscribe. That URL is already in packets and briefs sitting in
people's inboxes, and an unsubscribe link that 404s is worse than no link at all — so the
module moved and the route did not.
"""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.security import verify_unsubscribe_token
from lotscope.accounts.service import get_user_by_id
from lotscope.api.deps import get_app_settings, get_session
from lotscope.core.config import Settings

router = APIRouter(prefix="/digests", tags=["notifications"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]

_PAGE = (
    "<html><body style='font-family:Arial,sans-serif;max-width:520px;margin:60px auto;"
    "text-align:center;color:#1f2933;'>"
    "<h2>You're unsubscribed</h2>"
    "<p>You will no longer receive LotScope emails — briefs, packets or alerts. "
    "You can turn them back on anytime in your account settings.</p>"
    "</body></html>"
)


@router.get("/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(
    session: SessionDep,
    settings: SettingsDep,
    token: Annotated[str, Query(min_length=1)],
) -> HTMLResponse:
    user_id = verify_unsubscribe_token(settings, token)
    if user_id is not None:
        user = await get_user_by_id(session, user_id)
        if user is not None and user.digest_frequency != "off":
            user.digest_frequency = "off"
            await session.commit()
    return HTMLResponse(_PAGE)
