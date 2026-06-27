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
   │ PostgreSQL 16 + PostGIS + pgvector  │ Elasticsearch │ Redis │
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
- **Elasticsearch** — address / owner / parcel search.
- **Redis** — cache + ARQ job broker.
- **S3** (prod) — recorded documents and imagery feeding the OCR/RAG pipeline.

## Cross-cutting principles

- **Provenance everywhere.** Every derived datum records its source(s) and a computed-at timestamp.
- **Never trust upstream.** City/third-party data is parsed and validated defensively; ingestion is idempotent and restartable.
- **Pure core, isolated side effects.** Domain computation is deterministic and testable; DB/HTTP/LLM access lives in thin adapters at module edges.
- **Grounded AI.** Zoning/legal/value answers are retrieved-and-cited, schema-validated, and confidence-scored — never answered from parametric memory.

## Local development

`make up` starts infrastructure (Postgres, Redis, Elasticsearch, Martin). `make dev` runs the API locally against it. See [`adr/0002-scaffold-stack-and-local-infra.md`](adr/0002-scaffold-stack-and-local-infra.md) for the concrete image and topology choices.
