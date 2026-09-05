from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_session
from lotscope.core.market import MARKET_CODE
from lotscope.underwriting.schemas import BuyBoxMatches
from lotscope.underwriting.service import find_buy_box_matches

router = APIRouter(prefix="/underwriting", tags=["underwriting"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/matches", response_model=BuyBoxMatches)
async def read_buy_box_matches(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> BuyBoxMatches:
    return await find_buy_box_matches(session, user.id, market=MARKET_CODE, limit=limit)
