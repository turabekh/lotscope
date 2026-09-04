from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_current_user, get_session
from lotscope.buybox.schemas import (
    BuyBoxRead,
    BuyBoxWrite,
    OwnedParcelSeed,
    OwnedParcelSeedResult,
)
from lotscope.buybox.service import read_buy_box, seed_owned_parcels, write_buy_box

router = APIRouter(prefix="/me", tags=["buy-box"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/buy-box", response_model=BuyBoxRead)
async def read_own_buy_box(session: SessionDep, user: CurrentUserDep) -> BuyBoxRead:
    return await read_buy_box(session, user.id)


@router.put("/buy-box", response_model=BuyBoxRead)
async def write_own_buy_box(
    data: BuyBoxWrite, session: SessionDep, user: CurrentUserDep
) -> BuyBoxRead:
    saved = await write_buy_box(session, user.id, data)
    await session.commit()
    return saved


@router.post("/buy-box/owned-parcels/seed", response_model=OwnedParcelSeedResult)
async def seed_own_owned_parcels(
    data: OwnedParcelSeed, session: SessionDep, user: CurrentUserDep
) -> OwnedParcelSeedResult:
    result = await seed_owned_parcels(session, user.id, data.owner_name)
    await session.commit()
    return result
