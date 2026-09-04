# Architecture

A modular monolith serving **Philadelphia only**: one FastAPI backend of domain
modules talking through each other's `service.py`, one Quasar frontend, one
Postgres. `core/market.py` holds the four constants that used to be a registry —
`MARKET_CODE`, `MARKET_NAME`, `CRS_ANALYSIS`, `CRS_TILES`.

```
Quasar ──HTTPS──► FastAPI (api/) ──► domain services ──► Postgres 16 + PostGIS
   └───tiles───► Martin ──────────────────────────────► + pgvector + pg_trgm
ingestion/ (ARQ, nightly) ─────────► Postgres    Redis: cache + job broker
```

## Modules

Dependency runs inward toward `core/`; a module may use another module's
`service.py`, never its `models.py` or internals.

- `core/` — config, engine/session, logging, typed errors, deps, market constants
- `parcels/` — the spine: identity, geometry, context others read
- `zoning/` `valuation/` `risk/` `distress/` — engines returning sourced results
- `verdict/` — composes them into the Parcel Verdict; sole owner of that contract
- `deal/` `assemblage/` `checklist/` `subdivision/` — underwriting reads over those
- `ingestion/` — Carto/ArcGIS/CivilView loaders, key reconciliation, freshness
- `search/` `ai/` `provisions/` — services for `api/`; they own no domain truth
- `api/` — thin routers composing services
- accounts: `accounts/` `watchlist/` `pipeline/` `savedsearch/` `outreach/` `skiptrace/` `notifications/`; ops: `ops/` `admin/` `corrections/`

## Data

Analysis geometry **EPSG:2272** (feet), tiles **EPSG:4326**, GiST on all
geometry. pgvector holds RAG embeddings; `pg_trgm` plus full text does
address/owner/parcel search — no separate search engine. Martin serves
`parcels_mvt` and `vacant_lots_mvt` from PostGIS, introspecting at startup.

`market_code` survives as a column holding `"phl"`: it scopes rows in SQL, and no
code branches on its value. The one-row `market` table is retained, read only by
`deal/service.py`'s assumption-override path. Every derived datum carries its
source, a source URL where one exists, and a computed-at or fetched-at
timestamp; zoning and legal answers are retrieved and cited, never recalled.
