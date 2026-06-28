from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import get_app_settings, get_current_user, get_session
from lotscope.core.config import Settings
from lotscope.notifications.schemas import (
    PushSubscribeRequest,
    PushUnsubscribeRequest,
    VapidKeyResponse,
)
from lotscope.notifications.service import remove_push_subscription, save_push_subscription

router = APIRouter(prefix="/push", tags=["push"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/vapid-public-key", response_model=VapidKeyResponse)
async def vapid_public_key(settings: SettingsDep, user: CurrentUserDep) -> VapidKeyResponse:
    return VapidKeyResponse(public_key=settings.vapid_public_key)


@router.post("/subscribe", status_code=204)
async def subscribe(data: PushSubscribeRequest, session: SessionDep, user: CurrentUserDep) -> None:
    await save_push_subscription(
        session,
        user.id,
        endpoint=data.endpoint,
        p256dh=data.keys.p256dh,
        auth=data.keys.auth,
    )
    await session.commit()


@router.post("/unsubscribe", status_code=204)
async def unsubscribe(
    data: PushUnsubscribeRequest, session: SessionDep, user: CurrentUserDep
) -> None:
    await remove_push_subscription(session, user.id, data.endpoint)
    await session.commit()
