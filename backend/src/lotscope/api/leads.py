from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_session
from lotscope.core.market import MARKET_CODE
from lotscope.distress.schemas import LeadsResponse
from lotscope.distress.service import find_leads

LEAD_LIST_LIMIT = 200

router = APIRouter(prefix="/leads", tags=["leads"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("", response_model=LeadsResponse)
async def leads(
    session: SessionDep,
    current_user: CurrentUserDep,
    min_score: Annotated[int, Query(ge=1, le=100)] = 30,
    vacant_only: bool = False,
    zip_code: Annotated[str | None, Query(max_length=10)] = None,
) -> LeadsResponse:
    limit = LEAD_LIST_LIMIT
    items = await find_leads(
        session,
        limit=limit,
        market_code=MARKET_CODE,
        min_score=min_score,
        vacant_only=vacant_only,
        zip_code=zip_code,
    )
    return LeadsResponse(
        limit=limit,
        returned=len(items),
        leads=items,
    )
