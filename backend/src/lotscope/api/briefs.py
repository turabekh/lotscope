from datetime import date, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.agent.signals import AnalystBrief, AnalystSignal
from lotscope.api.deps import get_current_user, get_session

router = APIRouter(prefix="/briefs", tags=["briefs"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]

MAX_BRIEFS = 60


class BriefSignal(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    kind: str
    parcel_number: str | None
    headline: str
    source: str
    source_url: str | None


class BriefRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    brief_date: date
    text: str
    signal_count: int
    emailed_at: datetime | None
    run_id: int | None
    signals: list[BriefSignal] = []


@router.get("", response_model=list[BriefRead])
async def list_briefs(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=MAX_BRIEFS)] = 14,
) -> list[BriefRead]:
    rows = (
        (
            await session.execute(
                select(AnalystBrief)
                .where(AnalystBrief.user_id == user.id)
                .order_by(AnalystBrief.brief_date.desc())
                .limit(limit)
            )
        )
        .scalars()
        .all()
    )
    return [BriefRead.model_validate(row) for row in rows]


@router.get("/today", response_model=BriefRead | None)
async def todays_brief(session: SessionDep, user: CurrentUserDep) -> BriefRead | None:
    """What the Analyst screen pins. Null means nothing changed, which is an answer."""
    brief = (
        await session.execute(
            select(AnalystBrief)
            .where(AnalystBrief.user_id == user.id)
            .order_by(AnalystBrief.brief_date.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if brief is None:
        return None

    signals = (
        (
            await session.execute(
                select(AnalystSignal)
                .where(
                    AnalystSignal.user_id == user.id,
                    AnalystSignal.signal_date == brief.brief_date,
                )
                .order_by(AnalystSignal.id)
            )
        )
        .scalars()
        .all()
    )
    read = BriefRead.model_validate(brief)
    read.signals = [BriefSignal.model_validate(signal) for signal in signals]
    return read
