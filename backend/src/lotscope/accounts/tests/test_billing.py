from datetime import date

import pytest

from lotscope.accounts.billing import (
    appeal_packet_from_checkout,
    credit_grant_from_checkout,
    founding_offer_available,
    founding_offer_configured,
    granting_price_ids,
    interpret_event,
    investor_price_ids,
    price_id_for_cadence,
    pro_price_ids,
    subscription_state_from_object,
    tier_for_subscription,
)
from lotscope.core.config import Settings
from lotscope.core.errors import ConfigurationError

_TODAY = date(2026, 7, 11)


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "stripe_price_pro_monthly": "price_pro_monthly",
        "stripe_price_pro_annual": "price_pro_annual",
        "stripe_price_investor_monthly": "price_inv_monthly",
        "stripe_price_investor_annual": "price_inv_annual",
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("status", "price_id", "expected"),
    [
        ("active", "price_pro_monthly", "pro"),
        ("trialing", "price_pro_annual", "pro"),
        ("past_due", "price_pro_monthly", "pro"),
        ("active", "price_inv_monthly", "investor"),
        ("trialing", "price_inv_annual", "investor"),
        ("active", "price_pro_legacy_29", "pro"),
        ("canceled", "price_pro_monthly", "free"),
        ("unpaid", "price_inv_monthly", "free"),
        ("active", "unknown_price", "free"),
        ("active", None, "free"),
        (None, "price_pro_monthly", "free"),
    ],
)
def test_tier_for_subscription(status: str | None, price_id: str | None, expected: str) -> None:
    settings = _settings(stripe_price_pro_legacy="price_pro_legacy_29")
    assert tier_for_subscription(status, price_id, granting_price_ids(settings)) == expected


def test_pro_price_ids_include_legacy_and_ignore_unset() -> None:
    settings = _settings(
        stripe_price_pro_annual=None,
        stripe_price_pro_legacy="legacy_a, legacy_b",
    )
    assert pro_price_ids(settings) == frozenset({"price_pro_monthly", "legacy_a", "legacy_b"})


def test_investor_price_ids() -> None:
    assert investor_price_ids(_settings()) == frozenset({"price_inv_monthly", "price_inv_annual"})


def test_price_id_for_cadence_resolves_by_tier() -> None:
    settings = _settings()
    assert price_id_for_cadence(settings, "pro", "monthly") == "price_pro_monthly"
    assert price_id_for_cadence(settings, "pro", "annual") == "price_pro_annual"
    assert price_id_for_cadence(settings, "investor", "monthly") == "price_inv_monthly"
    assert price_id_for_cadence(settings, "investor", "annual") == "price_inv_annual"


def test_price_id_for_cadence_unconfigured_raises() -> None:
    settings = _settings(stripe_price_investor_annual=None)
    with pytest.raises(ConfigurationError):
        price_id_for_cadence(settings, "investor", "annual")


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


def test_credit_grant_from_payment_checkout() -> None:
    grant = credit_grant_from_checkout(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "payment",
                    "customer": "cus_1",
                    "payment_intent": "pi_1",
                    "metadata": {"credits": "100"},
                }
            },
        }
    )
    assert grant is not None
    assert grant.customer_id == "cus_1"
    assert grant.credits == 100
    assert grant.ref == "pi_1"


def test_credit_grant_ignores_subscription_checkout() -> None:
    assert (
        credit_grant_from_checkout(
            {
                "type": "checkout.session.completed",
                "data": {"object": {"mode": "subscription", "customer": "cus_1"}},
            }
        )
        is None
    )


def test_credit_grant_requires_credits_metadata() -> None:
    assert (
        credit_grant_from_checkout(
            {
                "type": "checkout.session.completed",
                "data": {"object": {"mode": "payment", "customer": "cus_1", "metadata": {}}},
            }
        )
        is None
    )


def test_appeal_packet_from_payment_checkout() -> None:
    purchase = appeal_packet_from_checkout(
        {
            "type": "checkout.session.completed",
            "data": {
                "object": {
                    "mode": "payment",
                    "customer": "cus_1",
                    "payment_intent": "pi_9",
                    "metadata": {"product": "appeal_packet", "parcel_number": "000000001"},
                }
            },
        }
    )
    assert purchase is not None
    assert purchase.customer_id == "cus_1"
    assert purchase.parcel_number == "000000001"
    assert purchase.ref == "pi_9"


def test_appeal_packet_ignores_credit_checkout() -> None:
    assert (
        appeal_packet_from_checkout(
            {
                "type": "checkout.session.completed",
                "data": {
                    "object": {
                        "mode": "payment",
                        "customer": "cus_1",
                        "metadata": {"credits": "25"},
                    }
                },
            }
        )
        is None
    )


def test_founding_price_grants_pro_tier() -> None:
    settings = _settings(stripe_price_pro_founding="price_founding")
    assert "price_founding" in pro_price_ids(settings)
    assert tier_for_subscription("active", "price_founding", granting_price_ids(settings)) == "pro"


def test_founding_offer_configured_requires_price_and_unexpired_cutoff() -> None:
    assert founding_offer_configured(_settings(), today=_TODAY) is False
    assert (
        founding_offer_configured(
            _settings(stripe_price_pro_founding="price_founding"), today=_TODAY
        )
        is True
    )
    assert (
        founding_offer_configured(
            _settings(stripe_price_pro_founding="price_founding", founding_cutoff="2026-07-10"),
            today=_TODAY,
        )
        is False
    )
    assert (
        founding_offer_configured(
            _settings(stripe_price_pro_founding="price_founding", founding_cutoff="not-a-date"),
            today=_TODAY,
        )
        is False
    )


def test_founding_offer_available_respects_cap() -> None:
    settings = _settings(stripe_price_pro_founding="price_founding", founding_cap=50)
    assert founding_offer_available(settings, active_count=49, today=_TODAY) is True
    assert founding_offer_available(settings, active_count=50, today=_TODAY) is False
    assert founding_offer_available(_settings(), active_count=0, today=_TODAY) is False
