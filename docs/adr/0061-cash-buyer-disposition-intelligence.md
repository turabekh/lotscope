# 61. Cash-buyer / disposition intelligence

Date: 2026-07-12

## Status

Proposed

Delivers deal-closing batch feature **F1** (the exit-side, Investor-tier surface). Derives entirely from
`sale.grantee` data already ingested (RTT, ADR-0003). Depends on ADR-0032 (related-party token heuristic),
ADR-0049 (package-deed exclusion), ADR-0051/0052 (canonical keys, `geom_local` per-market SRID). Tier-gated
per ADR-0030; per-market name gate mirrors the owner-portfolio posture pending Ordinance 3478-07 (see
`docs/pgh-ordinance-3478-07-memo.md`).

## Context

We tell a user what to build and what a lot is worth, and (F2) how to make the offer — but nothing about the
**exit**: who actually buys vacant lots in this submarket. That fact lives in data we already hold. Every RTT
transfer stores a `grantee`; the buyers who recur are the disposition list an investor pays for.

Recon on the dev DB sizes and constrains the feature:

- **phl `grantee` fill = 100%** (730k sales, through 2026-05). **hbg and pgh `grantee` = 0%** — their sale
  loaders populate neither grantor nor grantee. So **F1 is phl-only**; hbg/pgh ship an honest "not available
  for this market" state, and extending those loaders is a follow-up, not this batch.
- At the recommended threshold (**≥3 arm's-length vacant-lot purchases in 24 months**, package-deeds excluded,
  price floor applied), **~106 distinct active buyers** in phl (35 at ≥5, 14 at ≥10) — a real, non-trivial
  roster.
- The single largest "buyer" is **PHILADELPHIA LAND BANK (132)** — a public entity that must be excluded; the
  remainder are genuine private investors (LLCs and individuals). There is **no existing phl public-entity name
  list** to reuse — `is_city_owned` is a parcel flag, not a grantee-name filter — so a government/Land-Bank name
  exclusion is net-new.
- **Mailing-address recovery is best-effort:** of the 106 buyers, 100 match a current `parcel.owner_key` by
  name but only **34 (32%)** have a non-null `mailing_address`. Mailing address therefore ships nullable and
  honest, never fabricated.

Two normalizations already exist and are **different**: `is_related_party` (token overlap, `valuation/avm.py`)
and `owner_key` (full-string punctuation/whitespace normalization, a persisted generated column on `parcel`).
The related-party helper is an **internal helper of `valuation/`**, so a new `buyers/` module importing it
would violate the module-boundary rule (architecture.md:35).

## Decision

**Build F1 as a new `buyers/` module producing a nightly-derived `buyer_profile` table off `sale`, with a
market-predicated near-parcel read API, gated Investor-only and per-market name-gated.** Pure derivation core;
thin adapters.

### 1. Shared name normalization moves to `core/`

Promote the pure, dependency-free name helpers (`_name_tokens`, `is_related_party`) from `valuation/avm.py` to
`core/` (e.g. `core/names.py`). `valuation/avm.py` and `buyers/` both import from `core/` (dependency direction
is inward — allowed). The move preserves behavior; ADR-0032's existing tests run **unmodified** against the new
location to prove equivalence. Add a `buyer_key(name)` normalizer in `core/names.py` that mirrors the
`OWNER_KEY_EXPRESSION` transform (strip `.,#`, collapse whitespace, upper, null-if-empty) so a `buyer_key`
computed in Python matches the DB-computed `parcel.owner_key` for the mailing-address join.

### 2. Arm's-length derivation rules (named constants, per-market-overridable)

An entity qualifies as an **active lot buyer** when, within the market, it has **≥ `BUYER_MIN_LOT_PURCHASES`
(=3)** purchases of vacant parcels (`parcel.is_vacant IS TRUE`) with `sale_date` within
**`BUYER_WINDOW_MONTHS` (=24)**, each surviving all four arm's-length exclusions:

1. **Related-party** — `is_related_party(grantor, grantee)` token overlap (ADR-0032).
2. **Package deed** — the `document_id`-appears-on-multiple-parcels predicate (ADR-0049), reused as a shared
   SQL predicate factored into `core/sql.py` (currently inline text in `valuation/service.py`).
