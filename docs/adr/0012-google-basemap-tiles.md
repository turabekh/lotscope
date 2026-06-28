# 12. Google Map Tiles basemap

Date: 2026-06-28

## Status

Accepted

## Context

The map shipped on free OpenStreetMap raster tiles. We want Google **satellite** (and roadmap) imagery as the backdrop — it pairs well with the 3D buildable-envelope extrusion (ADR-0011). The operator has a Google Maps Platform key. Two constraints shaped the decision:

- **MapLibre cannot render Google's Photorealistic 3D Tiles** (3D Tiles / Cesium format). Only Google's **Map Tiles API 2D raster** tiles work as a MapLibre raster source. A photorealistic "Google Earth" mode would require a second renderer (CesiumJS/deck.gl) and is out of scope.
- A browser-rendered map must reference the tile URL (and therefore the API key) from the client. There is no way to fully hide the key without proxying every tile through our backend, which is wasteful.

## Decision

**Google Map Tiles API (2D raster) as a switchable basemap, with OSM retained as a fallback.**

- **Session tokens are minted server-side.** `GET /maps/basemap-session?map_type=satellite|roadmap` calls Google `createSession` using `GOOGLE_MAPS_API_KEY` (backend settings, never in the frontend bundle) and returns the tile URL template, attribution, and tile size. The Google access is centralized in `tiles/google.py` behind a mockable async adapter.
- **The returned tile URL contains the key**, so the key reaches the browser at runtime (the same as any client-rendered Google map). It must be **restricted by HTTP referrer** and scoped to the Map Tiles API in the Google Cloud console. It is never committed to the repo or the bundle.
- **Client switcher:** Satellite (default) / Roadmap / Streets (OSM). The base raster source is swapped under the parcel layers; OSM needs no key. If the session request fails (no key, quota, misconfig), the map silently falls back to OSM, so the app never breaks.
- Tiles are requested only for the selected basemap, so Google quota is consumed only when a Google base is active.

## Consequences

- The key is runtime-visible in the browser network tab; referrer restriction is the control. Acceptable and standard for client-rendered Google maps.
- Google Maps Platform billing/quota applies to Map Tiles usage; OSM is the zero-cost default-able fallback.
- **Attribution is per-viewport.** `GET /maps/attribution` proxies Google's `tile/v1/viewport` endpoint (a different base path from createSession/tiles) and returns the `copyright` string for the current bounds + zoom; the map updates it on a debounced `moveend`. The displayed text is rendered in a custom overlay (the default MapLibre attribution control is disabled), with OSM attribution shown for the OSM basemap.
- **Session tokens are cached in Redis** (`gmaps:session:{map_type}`) with a TTL derived from Google's `expiry` minus a safety buffer, so createSession is called at most once per validity window rather than per request. Cache failures fall back to minting fresh (fail-open).
- **Deferred:** photorealistic 3D (Cesium/deck.gl) and a tile-proxy option for full key hiding.
