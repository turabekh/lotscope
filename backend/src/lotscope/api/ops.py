from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_app_settings, get_session, require_admin
from lotscope.core.config import Settings
from lotscope.core.errors import NotFoundError
from lotscope.ops.schemas import FleetOverview, GateBoard, MarketHealthDetail
from lotscope.ops.service import fleet_overview, gate_board, market_health

router = APIRouter(prefix="/admin/ops", tags=["ops"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
AdminDep = Annotated[User, Depends(require_admin)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]


@router.get("/fleet", response_model=FleetOverview)
async def ops_fleet(session: SessionDep, admin: AdminDep, settings: SettingsDep) -> FleetOverview:
    return await fleet_overview(session, datetime.now(UTC), settings.git_sha)


@router.get("/gates", response_model=GateBoard)
async def ops_gates(session: SessionDep, admin: AdminDep) -> GateBoard:
    return await gate_board(session, datetime.now(UTC))


@router.get("/markets/{market_code}", response_model=MarketHealthDetail)
async def ops_market_health(
    market_code: str, session: SessionDep, admin: AdminDep
) -> MarketHealthDetail:
    detail = await market_health(session, market_code, datetime.now(UTC))
    if detail is None:
        raise NotFoundError(f"Market {market_code!r} is not registered.")
    return detail
