# PRD Amendment 01 — Monetization & Hardening

**Status:** Draft for review
**Date:** 2026-07-02
**Amends:** `docs/PRD.md` (current revision)
**Author:** Turaboy (drafted with Claude)

This amendment adds revenue-attach features, hardening work, and an updated pricing model to the product spec. It follows the §5 catalog convention (Core / Differentiator / Revenue tiers). Feature IDs here are `A1–A11`; fold them into the §5 numbering on the next PRD consolidation. Each A-feature is ADR-gated before implementation (next available ADR number — 0029+ is reserved for the frontend IA redesign series).

Context this amendment assumes: verdict at **v5**, ~550k parcels live on GCP, frontend IA redesign slices 2–6 in flight, and the ingestion refactor direction endorsed as **ELT with a raw landing layer, monorepo, staging schema as the contract** (ADR-0004 follow-up). Several features below depend on that raw layer; it is promoted from "architecture hygiene" to a **product prerequisite** (see §D1).

---

## 1. Strategic framing

The paying wedge is the **wholesaler / land flipper** persona (already primary in PRD personas). They currently pay PropStream / BatchLeads / DealMachine $80–500/mo for distressed-owner leads plus contactability. LotScope's lead engine (distress index, deal signal) is stronger; what's missing is **contactability (skip trace), freshness (daily deltas), and workflow egress (export)**. The developer persona pays for feasibility accuracy; for them the priority is **closing the overlay/abatement gaps** so "buildable by-right" verdicts survive scrutiny.

Revenue model shifts from subscription-only to **subscription + metered credits + transactional SKUs**:

| Line | Mechanism | Buyer |
|---|---|---|
| Subscriptions (Free / Pro / Investor) | Stripe recurring (exists, ADR-0010) | Wholesalers, developers |
| Skip-trace credits | Prepaid credit packs, metered burn | Wholesalers |
| Tax-appeal evidence packet | One-time Stripe checkout | Homeowners, small landlords |
| Data/API licensing, multi-city | Deferred (unchanged from PRD) | — |

**Non-product note (recorded so the PRD stays honest):** the binding constraint on revenue is distribution — Philly REIA meetups, investor groups, agent referrals — not the feature set. This amendment maximizes conversion of traffic that arrives; it does not create traffic.

---

## 2. Pricing & tier changes

### 2.1 Plan catalog (supersedes current `billing/plans.py` values)

| | Free | **Pro — $99/mo · $990/yr** | **Investor — $249/mo · $2,490/yr** | Enterprise |
|---|---|---|---|---|
| Positioning | Try the verdict | Full research, unlimited verdicts | Lead-gen machine: credits, exports, feed | Contact sales |
| Stripe action | — | checkout | checkout | contact |

The current catalog's Pro at $29/mo is superseded. Migration: grandfather existing Pro subscribers for 90 days, then offer a discounted move to the $99 plan. Requires new Stripe Prices; tier writes remain **webhook-only** per ADR-0010 — Investor is a new `tier` value flowing through the same path.

### 2.2 Limits table (extends `accounts/tiers.py`)

Existing limits unchanged unless noted. New gates in **bold**.

| Capability | Free | Pro | Investor |
|---|---|---|---|
| Parcel views / day | 4 | ∞ | ∞ |
| Ask the Parcel / day | 10 | 200 | ∞ |
| Leads returned | 8 | 200 | 1,000 |
| Watchlist | 25 | ∞ | ∞ |
| Pipeline deals | 10 | ∞ | ∞ |
| Saved searches | 1 | 50 | ∞ |
| **Lead/list CSV exports / month** | **0** | **10 exports · 2,000 rows ea** | **∞ exports · 10,000 rows ea** |
| **Deal Feed** | **—** | **In-app** | **In-app + daily email** |
| **Skip-trace credits included / mo** | **0** | **0 (purchasable)** | **100 (then purchasable)** |
| **Sheriff-sale calendar** | **—** | **✓** | **✓** |
| **Assemblage Top-Plays feed** | **—** | **✓** | **✓** |
| **Tax-appeal packet** | **$79 one-time (any tier, incl. Free)** | **$79** | **1 free / mo, then $79** |

