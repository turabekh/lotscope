from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.api.deps import get_session
from lotscope.markets.capabilities import (
    forced_sale_surface_label,
    hidden_surfaces,
    risk_coverage_note,
)
from lotscope.markets.schemas import MarketInfo
from lotscope.markets.service import list_markets

router = APIRouter(tags=["markets"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


@router.get("/markets", response_model=list[MarketInfo])
async def markets(session: SessionDep) -> list[MarketInfo]:
    rows = await list_markets(session)
    return [
        MarketInfo.model_validate(row).model_copy(
            update={
                "hidden_surfaces": sorted(hidden_surfaces(row.code)),
                "risk_coverage_note": risk_coverage_note(row.code),
                "forced_sale_surface_label": forced_sale_surface_label(row.code),
            }
        )
        for row in rows
    ]
