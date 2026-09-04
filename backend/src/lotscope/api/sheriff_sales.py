from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.security import create_calendar_token, verify_calendar_token
from lotscope.api.deps import get_app_settings, get_current_user, get_session
from lotscope.core.config import Settings
from lotscope.core.errors import NotFoundError
from lotscope.core.market import MARKET_CODE
from lotscope.risk.schemas import SheriffSaleCalendar, SheriffSaleDates
from lotscope.risk.service import (
    list_sheriff_sale_dates,
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
    sale_date: Annotated[date | None, Query(alias="date")] = None,
    date_from: Annotated[date | None, Query(alias="from")] = None,
    date_to: Annotated[date | None, Query(alias="to")] = None,
    zip_code: Annotated[str | None, Query(alias="zip")] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> SheriffSaleCalendar:
    return await list_sheriff_sales(
        session,
        market_code=MARKET_CODE,
        date_from=sale_date or date_from,
        date_to=sale_date or date_to,
        zip_code=zip_code,
        limit=limit,
    )


@router.get("/dates", response_model=SheriffSaleDates)
async def sheriff_sale_dates(
    session: SessionDep,
    current_user: CurrentUserDep,
) -> SheriffSaleDates:
    return await list_sheriff_sale_dates(session, market_code=MARKET_CODE)


@router.get("/calendar.ics")
async def sheriff_sales_ics(
    session: SessionDep,
    current_user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> Response:
    calendar = await list_sheriff_sales(session, market_code=MARKET_CODE, limit=limit)
    return _ics_response(calendar, MARKET_CODE)


@router.get("/calendar/subscribe", response_model=CalendarSubscription)
async def sheriff_sales_subscribe(
    current_user: CurrentUserDep,
    settings: SettingsDep,
) -> CalendarSubscription:
    token = create_calendar_token(settings, user_id=current_user.id)
    base = settings.api_base_url.rstrip("/")
    return CalendarSubscription(url=f"{base}/sheriff-sales/calendar/{token}.ics")


@router.get("/calendar/{token}.ics")
async def sheriff_sales_ics_by_token(
    session: SessionDep,
    settings: SettingsDep,
    token: str,
    limit: Annotated[int, Query(ge=1, le=500)] = 200,
) -> Response:
    user_id = verify_calendar_token(settings, token)
    if user_id is None:
        raise NotFoundError("This calendar subscription link is not valid.")
    user = await session.get(User, user_id)
    if user is None or not user.is_active:
        raise NotFoundError("This calendar subscription link is no longer active.")
    calendar = await list_sheriff_sales(session, market_code=MARKET_CODE, limit=limit)
    return _ics_response(calendar, MARKET_CODE)
