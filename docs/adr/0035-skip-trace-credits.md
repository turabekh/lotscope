# 35. Skip-trace credits

Date: 2026-07-03

## Status

Accepted

Gates PRD-amendment-01 feature **A1** (Phase 1). Resolves amendment open question #1 (provider). Extends ADR-0010/0030 (billing/tiers), ADR-0018/0019 (dormant-provider pattern), and the `owners` module.

## Context

The paying wedge (wholesalers) needs **contactability**: owner phones/emails to feed dialers and mailers. LotScope already holds the provider input — `parcel.owner`, `parcel.owner_key`, `parcel.mailing_address` (and the `owners` service that aggregates a portfolio by `owner_key`). What's missing is a skip-trace provider, a way to pay per lookup, and durable accounting for what was bought and spent.

Two hard constraints shape the design:
- **Money-adjacent state must be durable.** Credit balances cannot live in Redis (they survive no cache flush); they need Postgres. This is the opposite of the export counters (ADR-0034), which are disposable.
- **The provider is a paid external dependency with legal terms.** We must be able to build, test, and merge the whole feature with **no** live provider — mirroring the dormant-until-configured pattern for email (ADR-0018) and push (ADR-0019), where `get_*_sender(settings)` returns `None` when unconfigured and the app degrades gracefully.

Amendment open question #1 (provider selection) is decided here.

## Decision

**A durable Postgres credit ledger, a `skiptrace/` module behind a provider protocol that is dormant until configured, result caching keyed by `owner_key`, and Stripe one-time credit packs fulfilled webhook-only.**

### Provider

**First provider: BatchData** (skip-trace REST API), with **Endato** as the documented fallback. Rationale against the amendment's criteria: per-hit cost within the ≤ $0.15 target at volume, a JSON REST API, and **non-FCRA "people search"** permissible-use terms (explicitly not for credit/employment/insurance/tenant decisions). The choice is **configurable and dormant**: `skiptrace/provider.py` defines a `SkipTraceProvider` Protocol + a `NullSkipTraceProvider`; `get_skiptrace_provider(settings)` returns `None` (or the Null provider) when `skiptrace_api_key` is unset. The concrete `BatchDataProvider` HTTP client is wired when the contract is signed; nothing else in the feature depends on it being live, so this ADR and the module can merge before the contract does.

### Data model (Postgres, durable)

- `credit_ledger(id PK, user_id FK, delta int, reason text, ref text NULL, created_at)`. **Balance = `SUM(delta)`** for a user — never a mutable counter, so every grant/burn is auditable. `reason` ∈ {`pack_purchase`, `skiptrace_burn`, `investor_grant`, `appeal_packet_grant`, `refund`}; `ref` carries the Stripe payment id / parcel number / idempotency key.
- `skiptrace_result(owner_key PK, payload JSONB, provider text, traced_at)`. We paid once per owner; cache the raw provider payload with a **TTL policy** (default 90 days — re-trace after that as contact data goes stale).

### Spend & cache semantics

- `service.trace_owner(session, user_id, parcel_number)`:
  1. Resolve `owner_key` via the `owners` service. No `owner_key` → typed error (nothing to trace).
  2. **Cache hit within TTL:** return the cached payload. Burn **0** credits if *this user* already paid for this owner (idempotent per user, tracked via a `skiptrace_burn` ledger `ref = owner_key`); burn **1** credit if it's a different user (we resell the margin — we paid the provider once).
  3. **Miss / stale:** require balance ≥ 1, call the provider, upsert `skiptrace_result`, write a `skiptrace_burn` ledger row (`delta = -1`).
  - Balance check and burn happen in **one transaction** so concurrent traces can't overdraw.
- Insufficient balance → typed `QuotaExceededError`-style response the UI turns into a buy-credits prompt.

### Purchase & grants (webhook-only, mirrors ADR-0010)

- **Credit packs = Stripe one-time Prices** (e.g. 25 / $12.50, 100 / $40, 500 / $175 → ~$0.35–0.50 retail vs ~$0.08–0.15 cost, ≥60% margin). Checkout uses `mode="payment"` (today's checkout is `mode="subscription"` only — this adds the one-time mode).
- **Fulfillment is webhook-only:** `checkout.session.completed` for a credit-pack session writes a `pack_purchase` ledger row (`delta = +N` from price→credits config, `ref =` the Stripe payment id). Idempotent on `ref` so at-least-once delivery never double-grants. The success redirect never grants credits (same trust boundary as ADR-0010).
- **Investor monthly grant** (ADR-0030 gave Investor 100 credits/mo): a worker cron writes an `investor_grant` ledger row per active Investor, idempotent on `(user_id, ref=YYYY-MM)`.

### API

- `POST /parcels/{id}/skip-trace` (auth) → traces the owner, returns phones/emails + remaining balance.
- `GET /credits` (auth) → current balance + recent ledger.
- `POST /billing/credits/checkout` (auth) → one-time Checkout Session URL for a chosen pack.

### Frontend

Skip-trace button + result card in `OwnerPortfolioPanel` and Leads rows; credit balance in the user menu / Account; a buy-credits flow in Account. When the provider is unconfigured, the button is hidden (dormant), matching how push/email surfaces hide when off.

### Export integration (closes the ADR-0034 seam)

The A3 CSV export header was shaped to append skip-trace columns. Once traced, exports include the owner's phones/emails **for owners this user has traced** (join `skiptrace_result` by `owner_key`, gated on a `skiptrace_burn` by this user) — no extra burn at export time.

### Compliance (§13)

Provider data is **non-FCRA people-search**. UI copy states results may not be used for credit, employment, insurance, or tenant-screening decisions; outreach remains subject to TCPA/DNC and CAN-SPAM (extends the existing Leads/export disclaimer). Owner PII from traces is restricted to the purchasing user, encrypted at rest per §13, and never logged.

## Consequences

- The feature is fully buildable/testable/mergeable **before** a provider contract exists: the Null provider + config seam mean CI and local dev never touch a paid API; the concrete `BatchDataProvider` lands when the contract is signed.
- Ledger-as-source-of-truth (balance = `SUM(delta)`) is auditable and reconciles with Stripe, at the cost of a `SUM` per balance read — cheap at this scale, and cacheable later if needed.
- Caching by `owner_key` with cross-user resale keeps gross margin ≥60% (amendment success metric) and is the reason the cache is keyed by owner, not by user.
- Adds `mode="payment"` to checkout and a fulfillment branch to the existing subscription webhook — the webhook stays the single writer of money-adjacent state (tier **and** now credits).
- **Deferred:** the concrete BatchData HTTP client (dormant until contract); the appeal-packet credit grant (A5 will reuse `appeal_packet_grant`); rate-limiting/abuse controls on the trace endpoint beyond the balance gate; bulk/portfolio-wide tracing in one action (v1 traces one owner per call).
- **Risks:** provider format/terms drift (contained in the one client); PII handling is now a first-class obligation (encryption-at-rest + access scoping must ship with the concrete client, not after).
