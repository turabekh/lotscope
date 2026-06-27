# Architecture

LotScope PHL is a **modular monolith**: one deployable backend composed of independent domain modules that communicate only through service interfaces. This document is the high-level map; cross-cutting decisions are recorded as ADRs in [`adr/`](adr/).

## System shape

```
        ┌────────────┐      ┌──────────────┐
        │  Frontend  │      │   Martin     │  vector tiles (4326)
        │  (Quasar)  │◄────►│ (PostGIS RO) │◄───────────────┐
        └─────┬──────┘      └──────────────┘                │
              │ HTTPS (JSON)                                 │
        ┌─────▼───────────────────────────────────────┐     │
        │                FastAPI (api/)                │     │
        │      thin routers → domain services          │     │
        └─────┬───────────────┬───────────────┬────────┘     │
              │               │               │              │
      ┌───────▼──────┐ ┌──────▼──────┐ ┌──────▼──────┐       │
      │ parcels      │ │ zoning      │ │ valuation   │  …    │
      │ (the spine)  │ │ risk verdict│ │ search  ai  │       │
      └───────┬──────┘ └──────┬──────┘ └──────┬──────┘       │
              │               │               │              │
   ┌──────────▼───────────────▼───────────────▼──────────────▼─┐
   │ PostgreSQL 16 + PostGIS + pgvector (+ pg_trgm)  │   Redis   │
   └────────────────────────────────────────────────────────────┘
              ▲
        ┌─────┴──────┐
        │ ingestion  │  scheduled ETL (Carto SQL, ArcGIS Hub, FEMA, DOR)
        │ (ARQ jobs) │
        └────────────┘
```

## Module boundaries

Dependency direction is inward toward `core/`. A module may depend on `core/` and on another module's `service.py` interface — never on another module's `models.py` or internal helpers.

- **`core/`** — config, async DB engine/session, structured logging, typed errors, shared FastAPI dependencies.
- **`parcels/`** — the spine; parcel identity, geometry, and context that other modules read.
- **`zoning/` · `valuation/` · `risk/`** — independent engines producing structured, provenance-bearing results.
- **`verdict/`** — composes the engines into the **Parcel Verdict**. Sole owner of the verdict contract (changes are ADR-level).
- **`ingestion/`** — raw + normalized loaders, parcel-key reconciliation, freshness tracking. No business logic beyond normalization.
- **`search/` · `ai/`** — services consumed by `api/`; they do not own domain truth.
- **`api/`** — thin glue: routers compose services, no business logic.

## Datastores

- **PostgreSQL 16 + PostGIS 3.4 + pgvector** — single primary datastore. Analysis geometry in **EPSG:2272** (feet); tile geometry in **EPSG:4326**. GiST indexes on all geometry. pgvector holds RAG embeddings.
- **PostgreSQL `pg_trgm`/full-text** — address / owner / parcel search (ADR-0005); no separate search service.
- **Redis** — cache + ARQ job broker.
- **S3** (prod) — recorded documents and imagery feeding the OCR/RAG pipeline.

## HTTP API

The FastAPI app is thin glue (§10) — routers compose services, no business
logic. Endpoints so far:

- `GET /health`, `GET /health/ready` — liveness and DB/Redis readiness.
- `GET /search?q=` — trigram parcel search (address/owner/parcel#).
- `GET /parcels/{id}` — parcel detail.
- `GET /parcels/{id}/verdict` — the stored Parcel Verdict (404 until computed).
- `POST /parcels/{id}/verdict/refresh` — compute/recompute and persist the verdict.
- `GET /parcels/{id}/comps` — comparable land sales + valuation.
- `GET /layers` — map layer metadata and Martin tile-URL templates.

Domain errors (`LotScopeError` subclasses) and request-validation errors map to
a single `ErrorResponse` schema (`{error, detail}`) with appropriate status codes.

## Map tiles

Vector tiles are served by **Martin** directly from PostGIS. Martin connects via
`DATABASE_URL` and auto-publishes the MVT **function sources** defined in a
migration:

- `parcels_mvt(z, x, y)` → layer `parcels` (parcel_number, address, is_vacant, base_zoning_code).
- `vacant_lots_mvt(z, x, y)` → layer `vacant_lots` (vacant parcels only).

Each function clips `parcel.geom_4326` (filtered through its GiST index via the
tile envelope), reprojects to Web Mercator, and emits MVT with `ST_AsMVT`.
Endpoints: `/{function}/{z}/{x}/{y}` (e.g. `/parcels_mvt/12/1196/1539`), with
TileJSON at `/{function}` and a source listing at `/catalog`. The frontend
(MapLibre) consumes these directly; the API does not proxy tiles.

Martin introspects the schema at startup, so run migrations before it (or
restart Martin after a migration that changes the tile functions).

## Cross-cutting principles

- **Provenance everywhere.** Every derived datum records its source(s) and a computed-at timestamp.
- **Never trust upstream.** City/third-party data is parsed and validated defensively; ingestion is idempotent and restartable.
- **Pure core, isolated side effects.** Domain computation is deterministic and testable; DB/HTTP/LLM access lives in thin adapters at module edges.
- **Grounded AI.** Zoning/legal/value answers are retrieved-and-cited, schema-validated, and confidence-scored — never answered from parametric memory.

## Local development

`make up` starts infrastructure (Postgres, Redis, Martin). `make dev` runs the API locally against it. See [`adr/0002-scaffold-stack-and-local-infra.md`](adr/0002-scaffold-stack-and-local-infra.md) for the concrete image and topology choices.
