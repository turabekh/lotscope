# 11. Buildable envelope extrusion

Date: 2026-06-28

## Status

Accepted

## Context

Users want a quick visual sense of the by-right massing on a lot — the 3D volume you could build. The zoning engine (ADR-0006) already resolves a parcel's district, setbacks, and `max_height_ft`, but the buildable area it reports is computed analytically (net width × depth) and there is no buildable-footprint polygon to render. We want a "core" 3D envelope check on the map without a new tile pipeline.

## Decision

**Serve a per-parcel buildable envelope and render it client-side as a MapLibre `fill-extrusion`.**

- **Geometry:** the buildable footprint is the real PWD parcel polygon inset by setbacks via `ST_Buffer(geom_2272, -inset)`. Geometry is stored in EPSG:2272 (US feet), so the inset distance is applied directly in feet with no reprojection. The result is transformed to 4326 for the map.
- **Inset is a single representative distance** — the mean of the district's present front/side/rear setbacks. A uniform negative buffer cannot honor different per-edge setbacks, so this is explicitly **approximate** and labeled informational in the response `reasons` and the UI. Per-edge insets (which need street-frontage orientation detection) are a deferred follow-up.
- **Degenerate lots:** if the inset collapses the footprint (buildable area < 5% of lot area), we fall back to the full footprint with `applied_setback_ft = 0` and a reason explaining why.
- **Height:** extrusion height = `max_height_ft` (converted to meters client-side); estimated floors = `floor(height / 10.5 ft)`. When no height standard is loaded, `available = false` and the lot is shown as a flat outline only.
- **Endpoint:** `GET /parcels/{id}/envelope` (auth required, same as verdict/comps; it does not consume the free parcel-view quota — that is charged once on parcel detail). Returns lot footprint, buildable footprint, height, floors, applied setback, and **provenance + computed_at** on the derived geometry (golden rule 6).
- **Client:** a "3D building envelope" toggle fetches the selected parcel's envelope, feeds a GeoJSON source, tilts the camera, and extrudes the buildable footprint. Selected-parcel only — no citywide 3D layer and no change to the MVT tiles.

## Consequences

- The envelope is a **guidance massing, not a permit-grade buildable volume**: uniform inset, no floor-area-ratio / open-area / bulk-plane / overlay constraints, no height bonuses. The UI frames it as approximate and informational, consistent with the advice-layer framing (ADR-0008, §13).
- No verdict-contract change and no new ingestion or tile work; the feature is additive and isolated to the `zoning` service plus one API route and the map view.
- **Deferred:** per-edge setbacks with frontage detection, FAR/open-area caps, overlay and special-district bulk rules, and a citywide extrusion layer (would require `max_height_ft` in the MVT tiles).
