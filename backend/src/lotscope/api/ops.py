from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_session, require_admin
from lotscope.core.errors import NotFoundError
from lotscope.ops.schemas import FleetOverview, MarketHealthDetail
from lotscope.ops.service import fleet_overview, market_health

router = APIRouter(prefix="/admin/ops", tags=["ops"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AdminDep = Annotated[User, Depends(require_admin)]


@router.get("/fleet", response_model=FleetOverview)
async def ops_fleet(session: SessionDep, admin: AdminDep) -> FleetOverview:
    return await fleet_overview(session, datetime.now(UTC))


@router.get("/markets/{market_code}", response_model=MarketHealthDetail)
async def ops_market_health(
    market_code: str, session: SessionDep, admin: AdminDep
) -> MarketHealthDetail:
    detail = await market_health(session, market_code, datetime.now(UTC))
    if detail is None:
        raise NotFoundError(f"Market {market_code!r} is not registered.")
    return detail
