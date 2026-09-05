from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from lotscope.accounts.billing import create_checkout_session, verify_webhook
from lotscope.accounts.models import User
from lotscope.accounts.purchases import (
    SKU_LABELS,
    SKU_PRICES_CENTS,
    mark_paid,
    record_session,
)
from lotscope.api.deps import get_app_settings, get_current_user, get_session
from lotscope.core.config import Settings
from lotscope.core.errors import ValidationError
from lotscope.core.logging import get_logger

router = APIRouter(tags=["billing"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]
CurrentUserDep = Annotated[User, Depends(get_current_user)]
SettingsDep = Annotated[Settings, Depends(get_app_settings)]

_logger = get_logger(__name__)
_PAID_EVENT = "checkout.session.completed"


class CheckoutRequest(BaseModel):
    sku: Literal["packet", "diligence"]
    object_ref: str = Field(min_length=1, max_length=80)


class CheckoutResponse(BaseModel):
    url: str
    session_id: str
    amount_cents: int
    label: str


@router.get("/checkout/prices")
async def list_prices() -> dict[str, dict[str, object]]:
    return {
        sku: {"amount_cents": SKU_PRICES_CENTS[sku], "label": SKU_LABELS[sku]}
        for sku in SKU_PRICES_CENTS
    }


@router.post("/checkout", response_model=CheckoutResponse)
async def start_checkout(
    data: CheckoutRequest, session: SessionDep, user: CurrentUserDep, settings: SettingsDep
) -> CheckoutResponse:
    created = create_checkout_session(
        settings,
        sku=data.sku,
        object_ref=data.object_ref,
        user_id=user.id,
        email=user.email,
    )
    await record_session(
        session,
        user_id=user.id,
        sku=data.sku,
        object_ref=data.object_ref,
        stripe_session_id=created.session_id,
    )
    await session.commit()
    return CheckoutResponse(
        url=created.url,
        session_id=created.session_id,
        amount_cents=SKU_PRICES_CENTS[data.sku],
        label=SKU_LABELS[data.sku],
    )


@router.post("/billing/webhook")
async def stripe_webhook(
    request: Request,
    session: SessionDep,
    settings: SettingsDep,
    stripe_signature: Annotated[str | None, Header(alias="Stripe-Signature")] = None,
) -> dict[str, str]:
    if not stripe_signature:
        raise ValidationError("The Stripe signature header is missing.")
    event = verify_webhook(settings, await request.body(), stripe_signature)

    if event.get("type") != _PAID_EVENT:
        return {"status": "ignored"}

    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    session_id = obj.get("id") if isinstance(obj, dict) else None
    if not isinstance(session_id, str):
        raise ValidationError("The Stripe event carried no checkout session id.")

    purchase = await mark_paid(session, session_id)
    if purchase is None:
        _logger.warning("stripe_session_unknown", stripe_session_id=session_id)
        await session.commit()
        return {"status": "unknown_session"}

    await session.commit()
    _logger.info(
        "purchase_paid",
        purchase_id=purchase.id,
        sku=purchase.sku,
        object_ref=purchase.object_ref,
    )
    return {"status": "paid"}
