import pytest

from lotscope.accounts.billing import (
    interpret_event,
    price_id_for_cadence,
    pro_price_ids,
    subscription_state_from_object,
    tier_for_subscription,
)
from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError

_PRO = frozenset({"price_monthly", "price_annual"})


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "stripe_price_pro_monthly": "price_monthly",
        "stripe_price_pro_annual": "price_annual",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("status", "price_id", "expected"),
    [
        ("active", "price_monthly", "pro"),
        ("trialing", "price_annual", "pro"),
        ("past_due", "price_monthly", "pro"),
        ("canceled", "price_monthly", "free"),
        ("unpaid", "price_monthly", "free"),
        ("active", "unknown_price", "free"),
        ("active", None, "free"),
        (None, "price_monthly", "free"),
    ],
)
def test_tier_for_subscription(status: str | None, price_id: str | None, expected: str) -> None:
    assert tier_for_subscription(status, price_id, _PRO) == expected


def test_pro_price_ids_ignores_unset() -> None:
    settings = _settings(stripe_price_pro_annual=None)
    assert pro_price_ids(settings) == frozenset({"price_monthly"})


def test_price_id_for_cadence() -> None:
    settings = _settings()
    assert price_id_for_cadence(settings, "monthly") == "price_monthly"
    assert price_id_for_cadence(settings, "annual") == "price_annual"


def test_price_id_for_cadence_unconfigured_raises() -> None:
    settings = _settings(stripe_price_pro_annual=None)
    with pytest.raises(ConfigurationError):
        price_id_for_cadence(settings, "annual")


def test_subscription_state_extracts_price_from_nested_object() -> None:
    state = subscription_state_from_object(
        {
            "id": "sub_1",
            "customer": "cus_1",
            "status": "active",
            "items": {"data": [{"price": {"id": "price_monthly"}}]},
        }
    )
    assert state is not None
    assert state.customer_id == "cus_1"
    assert state.subscription_id == "sub_1"
    assert state.price_id == "price_monthly"


def test_subscription_state_requires_customer() -> None:
    assert subscription_state_from_object({"id": "sub_1", "status": "active"}) is None


def test_interpret_checkout_completed_links_customer_only() -> None:
    outcome = interpret_event(
        {"type": "checkout.session.completed", "data": {"object": {"customer": "cus_1"}}}
    )
    assert outcome is not None
    assert outcome.customer_id == "cus_1"
    assert outcome.state is None


def test_interpret_subscription_updated_carries_state() -> None:
    outcome = interpret_event(
        {
            "type": "customer.subscription.updated",
            "data": {
                "object": {
                    "id": "sub_1",
                    "customer": "cus_1",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_monthly"}}]},
                }
            },
        }
    )
    assert outcome is not None
    assert outcome.state is not None
    assert outcome.state.status == "active"
    assert outcome.state.price_id == "price_monthly"


def test_interpret_subscription_deleted_forces_canceled() -> None:
    outcome = interpret_event(
        {
            "type": "customer.subscription.deleted",
            "data": {
                "object": {
                    "id": "sub_1",
                    "customer": "cus_1",
                    "status": "active",
                    "items": {"data": [{"price": {"id": "price_monthly"}}]},
                }
            },
        }
    )
    assert outcome is not None
    assert outcome.state is not None
    assert outcome.state.status == "canceled"


def test_interpret_ignores_unhandled_event() -> None:
    assert interpret_event({"type": "invoice.paid", "data": {"object": {}}}) is None
