from typing import Annotated

from fastapi import APIRouter, Depends, Header, Request
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.billing import (
    StripeGateway,
    interpret_event,
    price_id_for_cadence,
)
from lotscope.accounts.models import User
from lotscope.accounts.schemas import (
    CheckoutRequest,
    CheckoutResponse,
    PlanInfo,
    PlansResponse,
    PortalResponse,
)
from lotscope.accounts.service import (
    apply_subscription_state,
    ensure_stripe_customer,
    get_user_by_stripe_customer,
)
from lotscope.accounts.tiers import PLAN_CATALOG
from lotscope.api.deps import (
    get_app_settings,
    get_current_user,
    get_optional_user,
    get_session,
    get_stripe_gateway,
)
from lotscope.core.config import Settings
from lotscope.core.errors import ValidationError

router = APIRouter(prefix="/billing", tags=["billing"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]
GatewayDep = Annotated[StripeGateway, Depends(get_stripe_gateway)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]


@router.get("/plans", response_model=PlansResponse)
async def plans(
    settings: SettingsDep,
    user: Annotated[User | None, Depends(get_optional_user)],
) -> PlansResponse:
    current_tier = user.tier if user is not None else None
    return PlansResponse(
        contact_url=settings.enterprise_contact_url,
        plans=[
            PlanInfo(
                tier=entry.tier,
                name=entry.name,
                tagline=entry.tagline,
                price_monthly_cents=entry.price_monthly_cents,
                price_annual_cents=entry.price_annual_cents,
                action=entry.action,
                highlights=list(entry.highlights),
                is_current=entry.tier == current_tier,
            )
            for entry in PLAN_CATALOG
        ],
    )


@router.post("/checkout", response_model=CheckoutResponse)
async def checkout(
    data: CheckoutRequest,
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    gateway: GatewayDep,
) -> CheckoutResponse:
    price_id = price_id_for_cadence(settings, data.tier, data.cadence)
    customer_id = await ensure_stripe_customer(session, gateway, user)
    url = await gateway.create_checkout_session(
        customer_id=customer_id,
        price_id=price_id,
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
    )
    await session.commit()
    return CheckoutResponse(url=url)


@router.post("/portal", response_model=PortalResponse)
async def portal(
    user: CurrentUserDep,
    session: SessionDep,
    settings: SettingsDep,
    gateway: GatewayDep,
) -> PortalResponse:
    if user.stripe_customer_id is None:
        raise ValidationError("No billing account exists for this user yet.")
    url = await gateway.create_portal_session(
        customer_id=user.stripe_customer_id,
        return_url=settings.billing_portal_return_url,
    )
    return PortalResponse(url=url)


@router.post("/webhook", status_code=200)
async def webhook(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    gateway: GatewayDep,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, bool]:
    if stripe_signature is None:
        raise ValidationError("Missing Stripe signature.")
    payload = await request.body()
    event = gateway.parse_event(payload=payload, signature=stripe_signature)
    outcome = interpret_event(event)
    if outcome is None:
        return {"handled": False}
    user = await get_user_by_stripe_customer(session, outcome.customer_id)
    if user is None or outcome.state is None:
        return {"handled": user is not None}
    apply_subscription_state(settings, user, outcome.state)
    await session.commit()
    return {"handled": True}
