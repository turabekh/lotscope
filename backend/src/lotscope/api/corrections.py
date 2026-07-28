from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.accounts.service import get_user_by_id
from lotscope.api.deps import get_current_user, get_session, require_admin
from lotscope.core.config import Settings, get_settings
from lotscope.corrections.schemas import CorrectionRead, CorrectionResolve, CorrectionStatus
from lotscope.corrections.service import (
    list_corrections,
    list_own_corrections,
    notify_correction_reporter,
    resolve_correction,
)
from lotscope.notifications.email import get_email_sender

router = APIRouter(tags=["corrections"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
AdminDep = Annotated[User, Depends(require_admin)]


@router.get("/corrections", response_model=list[CorrectionRead])
async def read_own_corrections(
    session: SessionDep,
    user: CurrentUserDep,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> list[CorrectionRead]:
    return await list_own_corrections(session, user.id, limit=limit)


@router.get("/admin/corrections", response_model=list[CorrectionRead])
async def read_correction_queue(
    session: SessionDep,
    admin: AdminDep,
    status: Annotated[CorrectionStatus | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> list[CorrectionRead]:
    return await list_corrections(session, status=status, limit=limit)


@router.patch("/admin/corrections/{correction_id}", response_model=CorrectionRead)
async def triage_correction(
    correction_id: int,
    data: CorrectionResolve,
    session: SessionDep,
    admin: AdminDep,
    settings: Annotated[Settings, Depends(get_settings)],
) -> CorrectionRead:
    correction = await resolve_correction(
        session, correction_id, resolved_by=admin.id, request=data
    )
    await session.commit()

    sender = get_email_sender(settings)
    if sender is not None:
        reporter = await get_user_by_id(session, correction.reported_by)
        if reporter is not None:
            await notify_correction_reporter(sender, settings, correction, to_email=reporter.email)
    return correction