Enforcement: monthly counters follow the existing Redis daily-key pattern (`usage:` keys) with month-granular keys; credits use a durable ledger (A1), not Redis.

---

## 3. New features — Revenue attach

### A1 — Skip-trace credits *(Revenue · P0)*

**Extends:** §5.14 (metered credits — PRD already envisions report credits; this generalizes the metering) and the PRD "outreach" tier.

**User story:** As a wholesaler viewing a lead or owner portfolio, I click **Skip trace**, spend 1 credit, and get the owner's phones/emails inline and in my exports.

**Data we already have:** `parcel.owner`, `parcel.owner_key`, `parcel.mailing_address` — sufficient provider input.

**Spec:**
- New module `skiptrace/` (module-boundary rules apply): `service.py` exposes `trace_owner(session, user_id, parcel_number)`.
- Provider behind a protocol with a `NullSkipTraceProvider` when unconfigured — same dormant-until-configured pattern as email (ADR-0018) and push (ADR-0019). First provider: BatchData or Endato (decision in the ADR; criteria: per-hit cost ≤ $0.15, permissible-use terms, JSON API).
- **Credit ledger:** table `credit_ledger(id, user_id FK, delta, reason, ref, created_at)`; balance = `SUM(delta)`. Postgres, not Redis — money-adjacent state must survive cache flushes. Monthly Investor grant = scheduled ledger credit (worker cron).
- **Result caching:** table `skiptrace_result(owner_key, payload JSONB, provider, traced_at)` with TTL policy (e.g., 90 days). A cache hit within TTL burns **no** credit for the same user and 1 credit for a different user (we paid once; we can price the margin).
- Credit packs: Stripe one-time Prices (e.g., 25 / $12.50, 100 / $40, 500 / $175 → $0.35–0.50 retail vs ~$0.08–0.15 cost). Fulfillment webhook-only, mirroring ADR-0010.
- API: `POST /parcels/{id}/skip-trace`, `GET /credits`, `POST /billing/credits/checkout`.
- Frontend: button + result card in `OwnerPortfolioPanel` and the Leads page rows; credit balance in `UserMenu`/Account; buy-credits flow in Account.
- **Compliance (§13 addition):** provider data is non-FCRA people-search; UI copy states results may not be used for credit, employment, insurance, or tenant-screening decisions; outreach remains subject to TCPA/DNC (extend the existing Leads-page disclaimer).

**Success metric:** ≥25% of Pro/Investor users buy or use credits in month 1 of the feature; credit gross margin ≥60%.

### A2 — Deal Feed: citywide change detection *(Differentiator · P0)*

**Extends:** §5.16 (change alerts) from *watched parcels* to *the whole city filtered by your buy box*. This is the retention feature.

**User story:** Every morning I open LotScope (or my email) and see: "Since yesterday in your buy box: 14 new sheriff-sale flags, 31 new delinquencies, 6 new dangerous-building designations, 4 assessment drops."

**Depends on D1 (raw landing layer).** Today loaders upsert in place, so yesterday's state is unrecoverable. Delta computation happens at load time: staged batch vs current rows → event rows.

**Spec:**
- Table `parcel_event(id, parcel_number FK, dataset, code, severity, old_value JSONB, new_value JSONB, detected_at, ingest_run_id)`. Event codes reuse the watchlist-change taxonomy (ADR-0017: `sheriff_sale`, `delinquent`, `tax_up`, `li_new`, `danger`, `vacancy`, `assessment`, plus `new_deed`, `new_permit`, `new_demo`).
- Emission lives in the ingestion staging→merge step (the staging schema is the contract; event emission is part of the merge, keeping loaders dumb).
- API: `GET /feed?since=&criteria=` — filtering reuses `savedsearch.matching.build_where` verbatim so a saved search doubles as a feed filter.
- Frontend: **Feed** page/pane — in the redesign IA this is a first-class left-sidebar item scoped to the active market (slots into the market-scope primitive from Slice 1). Each event row deep-links to the parcel dossier.
- Email: Investor daily digest reuses the ADR-0018 SMTP digest machinery and the 13:00 cron slot; per-user criteria come from their alert-enabled saved searches.
- Retention: keep `parcel_event` 18 months (also the seed of the longitudinal-history moat).

