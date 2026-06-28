# 10. Billing with Stripe

Date: 2026-06-28

## Status

Accepted

## Context

ADR-0009 established `user.tier` (`free`/`pro`/`enterprise`) as the billing plan and deferred the payment system. Build-order step 11 needs paid plans: free users hit daily caps (4 parcel views, 10 AI questions — see `accounts.tiers`), and Pro removes them. We need to collect payment, manage subscriptions, and keep `tier` in sync with the customer's real subscription state without handling card data ourselves.

## Decision

**Stripe, hosted Checkout + Customer Portal, webhook-driven tier sync.** Card data never touches our servers (Stripe-hosted pages keep PCI scope minimal). The Stripe subscription is the source of truth; `app_user.tier` is a denormalized cache that webhooks keep current.

- **Plans:** `free` (default, no payment), `pro` (self-serve via Checkout, monthly or annual price), `enterprise` (contact-sales — no online checkout, a mailto/contact CTA). Lineup matches `accounts.tiers`.
- **State on `app_user`:** add `stripe_customer_id`, `stripe_subscription_id`, `subscription_status`. A Stripe customer is created lazily on first checkout and reused.
- **Tier resolution is pure and tested:** `tier_for_subscription(status, price_id)` maps a Stripe subscription status + price to a tier. Active/trialing/past_due on a Pro price → `pro`; canceled/unpaid/incomplete_expired → `free`. This is the one piece of business logic and is unit-tested independently of Stripe.
- **Endpoints** (`api/billing.py`, thin):
  - `GET /billing/plans` — static plan catalog (price ids resolved from config, never hardcoded).
  - `POST /billing/checkout` (auth) — creates/returns a Checkout Session URL for a chosen cadence.
  - `POST /billing/portal` (auth) — returns a Customer Portal URL for managing/canceling.
  - `POST /billing/webhook` (public, **Stripe-signature-verified**) — the only writer of `tier`/subscription fields from `checkout.session.completed` and `customer.subscription.{updated,deleted}`.
- **Adapter:** all Stripe access is centralized in `accounts.billing` behind an async `StripeGateway` interface (mirrors the `ai` client pattern), injected via a FastAPI dependency and mockable in tests. Stripe's async methods (`*_async`) are used; signature verification (`stripe.Webhook.construct_event`) is pure crypto, no I/O.
- **Config (env-backed, never in code):** `stripe_secret_key`, `stripe_webhook_secret`, `stripe_price_pro_monthly`, `stripe_price_pro_annual`, `billing_success_url`, `billing_cancel_url`, `billing_portal_return_url`.

## Consequences

- The webhook is the trust boundary: it is public but rejects any payload failing signature verification, and it is the **only** path that elevates a tier. Checkout success redirect is cosmetic, never grants access on its own.
- Tier is eventually consistent with Stripe (webhook latency). Acceptable: caps are daily and generous; a brief lag costs nothing.
- Webhook delivery is at-least-once, so handling is idempotent (re-applying the same subscription state is a no-op).
- Without Stripe keys configured (local/CI default), billing endpoints return a typed "billing not configured" error and the rest of the app is unaffected; tests mock the gateway.
- **Deferred:** proration UI, seat/team billing, invoices in-app, dunning emails, tax/VAT collection beyond Stripe defaults, annual-vs-monthly upgrade proration nuances. Enterprise remains a contact form, not online checkout.
- Revocation-before-expiry of JWTs (ADR-0009) is still open; a downgraded user keeps Pro access until their short-lived token expires (≤60 min).
