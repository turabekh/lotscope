from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.security import create_calendar_token, verify_calendar_token
from lotscope.accounts.tiers import sheriff_calendar_access
from lotscope.api.deps import get_app_settings, get_current_user, get_session
from lotscope.core.config import Settings
from lotscope.core.errors import NotFoundError, QuotaExceededError
from lotscope.core.markets import market_code
from lotscope.risk.schemas import RepositoryList, SheriffSaleCalendar
from lotscope.risk.service import (
    list_repository,
    list_sheriff_sales,
    sheriff_sale_ics,
)

router = APIRouter(prefix="/sheriff-sales", tags=["sheriff-sales"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


class CalendarSubscription(BaseModel):
    url: str


def _ics_response(calendar: SheriffSaleCalendar, market: str) -> Response:
    body = sheriff_sale_ics(calendar, now=datetime.now(UTC))
    return Response(
        content=body,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{market}-sales.ics"'},
    )


@router.get("", response_model=SheriffSaleCalendar)
async def sheriff_sales(
    session: SessionDep,
    current_user: CurrentUserDep,
    market: Annotated[str, Query()] = "phl",
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    zip_code: Annotated[str | None, Query(alias="zip")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> SheriffSaleCalendar:
    if not sheriff_calendar_access(current_user.tier):
        raise QuotaExceededError(
            "The Sheriff-sale calendar is a Pro feature — upgrade to see upcoming auctions."
        )
    return await list_sheriff_sales(
        session,
        market_code=market_code(market),
        date_from=date_from,
        date_to=date_to,
        zip_code=zip_code,
        limit=limit,
    )


@router.get("/calendar.ics")
async def sheriff_sales_ics(
    session: SessionDep,
    current_user: CurrentUserDep,
    market: Annotated[str, Query()] = "phl",
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> Response:
    if not sheriff_calendar_access(current_user.tier):
        raise QuotaExceededError(
            "The Sheriff-sale calendar is a Pro feature — upgrade to see upcoming auctions."
        )
    calendar = await list_sheriff_sales(session, market_code=market_code(market), limit=limit)
    return _ics_response(calendar, market_code(market))


@router.get("/calendar/subscribe", response_model=CalendarSubscription)
async def sheriff_sales_subscribe(
    current_user: CurrentUserDep,
    settings: SettingsDep,
    market: Annotated[str, Query()] = "phl",
) -> CalendarSubscription:
    if not sheriff_calendar_access(current_user.tier):
        raise QuotaExceededError(
            "The Sheriff-sale calendar is a Pro feature — upgrade to subscribe."
        )
    token = create_calendar_token(settings, user_id=current_user.id)
    base = settings.api_base_url.rstrip("/")
    return CalendarSubscription(
        url=f"{base}/sheriff-sales/calendar/{token}.ics?market={market_code(market)}"
    )


@router.get("/calendar/{token}.ics")
async def sheriff_sales_ics_by_token(
    session: SessionDep,
    settings: SettingsDep,
    token: str,
    market: Annotated[str, Query()] = "phl",
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> Response:
    user_id = verify_calendar_token(settings, token)
    if user_id is None:
        raise NotFoundError("This calendar subscription link is not valid.")
    user = await session.get(User, user_id)
    if user is None or not user.is_active or not sheriff_calendar_access(user.tier):
        raise NotFoundError("This calendar subscription link is no longer active.")
    calendar = await list_sheriff_sales(session, market_code=market_code(market), limit=limit)
    return _ics_response(calendar, market_code(market))


@router.get("/repository", response_model=RepositoryList)
async def repository(
    session: SessionDep,
    current_user: CurrentUserDep,
    market: Annotated[str, Query()] = "hbg",
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> RepositoryList:
    return await list_repository(session, market_code=market_code(market), limit=limit)