**Success metric:** feed WAU / paying users ≥ 60%; churn among feed-users at least 30% lower than non-users.

### A3 — Lead & list export (CSV) *(Revenue gate · P0)*

**Extends:** §5.1 (saved searches) and the Leads surface. Wholesalers live in dialers and mail-merge; export is the egress that justifies $99+.

**Spec:**
- `GET /leads/export` and `GET /saved-searches/{id}/export` → CSV of the current result set joined to `parcel.mailing_address` (+ skip-trace phones/emails where the user already traced that owner).
- Streaming response; row cap and monthly export count per tier (see §2.2). Monthly Redis counters.
- Every file carries a footer row: informational-only + Fair Housing / TCPA / CAN-SPAM reminder (§13).
- Frontend: Export button on Leads and expanded Saved Search views; upgrade prompt for Free.

**Success metric:** export used by ≥50% of paying users monthly; appears in top-3 stated reasons to upgrade.

### A4 — Sheriff-sale calendar *(Differentiator · P1)*

**Extends:** §5.5 (risk & due diligence). We flag `in_sheriff_sale` (boolean) but not *when* or *for what case*. Auction-prep is a proven standalone SKU elsewhere ($40–200/mo products).

**Spec:**
- New source: Philadelphia Sheriff's Office sale lists (tax & mortgage foreclosure). Register in `data-sources.md`; likely scrape/CSV rather than Carto — the ingestion client abstraction (Carto/ArcGIS) grows a third fetch style, contained in the loader.
- Table `sheriff_sale(id, parcel_number FK, case_number, sale_type, sale_date, status, opening_bid NUMERIC NULL, source, ingested_at)` (+ IngestionMixin).
- Risk flag upgrade: `sheriff_sale` flag detail gains the date ("listed for sale 2026-08-05"); imminent sales (<30 days) surface in the Deal Feed as high-severity events.
- API: `GET /sheriff-sales?from=&to=&zip=` ranked by `verdict.max_allowable_offer` vs `opening_bid` where present.
- Frontend: calendar/list page (Pro+), sidebar item in redesign IA; countdown chip on the parcel dossier.

**Success metric:** ≥30% of Pro+ users visit monthly during sale cycles.

### A5 — Tax-appeal evidence packet *(Transactional SKU · P1)*

**Extends:** §5.10 (reports) + PRD "owner-side revenue lines". We already compute over-assessment status, gap, and estimated savings at the 1.3998% rate with comps behind it (`assessment` module); the fpdf2 renderer exists (ADR-0021).

**Spec:**
- New dossier variant: "Assessment Review Packet" — assessed vs market estimate, comp table with distances/dates, gap math, savings estimate, sources, and appeal-process pointers (OPA First-Level Review / BRT deadlines).
- $79 one-time Stripe checkout (any tier, including Free — this is the homeowner on-ramp); Investor gets 1/mo included via the credit ledger (`reason='appeal_packet_grant'`).
- Fulfillment webhook → generate + email PDF + in-app download.
- Copy discipline: "informational, not tax or legal advice" (existing pattern); no outcome guarantees.
- Marketing hook (non-product): reassessment-cycle waves; a free "am I over-assessed?" check is the lead magnet — the check is already free in-product.

**Success metric:** ≥3% conversion from assessment-panel views showing `over_assessed` to purchase during a reassessment window.

### A6 — Owner-intent signals: tenure + tired-landlord *(Differentiator · P1)*

**Extends:** the distress index (ADR-0015) with two computable-today dimensions. Distress index bumps to **v2**.

**Spec:**
- **Tenure:** years since last arm's-length deed = `now() - max(sale.sale_date)` per parcel. Long-tenure + absentee is a classic seller signal. Proposed weight: `long_tenure` (≥15 yrs) **+5**, only when combined with absentee.
- **Tired landlord:** join `parcel.owner_key` → portfolio → aggregate open `li_event` violations and delinquency across the portfolio. Proposed: `portfolio_distress` **+10** when owner holds ≥3 parcels with ≥5 open violations portfolio-wide. Computed in the nightly `recompute_distress` job (owner-level aggregation once, fanned out to parcels).
- Cap stays 100; tier thresholds (60/30) unchanged; new factors appear in `DistressPanel` and lead `top_factors`.
- ADR records the weight rationale (Nygard), consistent with how ADR-0015 documented the original weights.