3. **Nominal price** — `sale_price >= BUYER_MIN_PRICE` (=`DEFAULT_MIN_PRICE`); nulls excluded.
4. **Government / Land Bank** — grantee matching `GOVERNMENT_BUYER_PATTERNS` (net-new constant list:
   `PHILADELPHIA LAND BANK`, `CITY OF PHILADELPHIA`, `REDEVELOPMENT AUTHORITY`, `PHDC`, `PHILADELPHIA HOUSING
   AUTHORITY`, `COMMONWEALTH OF PENNSYLVANIA`, `SCHOOL DISTRICT`, `PHILADELPHIA REDEVELOPMENT`) is excluded.
   Empty/blank grantee fails safe to **excluded**.

Thresholds are named constants (module-level, later per-market-overridable) — never literals inside queries.

### 3. Derived `buyer_profile` table (provenance + computed-at, Golden Rule 6)

`buyer_profile`: `id, market_code FK, buyer_key (normalized), display_name, purchases_window,
lot_purchases_window, last_purchase_at, median_price, total_consideration, mailing_address NULL,
activity_centroid geometry(Point) NULL, computed_at, source`. Unique `(market_code, buyer_key)`. GiST index on
`activity_centroid` (the near-parcel read uses it). Migration is **additive** (autogenerate-managed — this is a
new table imported into `lotscope/models.py`).

### 4. Derivation job — pure core + thin adapter, idempotent

Scan `sale` for the window, apply the four exclusions, normalize grantee → `buyer_key`, aggregate stats,
compute an activity centroid from the bought parcels' `geom_local`, best-effort join `buyer_key = owner_key`
for a `mailing_address`, **upsert** qualifying profiles and **delete** profiles that no longer qualify (buyer
aged out). Idempotent and restartable. Registered as a **nightly ARQ cron** in the post-ingest slot (per D4) +
an **admin-console maintenance job**, with a `dataset_freshness` cadence entry (`("phl","buyer_profile")`) so
the ops page grades it honestly.

### 5. API — Investor-gated, market-predicated, name-gated

- `GET /parcels/{id}/buyers` — active buyers ranked by proximity of their `activity_centroid` to the subject
  parcel (`geom_local`, market-predicated join), then recency. **Every cross-parcel spatial query joins on
  `market_code`** and is added to the `zzz` two-market isolation suite.
- `GET /buyers?market=&min_purchases=` — paginated market roster.
- `GET /buyers/{buyer_key}` — profile + purchase list with parcel deep-links.

All **Investor-tier** (new `INVESTOR_TIERS` set + `buyer_intel_access` in `accounts/tiers.py`; enforce via the
existing 429/`QuotaExceededError` machinery — no new gating pattern). The per-market **name gate** is a
data-driven `"buyer_names"` token added to `_HIDDEN_SURFACES["pgh"]`: for a gated market the endpoints return
the unavailable state, never names.

### Privacy (§13)

Buyer names and mailing addresses are owner-adjacent PII: shown in-product and in gated Investor exports (with
the existing Fair Housing / TCPA / CAN-SPAM footer) but **never logged**. Retention follows the source `sale`
data (public record).

## Consequences

- **A genuine Investor-tier surface ships from data we already store** — no new ingestion, no scoring change.
- **phl-only, honestly.** hbg/pgh grantee backfill is the obvious follow-up; until then the name gate + empty
  grantee produce an honest "not available" state, so the feature never lies about coverage.
- **A shared `core/names.py` resolves a latent boundary problem** (valuation's name helper was being eyed for
  cross-module reuse) and de-duplicates two normalizations into one home. ADR-0032 tests prove equivalence.
- **Mailing address is ~32% populated** — the UI and export render it nullable and say so; this is a lead, not
  a guarantee.
- **New surface to own:** a `buyers/` module, one table + nightly job, three read endpoints, one roster page +
  one dossier panel. All follow existing patterns (derived table + cadence, thin routers, capability gate).
- **`VERDICT_VERSION` unaffected** (read-side derived data; no scoring, buildability, or verdict touch).
- **Deferred:** hbg/pgh grantee loaders; buyer skip-trace; buyer "match scoring"/ML; per-market threshold
  overrides beyond the constants.
