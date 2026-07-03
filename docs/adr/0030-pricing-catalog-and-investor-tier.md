# 30. Pricing catalog revision and the Investor tier

Date: 2026-07-03

## Status

Proposed

Gates PRD-amendment-01 Phase 0 pricing. Extends ADR-0010 (billing) and ADR-0009 (accounts).

## Context

The $29/mo Pro price (ADR-0010, `accounts.tiers.PLAN_CATALOG`) anchors LotScope below the tools the paying wedge already buys (PropStream / BatchLeads / DealMachine at $80–500/mo). PRD-amendment-01 §2 resets the catalog to **Pro $99/mo · $990/yr** and adds a third self-serve plan, **Investor $249/mo · $2,490/yr**, positioned as the lead-gen machine (credits, exports, feed). The revenue-attach features that justify Investor (skip-trace credits A1, Deal Feed A2, CSV export A3) are gated by their own ADRs; this ADR covers **only the tier plumbing and the limit/catalog changes** so those features have a tier to hang off.

Two decisions the amendment leaves open (its §9.3) are resolved here: whether Investor is a distinct persisted `tier` value, and how existing $29 Pro subscribers are handled.

Constraints inherited from ADR-0010 that must not regress: **tier is written only by the Stripe webhook** (the checkout redirect never grants access); tier resolution is a **pure, unit-tested** function; Stripe prices come from **config, never hardcoded**; billing degrades to a typed "not configured" error when keys are absent.

## Decision

**Add `investor` as a first-class persisted tier flowing through the existing webhook-only path; reprice Pro; recognize legacy Pro prices so existing subscribers are grandfathered without a forced migration.**

- **New tier value `investor`.** `app_user.tier` is `String(20)` with no DB enum/check constraint, so no migration is needed for the column — `investor` is just a new value. It slots between `pro` and `enterprise`. The tier lineup becomes `free` < `pro` < `investor` < `enterprise` (Enterprise stays contact-sales, unchanged).

- **Limits (`accounts/tiers.py`) gain an `investor` column** and Pro values are unchanged from today except where the amendment §2.2 dictates. Values for the capabilities that exist today:

  | Capability | Free | Pro | Investor |
  |---|---|---|---|
  | Parcel views / day | 4 | ∞ | ∞ |
  | Ask the Parcel / day | 10 | 200 | ∞ |
  | Leads returned | 8 | 200 | 1,000 |
  | Watchlist | 25 | ∞ | ∞ |
  | Pipeline deals | 10 | ∞ | ∞ |
  | Saved searches | 1 | 50 | ∞ |

  Each limit lookup keeps its `_DEFAULT_TIER` (`free`) fallback, so an unknown tier fails safe to the most restrictive plan. The **new gates** in the amendment (CSV export, Deal Feed, skip-trace credits, sheriff calendar, assemblage, appeal packet) are **not** added here — they land with their feature ADRs (A1/A2/A3/A4/A5/A7), each extending the same maps.

- **Catalog (`PLAN_CATALOG`) repriced + extended:** Pro → `price_monthly_cents=9900`, `price_annual_cents=99000`; a new `investor` entry at `24900` / `249000` with `action="checkout"`; Free and Enterprise unchanged. Highlights follow the amendment's positioning (Pro = full research/unlimited verdicts; Investor = credits, exports, feed).

- **Tier resolution generalized to a price→tier map.** `tier_for_subscription` today returns `"pro"` when the price is in the Pro-granting set. It becomes a lookup over an ordered set of `(granting_price_ids, tier)` groups — Investor prices → `investor`, Pro prices → `pro`, else `free` — still pure and unit-tested, still driven entirely by config. Webhook handling is otherwise untouched (same statuses, same idempotency, still the only writer of `tier`).

- **New config (env-backed):** `stripe_price_investor_monthly`, `stripe_price_investor_annual`. `stripe_price_pro_monthly` / `_annual` are repointed to the new $99 Stripe Prices. A **legacy Pro price set** — `stripe_price_pro_legacy` (comma-separated ids, optional) — is folded into the Pro-granting group so existing $29 subscriptions keep resolving to `pro`.

- **Grandfathering (resolves §9.3).** No forced migration and no automatic re-charge. Existing $29 subscriptions keep their Stripe Price and keep resolving to `pro` (via `stripe_price_pro_legacy`) indefinitely at the code level; the **90-day window is a comms/billing-ops action, not code**: after it, affected users are offered a discounted move to the $99 plan via a Stripe coupon + the existing Customer Portal (ADR-0010). The app never downgrades or surprises them.

## Consequences

- The only schema touch is data, not DDL: introducing `investor` needs no `app_user` migration. Anywhere tier is compared as an ordered capability (limits maps) must include `investor`; a missing entry fails safe to Free.
- Legacy $29 subscribers are unaffected the moment this ships — their price id is still recognized. If `stripe_price_pro_legacy` is left unset in an environment, only the current Pro price grants Pro there (fine for fresh/test envs).
- Tier stays eventually-consistent with Stripe and webhook-idempotent (ADR-0010, unchanged). Investor downgrades behave exactly like Pro downgrades.
- **Deferred / out of scope:** the metered/credit and export/feed gates (their own ADRs); proration UX for the $29→$99 move (handled by Stripe + coupon, not in-app); any Investor-specific entitlement beyond the limits table above until A1/A2/A3 land. Enterprise remains a contact form.
- **Follow-up flagged:** JWT tier is embedded until token expiry (ADR-0009's open revocation item), so a newly-upgraded Investor may wait ≤60 min for elevated limits unless we refresh the token on return from checkout — same latency ADR-0010 already accepts for Pro.
