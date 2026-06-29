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

- **Radius search is complete and dependency-free.**
- **Freehand polygon drawing is now implemented** (added after the initial radius slice, with the dependency confirmed): the frontend uses **terra-draw** with its MapLibre adapter (`terra-draw` + `terra-draw-maplibre-gl-adapter`, pinned) — chosen over `mapbox-gl-draw` for being TypeScript-native and map-library-agnostic via adapters. A shape toggle switches the "Search this area" mode between radius and polygon; the drawn polygon's geometry is sent to the existing `POST /search/area` polygon path. terra-draw is started/stopped with the mode so it never intercepts clicks during radius mode.
- **Named-neighborhood search is now implemented** (added after radius/polygon): a `neighborhood` table is populated by a new ArcGIS ingestion loader from the City's `Philadelphia_Neighborhoods` feature service (name field `id`, key `ObjectId`). `POST /search/area` gained a third mutually-exclusive shape, `neighborhood`, resolved by `ST_Intersects(parcel.geom_4326, (SELECT ST_Union(geom_4326) FROM neighborhood WHERE name = :name))`; `GET /neighborhoods` lists names for the frontend dropdown. The "Search this area" panel gained an "Area" mode with a typeahead neighborhood select. Drawing the selected boundary outline on the map is a possible follow-up; today the matched parcels are highlighted.
- Area search respects the map's `vacant_only` filter at query time; it does not yet re-run automatically when that toggle flips on an already-placed circle (the next center/radius change picks it up). A minor follow-up.
- The search module stays self-contained; it reads parcel/verdict state via SQL and owns no domain truth.