**Success metric:** lead-list CTR (open-parcel rate) improves ≥15% vs v1 scoring on the same cohort.

### A7 — Assemblage Top Plays *(Differentiator · P1)*

**Extends:** §5.2 from per-parcel on-demand to a ranked citywide feed. Genuinely novel vs incumbents; pure PostGIS on logic we've already written (ADR-0013/0014).

**Spec:**
- Nightly job precomputes `parcel_assemblage(parcel_number PK, potential, candidate_count, combined_lot_area_sqft, by_right_units_current, by_right_units_combined, unit_unlock, computed_at)` for vacant parcels with ≥1 candidate. Batched like verdict jobs (500/chunk).
- Ranking: `unit_unlock DESC`, tie-break combined area; filterable by zoning class and neighborhood.
- API: `GET /assemblage/top?neighborhood=&zoning=&limit=`; each row deep-links to the dossier with the assemblage layer pre-lit (existing purple highlight machinery in `MapView`).
- Frontend: "Top plays" tab or sidebar item (Pro+); in redesign IA, scoped to active market.

**Success metric:** feature used by ≥20% of Pro+ monthly; produces ≥1 organic social/community share per month (this is the demo-candy feature).

---

## 4. New features — Hardening (protect conversion)

### A8 — Zoning overlays & RCO surfacing *(Core gap · P1 — this is existing PRD §5.3 scope, never built)*

The largest credibility hole for the developer persona: a "buildable by-right" verdict that misses an NCO/overlay district gets caught fast and costs trust.

**Spec:**
- New loader: Philadelphia zoning **overlay** districts (OpenDataPhilly/ArcGIS — same transport as existing ArcGIS loaders). Table `zoning_overlay(id, external_id, code, name, geom_2272, geom_4326)`.
- Parcel resolution: centroid `ST_Contains` (same pattern as districts/historic).
- Verdict integration: `overlay_district` risk flag (severity **low**, info-grade like `historic_district`) listing overlay names; buildability `reasons` gains "Parcel is in overlay X — check Title 14 §14-500 series for modified standards." We do **not** attempt to model overlay dimensional overrides in v1 of this feature — surfacing + citation only; modeling is a follow-up ADR.
- RCO boundaries: same loader family; surfaced on the dossier as "RCO: <name> — community meeting required for variances" (feeds §5.5 diligence and the checklist `overlays` category, which exists).
- **Verdict version bumps to v6** (recompute sweep required — same playbook as v5/historic; `get_or_compute_current_verdict` handles lazy migration, full sweep via `make recompute-verdicts`).

### A9 — Abatement & exemption ingestion *(Deal-math gap · P1)*

**Extends:** §5.4. OPA carries exemption fields (`exempt_building`, `exempt_land`) the loader currently drops; abatement status materially changes developer math and is a first-question item.

**Spec:** add fields to `parcel` + OPA loader mapping; surface in `PropertyFacts`; deal engine `reasons` note when an active abatement is detected; checklist `liens_taxes` item. No verdict version bump (informational).

### A10 — Comp hygiene: related-party exclusion *(Accuracy · P2, cheap)*

RTT filter (deed-type + consideration > 0 + $1,000 floor + date) still admits intra-family transfers, dragging the AVM down.

**Spec:** in `find_comps`, exclude sales where grantor/grantee share a surname token (normalized: strip suffixes, uppercase, token overlap on tokens ≥3 chars). Guarded by the existing IQR trim, so impact is incremental; property-test with known family-transfer fixtures. Excluded count appears in valuation `reasons` for transparency.

### A11 — Vacancy confidence cross-check *(Accuracy · P2, cheap)*

VPI has known false positives — "that lot has a house on it" is the most embarrassing demo failure.

**Spec:** boost/attenuate `parcel.vacancy_confidence` (field exists) using corroboration: L&I vacancy-code violations and demolition events raise it; recent building permits or improvement value ≫ land value lower it. Rules documented in the ADR; `is_vacant` display unchanged, but sub-threshold confidence adds a "low confidence" qualifier to the Vacant chip tooltip.

---

