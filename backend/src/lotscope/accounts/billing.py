import json
from dataclasses import dataclass

import stripe

from lotscope.accounts.purchases import SKU_LABELS, SKU_PRICES_CENTS
from lotscope.core.config import Settings
from lotscope.core.errors import BillingUnconfiguredError, ValidationError


@dataclass(frozen=True)
class CheckoutSession:
    session_id: str
    url: str


def billing_is_configured(settings: Settings) -> bool:
    return bool(
        settings.stripe_secret_key
        and settings.stripe_price_packet
        and settings.stripe_price_diligence
    )


def price_id_for(settings: Settings, sku: str) -> str:
    price = {
        "packet": settings.stripe_price_packet,
        "diligence": settings.stripe_price_diligence,
    }.get(sku)
    if not price:
        raise BillingUnconfiguredError
    return price


def create_checkout_session(
    settings: Settings, *, sku: str, object_ref: str, user_id: int, email: str
) -> CheckoutSession:
    if not billing_is_configured(settings):
        raise BillingUnconfiguredError
    stripe.api_key = settings.stripe_secret_key
    created = stripe.checkout.Session.create(
        mode="payment",
        line_items=[{"price": price_id_for(settings, sku), "quantity": 1}],
        customer_email=email,
        client_reference_id=str(user_id),
        metadata={"user_id": str(user_id), "sku": sku, "object_ref": object_ref},
        success_url=settings.billing_success_url,
        cancel_url=settings.billing_cancel_url,
    )
    if created.url is None:
        raise BillingUnconfiguredError
    return CheckoutSession(session_id=created.id, url=created.url)


def verify_webhook(settings: Settings, payload: bytes, signature: str) -> dict[str, object]:
    if not settings.stripe_webhook_secret:
        raise BillingUnconfiguredError
    try:
        event = stripe.Webhook.construct_event(  # type: ignore[no-untyped-call]
            payload, signature, settings.stripe_webhook_secret
        )
    except (ValueError, AttributeError, KeyError) as cause:
        raise ValidationError("The Stripe event could not be read.") from cause
    except stripe.SignatureVerificationError as cause:
        raise ValidationError("The Stripe signature did not verify.") from cause
    del event
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValidationError("The Stripe event was not an object.")
    return parsed


def label_for(sku: str) -> str:
    return SKU_LABELS.get(sku, sku)


def amount_for(sku: str) -> int:
    return SKU_PRICES_CENTS[sku]
