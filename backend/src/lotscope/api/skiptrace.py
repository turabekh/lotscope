from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.models import User
from lotscope.api.deps import (
    ParcelKeyDep,
    get_app_settings,
    get_current_user,
    get_session,
)
from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError
from lotscope.skiptrace.provider import get_skiptrace_provider
from lotscope.skiptrace.schemas import (
    SkipTraceResultOut,
)
from lotscope.skiptrace.service import trace_owner

router = APIRouter(tags=["skip-trace"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.post("/parcels/{parcel_number}/skip-trace", response_model=SkipTraceResultOut)
async def skip_trace(
    parcel_number: ParcelKeyDep,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> SkipTraceResultOut:
    provider = get_skiptrace_provider(settings)
    if provider is None:
        raise ConfigurationError("Skip trace is not available yet.")
    result = await trace_owner(
        session,
        provider,
        current_user.id,
        parcel_number,
        ttl_days=settings.skiptrace_cache_ttl_days,
    )
    await session.commit()
    return result
