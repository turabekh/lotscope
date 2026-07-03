from typing import Annotated

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.billing import StripeGateway
from lotscope.accounts.models import User
from lotscope.accounts.service import ensure_stripe_customer
from lotscope.api.deps import (
    get_app_settings,
    get_current_user,
    get_session,
    get_stripe_gateway,
)
from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError, ValidationError
from lotscope.skiptrace.packs import CREDIT_PACKS, pack_price_id
from lotscope.skiptrace.provider import get_skiptrace_provider
from lotscope.skiptrace.schemas import (
    CreditBalance,
    CreditCheckoutRequest,
    CreditCheckoutResponse,
    SkipTraceResultOut,
)
from lotscope.skiptrace.service import get_credit_balance, trace_owner

router = APIRouter(tags=["skip-trace"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
GatewayDep = Annotated[StripeGateway, Depends(get_stripe_gateway)]


@router.post("/parcels/{parcel_number}/skip-trace", response_model=SkipTraceResultOut)
async def skip_trace(
    parcel_number: str,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
) -> SkipTraceResultOut:
    provider = get_skiptrace_provider(settings)
    if provider is None:
        raise ConfigurationError("Skip trace is not available yet.")
    result = await trace_owner(session, provider, current_user.id, parcel_number)
    await session.commit()
    return result


@router.get("/credits", response_model=CreditBalance)
async def get_credits(session: SessionDep, current_user: CurrentUserDep) -> CreditBalance:
    return await get_credit_balance(session, current_user.id)


@router.post("/billing/credits/checkout", response_model=CreditCheckoutResponse)
async def credits_checkout(
    data: CreditCheckoutRequest,
    session: SessionDep,
    settings: SettingsDep,
    current_user: CurrentUserDep,
    gateway: GatewayDep,
) -> CreditCheckoutResponse:
    pack = CREDIT_PACKS.get(data.pack)
    if pack is None:
        raise ValidationError(f"Unknown credit pack '{data.pack}'.")
    price_id = pack_price_id(settings, pack.key)
    if not price_id:
        raise ConfigurationError("Credit packs are not configured.")
    customer_id = await ensure_stripe_customer(session, gateway, current_user)
    url = await gateway.create_credit_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        credit_amount=pack.credits,
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
    )
    await session.commit()
    return CreditCheckoutResponse(url=url)
