from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.tiers import top_plays_access
from lotscope.api.deps import get_current_user, get_session
from lotscope.assemblage.schemas import AssemblageTopResponse
from lotscope.assemblage.service import top_plays
from lotscope.core.errors import QuotaExceededError

router = APIRouter(prefix="/assemblage", tags=["assemblage"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/top", response_model=AssemblageTopResponse)
async def assemblage_top(
    session: SessionDep,
    current_user: CurrentUserDep,
    neighborhood: Annotated[str | None, Query(max_length=120)] = None,
    zoning: Annotated[str | None, Query(max_length=20)] = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> AssemblageTopResponse:
    if not top_plays_access(current_user.tier):
        raise QuotaExceededError(
            "Assemblage Top Plays is a Pro feature — upgrade to see the ranked citywide feed."
        )
    return await top_plays(session, neighborhood=neighborhood, zoning=zoning, limit=limit)
