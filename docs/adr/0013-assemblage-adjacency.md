# 13. Assemblage (adjacent-lot) radar

Date: 2026-06-28

## Status

Accepted

## Context

PRD §5.2 ("Adjacent parcels & assemblage") and §5.3 ("Subdivision / consolidation potential"): a developer looking at a lot wants to know whether the neighbors can be bought to build a wider, more profitable project. Nothing in the platform surfaced spatial neighbors or scored the assemblage opportunity. This is a new analytical concern that reads parcel geometry and attributes.

## Decision

**A new `assemblage` engine** — an independent module that, given a parcel, finds spatially adjacent lots and scores the assemblage opportunity. It follows the established engine pattern (`risk`, `zoning`): pure, tested logic plus a thin service that queries the `parcel` table directly; it does not reach into other modules.

- **Adjacency** is `ST_DWithin(geom_2272, geom_2272, 2.0)` — neighbors within 2 ft, in EPSG:2272 (feet). A small tolerance (not strict `ST_Touches`) is deliberate: PWD parcel polygons have slivers and gaps, so exact-touch misses real neighbors. `shared_boundary_ft` is computed (`ST_Length(ST_CollectionExtract(ST_Intersection(...), 2))`) for ranking; corner-only neighbors rank last.
- **Acquirability** per neighbor, in priority order: `same_owner` (already controlled / single-seller) → `city_owned` (public disposition) → `vacant` (likely acquirable) → `built` (hard).
- **A "candidate"** is an adjacent lot with the **same base zoning** *and* an acquirable status. Combined dimensions and the potential score are computed from candidates only; non-candidate neighbors are still listed for context.
- **Potential**: `high` if any candidate is same-owner/city-owned (clear acquisition path) or there are ≥2 candidates; `medium` for a single vacant candidate; `none` otherwise.
- **Exposed** at `GET /parcels/{id}/assemblage` (auth, like verdict/envelope; on-demand, not precomputed). The frontend auto-loads it on selection, lists neighbors with acquirability badges, and draws the candidates on the map as a dashed-outline "radar" colored by acquirability.

## Consequences

- **Combined dimensions are approximate.** Combined area sums target + candidate lot areas (sound). Combined frontage sums frontages, which is only correct for side-by-side lots — we don't infer parcel orientation in v1, so it is labeled approximate and the UI leads with combined area.
- **Combined by-right units** are estimated for districts with area-based density (ADR-0014): the summary exposes `by_right_units_current` vs `by_right_units_combined` and the panel shows "1 → N units." FAR-governed districts still report combined land only, since unit count there is design-dependent.
- The 2 ft tolerance can include corner-touching or across-narrow-gap parcels; they are ranked last by shared boundary and rarely matter. Tightening this is a tuning follow-up.
- On-demand spatial query per parcel; fast via the GiST index on `geom_2272`. Capped at 16 neighbors.
