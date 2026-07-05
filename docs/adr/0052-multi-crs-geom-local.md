# 52. Multi-CRS geometry: `geom_local` and the market-predicate rule

Date: 2026-07-05

## Status

Accepted

Implements PRD Amendment-02 workstream **B2**. (PRD calls this "ADR-0030".)

## Context

Eight spatial tables (`parcel`, `historic_district`, `neighborhood`, `street_centerline`, `zoning_district`, `zoning_overlay`, `rco`, `flood_zone`) each declare `geom_2272` (SRID 2272, PA South, US ft, `spatial_index=True`) plus `geom_4326` for tiles; every table has a GiST index on **both** columns. All engine math is feet-denominated on `geom_2272`: adjacency `ST_DWithin(..., 2.0)`, 75 ft street access, `ST_Buffer(geom_2272, -inset)` envelope, 1,500 ft comps radius, 1,500 ft market-context radius. The B2 inventory catalogued **17 spatial queries** — 5 true cross-parcel joins (assemblage neighbors, comps, market-context, neighborhood-stats, subdivision-via-assemblage) and 12 parcel↔context intersects (flood, historic ×2, street access, zoning district contains, overlay ×2, rco, neighborhood contains ×2, envelope buffer). **None carries a market predicate today** (there is no `market_code` column yet — B1 adds it). The Martin MVT functions (`parcels_mvt`, `vacant_lots_mvt`) operate on `geom_4326` only; area/buy-box search uses `geom_4326::geography` in **meters**.

Other markets are not all SRID 2272: Philadelphia/Harrisburg/Pittsburgh are (PA South), but Baltimore is EPSG:2248, and MI/WI/OH have their own foot-based state planes. Mixed-SRID rows must never meet in one `ST_DWithin`.

## Decision

**Rename `geom_2272` → `geom_local` with the SRID constraint relaxed to accept per-row SRIDs, hold the invariant "`geom_local` is always a foot-denominated plane", and require a `market_code` predicate on every cross-parcel spatial query.**

- **Column rename + typmod relax** (Alembic, `feat/expansion-b2-geom-local`): rename to `geom_local` and relax the SRID typmod (typed `Geometry(geometry_type="GEOMETRY", srid=0)` / drop the SRID check) so the column holds each market's local plane. Preserve or rebuild the GiST indexes — the PR body states which (a plain column rename keeps the index; a typmod change via `USING` rebuilds it). **All existing rows stay SRID 2272; no data transform.** `geom_4326` is unchanged.
- **The invariant keeps engine math untouched**: because every `local_srid` is a *foot* plane, all feet constants (`2.0`, `75.0`, `1500.0`, buffer insets) remain literal and correct. `market.local_srid` records each market's EPSG; ingestion derives `geom_local` via `ST_Transform(geom, market.local_srid)` — for `phl` this is a no-op by construction.
- **Market-predicate rule (the one real rule this creates)**: every cross-parcel spatial query gains a `market_code` join/predicate, both for correctness (mixed-SRID rows must never meet in one `ST_DWithin`/`ST_Intersects`) and index selectivity. The B2 inventory's 17-query checklist is worked through and checked off in the Slice-2 PR body.
- **Enforced by a synthetic two-market isolation test** (the Phase-P keystone, runs in CI from now on): plant a fake `zzz` market whose parcels sit at coordinates that would collide with Philadelphia if the predicate were missing; assert comps, assemblage neighbors, street access, and area search never cross markets, and that a `zzz` parcel's verdict computes without touching `phl` data.

## Consequences

- **Ships as a rename with zero behavioral change through Wave 1** (Philadelphia, Harrisburg, Pittsburgh are all 2272); B2 fires for real at Baltimore (2248). Golden-parcel verdicts are asserted unchanged.
- The distance-unit contract is preserved per query: `geom_local` queries stay in feet; the `geom_4326::geography` area search stays in meters (`MAX_RADIUS_M`). Any future change must not conflate them.
- MI/WI/OH EPSGs (and Michigan's international-foot vs US-survey-foot sub-inch nuance) are pinned in each wave's kickoff ADR, not here.
- A missed market predicate silently leaks cross-market data; the synthetic-market test is the standing guard, and every new cross-parcel spatial query must add the predicate + a test assertion.
