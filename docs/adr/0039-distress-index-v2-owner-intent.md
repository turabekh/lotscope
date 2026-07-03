# 39. Distress index v2 — owner-intent signals

Date: 2026-07-03

## Status

Proposed

Gates PRD-amendment-01 feature **A6** (Phase 4). Extends ADR-0015 (motivated-seller distress index) with two owner-intent dimensions and bumps the scorer to **v2**. Reads the `sale` table (RTT comps) and `parcel.owner_key` (the reconciled owner identity used by the `owners` module).

## Context

The v1 distress index (ADR-0015) scores *property-level* distress — sheriff sale, delinquency, liens, L&I danger, vacancy, absentee ownership. It says nothing about **owner intent**: how long the owner has held the property, or whether the owner is a landlord drowning across a portfolio. Both are classic "likely to sell" signals the wholesaler persona pays PropStream/BatchLeads to surface, and both are **computable today** from data we already ingest — recorded deeds (`sale`) and the reconciled `owner_key`. A6 adds them and bumps the index to v2. The success bar is a ≥15% lift in lead-list open-rate versus v1 on the same cohort.

Two facts about the existing engine shape the decision:
- **The nightly recompute chunks parcels** (`recompute_all_distress` fans batches of ~1000 into `recompute_distress`). A per-parcel signal (tenure) fits that model directly; a **portfolio-wide** signal (tired landlord) does **not** — an owner's parcels can straddle chunk boundaries, so portfolio aggregation cannot live inside a single chunk.
- **`score_distress` is a pure function** and the single source of truth for both the live `GET /parcels/{id}/distress` and the batch job. New signals must enter through `DistressSignals`, not through SQL branching.

## Decision

**Add two factors to the pure `score_distress` (v2), gather their inputs from `sale` and an owner-level aggregation, and stamp the stored score with a version.**

### New factors (weights recorded here, per ADR-0015's precedent)

- **`long_tenure` (+5)** — `years_since_last_sale ≥ 15` **and** the owner is absentee. Gated on absentee deliberately: long tenure alone is common and weak; long tenure *by an out-of-area owner* is the seller signal. Modest weight, like v1's absentee heuristic.
- **`portfolio_distress` / tired landlord (+10)** — the owner holds **≥3 parcels** and has **≥5 open L&I violations across the whole portfolio**. A landlord bleeding violations across several properties is a motivated seller; weighted above tenure because it compounds real, current distress.

Cap stays **100**; tiers stay **high ≥60 / medium ≥30 / low >0**; **city/Land-Bank-owned still scores 0**. `DistressSignals` gains `years_since_last_sale: float | None` and `is_tired_landlord: bool`.

### Tenure input — recorded deeds

`years_since_last_sale = now − max(sale.sale_date)` over **recorded deed transfers** (`document_type ~ DEED`), joined per parcel in the existing bulk/live signals query. Deed-only is a pragmatic arm's-length proxy that keeps A6 self-contained; folding in the ADR-0032 related-party/nominal-consideration exclusion (to drop $1 intra-family quitclaims that spuriously reset tenure) is a **follow-up refinement**, noted so v2 tenure is not mistaken for hygiene-clean.

### Tired-landlord input — one owner-level pass, fanned out

Because the signal is portfolio-wide, it is computed **once per recompute run**, independent of chunking: a single `GROUP BY owner_key HAVING count(*) ≥ 3 AND sum(open_violations) ≥ 5` query (open = `event_type='violation' AND upper(status)='OPEN'`, matching the risk module) yields the set of "tired" `owner_key`s. That set is passed into `recompute_distress(chunk, tired_owner_keys)`; each parcel checks membership by its `owner_key`. The live per-parcel endpoint computes the one owner's portfolio on demand (a small `owner_key`-scoped query), so it stays fresh and fully explainable. Owners with a null `owner_key` never qualify.

### Versioning & provenance

Introduce `DISTRESS_VERSION = "v2"` in `distress.scoring` and add a **`version` column to `parcel_distress`** (written on upsert, carried on the live result) — mirroring `verdict_version`, satisfying Golden Rule 6 (every derived datum records provenance), and making a stale v1 row visible during rollout. A one-time full `recompute_distress` runs on deploy; the nightly cron self-heals thereafter.

### Surfaces

Both factors flow through `score_distress().factors`, so `DistressPanel` renders them with no change. `_lead_top_factors` (the separate, hand-picked lead summary list) is extended to include tired-landlord and long-tenure so they appear in lead `top_factors` and exports.

### Rollout (slices, each tested + committed)

1. This ADR.
2. **Scoring v2** — `score_distress` gains the two factors + `DISTRESS_VERSION`, written test-first (each factor's threshold, the absentee gate on tenure, cap/tier invariance, city-owned still 0). `version` column migration on `parcel_distress`.
3. **Signal gathering + job wiring** — extend the bulk/live signals SQL (`owner_key`, deed `max(sale_date)`), the tired-landlord owner-set query, thread both through `recompute_distress` and the live endpoint, extend `_lead_top_factors`, and recompute.

## Consequences

- **Lead quality improves where it's measurable.** Two orthogonal owner-intent signals enter the ranked list and the dossier without new ingestion — the amendment's "computable-today" bet. Scores can rise by up to +15 for a long-tenured absentee tired landlord, still capped at 100.
- **The chunking hazard is designed out.** Tired-landlord aggregation is a single pre-pass, not per-chunk, so portfolio counts are correct regardless of batch boundaries. This is the one place v2 could have silently under-counted; the ADR pins the approach and it is tested against an owner whose parcels straddle chunks.
- **Rollout needs a recompute.** v2 changes the meaning of the stored score, so every `parcel_distress` row is stale until recomputed; the `version` column makes that visible and the deploy-time recompute closes it. No verdict impact — the verdict does not read distress, so there is no verdict-version bump.
- **Tenure is a proxy, labeled as one.** Deed-only `max(sale_date)` can be reset by a non-arm's-length transfer; the factor label and this ADR say so, and the ADR-0032 hygiene refinement is the named follow-up.
- **Cost is contained.** All work is in `distress` (+ one owner-aggregation query reusing `owner_key`); one small migration; no new dependency, no new dataset, no contract change beyond adding a nullable column.
- **Deferred:** arm's-length hygiene on tenure (ADR-0032), any tenure/portfolio weights beyond the two above, and surfacing tenure as a standalone dossier chip.
