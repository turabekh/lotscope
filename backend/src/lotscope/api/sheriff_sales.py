from datetime import UTC, date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import sheriff_calendar_access
from lotscope.api.deps import get_current_user, get_session
from lotscope.core.errors import QuotaExceededError
from lotscope.risk.schemas import RepositoryList, SheriffSaleCalendar
from lotscope.risk.service import (
    list_repository,
    list_sheriff_sales,
    sheriff_sale_ics,
)

router = APIRouter(prefix="/sheriff-sales", tags=["sheriff-sales"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


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
        market_code=market,
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
    calendar = await list_sheriff_sales(session, market_code=market, limit=limit)
    body = sheriff_sale_ics(calendar, now=datetime.now(UTC))
    return Response(
        content=body,
        media_type="text/calendar",
        headers={"Content-Disposition": f'attachment; filename="{market}-sales.ics"'},
    )


@router.get("/repository", response_model=RepositoryList)
async def repository(
    session: SessionDep,
    current_user: CurrentUserDep,
    market: Annotated[str, Query()] = "hbg",
    limit: Annotated[int, Query(ge=1, le=1000)] = 500,
) -> RepositoryList:
    return await list_repository(session, market_code=market, limit=limit)
