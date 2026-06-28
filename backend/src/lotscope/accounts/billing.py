from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, Protocol, cast

import stripe

from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError, ValidationError

Cadence = Literal["monthly", "annual"]

_PRO_GRANTING_STATUSES = frozenset({"active", "trialing", "past_due"})
_HANDLED_EVENTS = frozenset(
    {
        "checkout.session.completed",
        "customer.subscription.created",
        "customer.subscription.updated",
        "customer.subscription.deleted",
    }
)


def pro_price_ids(settings: Settings) -> frozenset[str]:
    return frozenset(
        price
        for price in (settings.stripe_price_pro_monthly, settings.stripe_price_pro_annual)
        if price
    )


def price_id_for_cadence(settings: Settings, cadence: Cadence) -> str:
    price = (
        settings.stripe_price_pro_monthly
        if cadence == "monthly"
        else settings.stripe_price_pro_annual
    )
    if not price:
        raise ConfigurationError(f"No Stripe price configured for the {cadence} Pro plan.")
    return price


def tier_for_subscription(
    status: str | None, price_id: str | None, granting_price_ids: frozenset[str]
) -> str:
    if status in _PRO_GRANTING_STATUSES and price_id is not None and price_id in granting_price_ids:
        return "pro"
    return "free"


@dataclass(frozen=True)
class SubscriptionState:
    customer_id: str
    subscription_id: str | None
    status: str | None
    price_id: str | None


@dataclass(frozen=True)
class WebhookOutcome:
    customer_id: str
    state: SubscriptionState | None


def _extract_price_id(subscription: dict[str, Any]) -> str | None:
    items = subscription.get("items", {}).get("data", [])
    if not items:
        return None
    price = items[0].get("price")
    if isinstance(price, dict):
        value = price.get("id")
        return value if isinstance(value, str) else None
    return price if isinstance(price, str) else None


def subscription_state_from_object(subscription: dict[str, Any]) -> SubscriptionState | None:
    customer = subscription.get("customer")
    if not isinstance(customer, str):
        return None
    return SubscriptionState(
        customer_id=customer,
        subscription_id=subscription.get("id"),
        status=subscription.get("status"),
        price_id=_extract_price_id(subscription),
    )


class StripeGateway(Protocol):
    async def create_customer(self, *, email: str, user_id: int) -> str: ...

    async def create_checkout_session(
        self, *, customer_id: str, price_id: str, success_url: str, cancel_url: str
    ) -> str: ...

    async def create_portal_session(self, *, customer_id: str, return_url: str) -> str: ...

    def parse_event(self, *, payload: bytes, signature: str) -> dict[str, Any]: ...


class StripeApiGateway:
    def __init__(self, settings: Settings) -> None:
        if not settings.stripe_secret_key:
            raise ConfigurationError("Billing is not configured.")
        self._client = stripe.StripeClient(settings.stripe_secret_key)
        self._webhook_secret = settings.stripe_webhook_secret

    async def create_customer(self, *, email: str, user_id: int) -> str:
        customer = await self._client.v1.customers.create_async(
            params={"email": email, "metadata": {"user_id": str(user_id)}}
        )
        return customer.id

    async def create_checkout_session(
        self, *, customer_id: str, price_id: str, success_url: str, cancel_url: str
    ) -> str:
        session = await self._client.v1.checkout.sessions.create_async(
            params={
                "mode": "subscription",
                "customer": customer_id,
                "line_items": [{"price": price_id, "quantity": 1}],
                "success_url": success_url,
                "cancel_url": cancel_url,
                "allow_promotion_codes": True,
            }
        )
        if session.url is None:
            raise ValidationError("Stripe did not return a checkout URL.")
        return session.url

    async def create_portal_session(self, *, customer_id: str, return_url: str) -> str:
        session = await self._client.v1.billing_portal.sessions.create_async(
            params={"customer": customer_id, "return_url": return_url}
        )
        return session.url

    def parse_event(self, *, payload: bytes, signature: str) -> dict[str, Any]:
        if not self._webhook_secret:
            raise ConfigurationError("Stripe webhook secret is not configured.")
        construct: Callable[..., Any] = stripe.Webhook.construct_event
        try:
            event = construct(payload, signature, self._webhook_secret)
        except (ValueError, stripe.SignatureVerificationError) as error:
            raise ValidationError("Invalid Stripe webhook signature.") from error
        return cast("dict[str, Any]", event.to_dict_recursive())


def interpret_event(event: dict[str, Any]) -> WebhookOutcome | None:
    event_type = event.get("type")
    if event_type not in _HANDLED_EVENTS:
        return None
    obj = event.get("data", {}).get("object", {})
    if not isinstance(obj, dict):
        return None
    if event_type == "checkout.session.completed":
        customer = obj.get("customer")
        if not isinstance(customer, str):
            return None
        return WebhookOutcome(customer_id=customer, state=None)
    state = subscription_state_from_object(obj)
    if state is None:
        return None
    if event_type == "customer.subscription.deleted":
        return WebhookOutcome(
            customer_id=state.customer_id,
            state=SubscriptionState(
                customer_id=state.customer_id,
                subscription_id=state.subscription_id,
                status="canceled",
                price_id=state.price_id,
            ),
        )
    return WebhookOutcome(customer_id=state.customer_id, state=state)
