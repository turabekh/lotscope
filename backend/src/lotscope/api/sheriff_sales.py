from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import sheriff_calendar_access
from lotscope.api.deps import get_current_user, get_session
from lotscope.core.errors import QuotaExceededError
from lotscope.risk.schemas import SheriffSaleCalendar
from lotscope.risk.service import list_sheriff_sales

router = APIRouter(prefix="/sheriff-sales", tags=["sheriff-sales"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=SheriffSaleCalendar)
async def sheriff_sales(
    session: SessionDep,
    current_user: CurrentUserDep,
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
        session, date_from=date_from, date_to=date_to, zip_code=zip_code, limit=limit
    )