## 5. Data & infrastructure prerequisites

### D1 — Raw landing layer becomes a product dependency *(P0)*

The endorsed ELT direction (raw landing → staging schema contract → merge) is now **required** by A2 (deltas) and strongly serves A4/A6/A8. The ADR-0004 note that "raw capture is deferred" is superseded: raw capture + staged merge with event emission is the next infrastructure slice. Two previously-open decisions are resolved by this amendment's needs:
- **Where normalization lives:** in the merge step (staging → core), so event emission sees both sides.
- **Staging schema vs separate DB:** staging **schema** in the same Postgres — event emission and merge need transactional access to core tables.

### D2 — New datasets (register in `data-sources.md`)

| Dataset | Source | Transport | Feeds |
|---|---|---|---|
| Sheriff sale lists (tax + mortgage) | Philly Sheriff's Office | scrape/CSV | A4, A2 |
| Zoning overlays | OpenDataPhilly | ArcGIS | A8 |
| RCO boundaries | OpenDataPhilly | ArcGIS | A8 |
| OPA exemption fields | existing OPA dataset | Carto (loader fields) | A9 |
| Skip-trace provider | BatchData / Endato | REST (paid) | A1 |

### D3 — New tables

`credit_ledger`, `skiptrace_result`, `parcel_event`, `sheriff_sale`, `zoning_overlay` (+ RCO), `parcel_assemblage`; `parcel` gains exemption fields. All with the standard mixins where applicable; Alembic migrations per slice.

---

## 6. Sequencing

Respects the solo-dev / Claude Code slice workflow and the in-flight frontend redesign (slices 2–6). Ordering optimizes revenue attach per unit of work; each phase is shippable alone.

| Phase | Contents | Rationale |
|---|---|---|
| **0 (days)** | Pricing catalog → $99/$249, Investor tier plumbing; A10 comp hygiene; A11 vacancy confidence; A9 abatement fields | Small, immediate; fixes the $29 anchor before any marketing push |
| **1** | A3 export; A1 skip-trace credits (ledger + provider + packs) | The two features that convert wholesalers; no infra dependency |
| **2** | D1 raw landing layer + staged merge | Infrastructure slice; also the ADR-0004 follow-up already planned |
| **3** | A2 Deal Feed (events, API, page, Investor email) | The retention engine; lands right after its dependency |
| **4** | A4 sheriff calendar; A6 distress v2 | Deepens the lead product |
| **5** | A8 overlays/RCO → verdict v6 sweep; A7 assemblage top plays | Developer-persona credibility + demo candy |
| **6** | A5 appeal packet SKU | Independent; can be pulled earlier if a reassessment window approaches |

Frontend redesign interaction: A2/A4/A7 each want a sidebar destination — specify their nav slots in the redesign docs now (cheap), build the pages in their phases.

---

## 7. Non-goals (this amendment)

Two-sided buyer marketplace; CV lot-condition scoring; CRM/dialer functionality beyond export + skip trace; offer/LOI generation (stays deferred per §5.9/§5.11); multi-city expansion (separate track — Harrisburg pilot spec unaffected); modeling overlay dimensional overrides in the buildability engine (surface-and-cite only, per A8).

## 8. Success metrics (roll-up)

- **ARPU:** ≥ $130 blended across paying users within 2 quarters of Phase 4 (subscription + credits + SKUs).
- **Conversion:** Free→paid ≥ 4% with the new gates (exports, feed, calendar as the visible upgrade walls).
- **Retention:** logo churn ≤ 4%/mo among feed-active users.
- **Credit economics:** ≥ 60% gross margin on skip trace after caching.
- **Accuracy guardrail:** zero verdict-credibility regressions — A8/A10/A11 exist to make the demo unloseable.

## 9. Open questions (to resolve in feature ADRs)

1. Skip-trace provider selection and contract terms (A1 ADR).
2. Sheriff list acquisition mechanics and stability of the source format (A4 ADR).
3. Grandfathering window and comms for existing $29 Pro subscribers (pricing ADR).
4. Whether Deal Feed events should also emit web push (ADR-0019 infra exists) or stay in-app + email for v1.
5. `parcel_event` retention beyond 18 months once it becomes the historical-analytics moat (storage vs value).
