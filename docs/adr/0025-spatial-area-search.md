# 25. Spatial area search (radius + polygon)

Date: 2026-06-29

## Status

Accepted

## Context

PRD §5.1 lists **draw / radius / neighborhood search** (Core): find parcels within a drawn polygon, a radius, or a named neighborhood/RCO. Parcels already carry `geom_4326`, so PostGIS can answer these directly. The three variants differ sharply in cost: radius needs nothing new; freehand polygon drawing needs a new frontend map-draw dependency; named-neighborhood search needs a neighborhood/RCO boundary layer that is not yet ingested.

## Decision

**Ship radius search end-to-end now; build the polygon query on the backend but defer the two variants that require a new dependency or data source.**

- A single `POST /search/area` endpoint accepts **either** `center + radius_m` **or** a GeoJSON `polygon` (validated mutually exclusive by the request schema), plus optional `vacant_only` / `zoning_codes` filters and a capped `limit`.
- Radius uses `ST_DWithin(geom_4326::geography, point, radius_m)` ordered by true geodesic `ST_Distance`; polygon uses `ST_Intersects(geom_4326, ST_GeomFromGeoJSON(...))`. All inputs are parametrized; the WHERE builder is pure and unit-tested, and the spatial behavior is integration-tested against real PostGIS geometries.
- Each result carries a representative point (`ST_PointOnSurface`) so the frontend can list and locate matches. Radius is server-clamped to a max; result count is capped and surfaced via `truncated`.
- Frontend: a "Search this area" map mode (click to set center, radius slider) renders the radius as a **generated GeoJSON circle** and highlights matched parcels on the existing vector-tile source — **no new dependency**. The polygon endpoint is ready for a future draw UI.

## Consequences

- **Radius search is complete and dependency-free.** The polygon endpoint is exercised by tests and usable by API clients today, even though no freehand-draw UI ships yet.
- **Freehand polygon drawing is deferred** — it needs a map-draw library (e.g. mapbox-gl-draw / terra-draw), a dependency addition to confirm before adding (§2/§15).
- **Named-neighborhood search is deferred** — it needs a new ingestion loader for the Philadelphia neighborhood/RCO boundary layer (ArcGIS Hub); once that table exists, "search by neighborhood" becomes a point-in-polygon lookup that reuses this same endpoint.
- Area search respects the map's `vacant_only` filter at query time; it does not yet re-run automatically when that toggle flips on an already-placed circle (the next center/radius change picks it up). A minor follow-up.
- The search module stays self-contained; it reads parcel/verdict state via SQL and owns no domain truth.
