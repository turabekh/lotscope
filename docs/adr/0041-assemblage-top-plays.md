# 41. Assemblage Top Plays

Date: 2026-07-03

## Status

Accepted

Gates PRD-amendment-01 feature **A7** (Phase 5). Promotes the existing on-demand assemblage engine (ADR-0013/0014) into a nightly-precomputed, ranked citywide feed. Sibling of ADR-0040 (A8, same phase).

## Context

We already compute assemblage **per parcel, on demand**: the `assemblage` module finds adjacent candidate lots (same-zoning + acquirable via same-owner / city-owned / vacant), sums the combined lot area, and estimates by-right units current vs combined — all pure PostGIS + the zoning density logic we've written. What we've never done is ask the inverse, citywide question a wholesaler actually wants: *"where in Philadelphia does buying the lot next door unlock the most units?"* That is genuinely novel versus PropStream/BatchLeads (none of them reason about by-right density), and it's the amendment's designated **demo-candy** feature. The only thing missing is **precomputation, ranking, and a feed surface** — no new spatial logic.

The blocker to doing it live is cost: the neighbor query is per-parcel spatial work, too slow to rank citywide on request. The verdict/distress engines already solved this shape — a nightly batched job that upserts a precomputed table read cheaply by an API.

## Decision

**Precompute assemblage nightly into a `parcel_assemblage` table for vacant parcels with ≥1 candidate, and serve a Pro+ ranked feed over it — reusing `compute_assemblage` verbatim and the verdict batch-job template.**

### Table

`parcel_assemblage(parcel_number PK → parcel, potential, candidate_count, combined_lot_area_sqft, by_right_units_current, by_right_units_combined, unit_unlock, computed_at)` + standard mixins — mirroring `ParcelVerdict`. `unit_unlock = by_right_units_combined − by_right_units_current` is stored (not derived at query time) so it can be the ranking key with an index.

### Nightly job

`assemblage/jobs.py` clones `verdict/jobs.py`: page **vacant parcels with geometry** (the amendment's scope — `is_vacant IS TRUE AND geom_2272 IS NOT NULL`), chunk **500**, call the existing `compute_assemblage(session, parcel_number)` per parcel, and **upsert only rows with `candidate_count ≥ 1`** (parcels with no assemblage play are not stored — the feed is plays, not all parcels). Wired into `worker.py` as a nightly `cron` and a `make recompute-assemblage` target, exactly like verdict/distress.

### API

`GET /assemblage/top?neighborhood=&zoning=&limit=` (Pro+ gated via a `top_plays_access` tier check, reusing `FEED_TIERS`). Ranking: **`unit_unlock DESC`, tie-break `combined_lot_area_sqft DESC`**. Filters join `parcel` for `base_zoning_code` (zoning class) and resolve neighborhood via the existing neighborhood mechanism; both optional, built into the `WHERE` dynamically (the `find_leads` idiom). Thin router over a service returning `AssemblageTopPlay` rows (parcel_number, address, potential, candidate_count, combined area, units current/combined, unit_unlock).

### Frontend

A Pro+ **"Top plays"** sidebar item → `/:market/top-plays` page (mirroring the Feed/Sheriff pages: tier gate + upgrade card + filters + ranked list). Each row deep-links to the parcel dossier (`{name:'parcel', params:{market, id}}`); the existing `stores/parcel.select → loadAssemblage → MapView.applyAssemblage` chain **pre-lights the purple candidate layer** with zero new map code.

### Rollout (slices, each tested + committed)

1. This ADR.
2. **Table + job** — `ParcelAssemblage` model (registered in `models.py`) + migration; `assemblage/jobs.py` (recompute-all → chunk → `compute_assemblage` → upsert, candidate-gated); worker cron + `make recompute-assemblage`. Job test mirrors `verdict/tests/test_jobs.py`.
3. **API** — `GET /assemblage/top` service + schema + thin Pro+ router; tests (gate 429, ranking by unit_unlock, zoning/neighborhood filters).
4. **Frontend** — Top Plays page + sidebar + `api.getTopPlays` + types; api-client test.

## Consequences

- **A novel, shareable feed ships on logic we already trust.** No new spatial code — `compute_assemblage` is the single source of truth for both the live dossier panel and the ranked feed, so they can't disagree.
- **Freshness is nightly, and that's fine.** Assemblage inputs (parcels, zoning, vacancy) change slowly; a stale-by-a-day top-plays list is acceptable, and the dossier still computes live on click.
- **Storage is bounded to plays.** Only vacant parcels with ≥1 candidate are persisted, a small fraction of the parcel base; the table stays small and the ranked read is a single indexed scan.
- **Cost is one batched job + one table + one endpoint + one page** — every piece a clone of an existing, tested pattern (verdict job, leads/feed router, feed page, MapView assemblage layer). No verdict-version impact (assemblage is independent of the verdict contract).
- **Deferred:** owner-level assemblage (multiple non-adjacent lots), cross-zoning plays, and any assemblage weighting into the distress/verdict scores — all out of scope for a ranked-feed v1.
