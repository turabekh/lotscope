# Entitlement consistency audit — 2026-08-01

**Requirement:** Amendment 03 §14.4 · **Backlog:** LR-B-031

Every advertised capability checked against `accounts/tiers.py`, the single source of entitlement truth.

## Surfaces

| Surface | How it gets entitlements | Drift risk |
|---|---|---|
| Pricing page (`PricingPlans.vue`) | `GET /billing/plans` → `PLAN_CATALOG` | **None structurally** — the page renders server copy; it hardcodes no limits |
| API authorization (`api/deps.py`, routers) | `tiers.py` predicates directly | None |
| Frontend gating (`UpgradePrompt.vue`, stores) | Server 429/403 with a cap name | None |
| Checkout (`api/billing.py`) | `PLAN_CATALOG` tiers | None |
| Portal | Stripe-hosted, tier written back on webhook | None |
| Upgrade prompts | Cap name from the server error | None |

The architecture is sound: the pricing page does not restate limits in its own copy, so the classic drift — a number changed in code and forgotten in marketing — cannot happen through the frontend. **All six surfaces read from one place.**

The remaining risk is inside `PLAN_CATALOG` itself, where `highlights` are free text sitting next to the limit tables they describe. That is what the new test binds.

## Findings

### 1. Two Enterprise claims have nothing behind them — owner decision

| Claim | Reality |
|---|---|
| `"Team seats and support"` | No team, organisation, or seat concept exists anywhere in the codebase. `app_user` has no organisation and there is no seat allocation |
| `"Bulk export and API access"` | Every `api_key` reference in the codebase is an **outbound vendor** key (Anthropic, Google). There is no customer API-key issuance and no public API surface. Bulk export *is* real: `EXPORT_ROW_LIMITS["enterprise"] = 10000` |

Enterprise is `action="contact"` rather than self-serve checkout, so both are sold through a conversation and could be delivered manually. That is materially different from a self-serve promise, and it is why this is flagged rather than deleted: **removing revenue copy is a commercial decision, not an engineering one.**

Both are recorded in `_UNENFORCEABLE_CLAIMS` in the consistency test, so they are declared rather than silent, and a third one cannot be added without the test failing.

**Recommendation:** keep "Team seats and support" (plausibly delivered by hand for a contact-sales tier), and either qualify "API access" as *on request* or drop it. An advertised API with no endpoint is the one most likely to reach a customer's expectations before it reaches ours.

### 2. Pro's export entitlement is under-advertised

`EXPORT_MONTHLY_LIMITS["pro"] = 10` and `EXPORT_ROW_LIMITS["pro"] = 2000` — Pro can export. But CSV export appears only in Investor's highlights (*"1,000 leads with CSV export"*), which reads as though export begins at Investor.

This errs in the customer's favour, so it is not a refund conversation — it is unclaimed value on the paid tier most likely to convert. Copy change, owner's call.

### 3. Everything numeric agrees

Verified against the tables, tier by tier: free 4 verdicts/day and 10 AI questions/day; Pro unlimited verdicts, 200 AI questions, 200 leads; Investor unlimited AI questions, 1,000 leads with export; Enterprise unlimited AI questions. Deal-feed claims match `feed_access`.

## What now guards this

`accounts/tests/test_entitlement_consistency.py` binds the advertised copy to the enforced predicates:

- every advertised number for AI questions, parcel verdicts, and leads must equal the enforced limit, and "Unlimited" must mean `None`;
- a tier advertising export must have a non-zero export allowance;
- a tier advertising the deal feed must be granted it by `feed_access`;
- the unenforceable-claim allowlist must match the catalog exactly, so a **new** unbacked claim fails the suite.

The last one is the important one. It converts "someone should check the pricing page" into a test that fails on the pull request that introduces the problem.

## Status

**Engineering complete.** The two copy decisions in finding 1 and the one in finding 2 are the owner's, and LR-B-031's "all six surfaces agree" cannot be fully closed until they are made.
