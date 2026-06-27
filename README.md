# LotScope PHL

**Philadelphia vacant-land & infill-lot intelligence.** One screen that tells investors, builders, agents, and owners what can be built on any Philadelphia vacant lot, what it's worth, and what's wrong with it — with the reasoning shown and the sources cited.

> **Status:** Early development. Interfaces and data contracts are unstable.

---

## Overview

LotScope turns Philadelphia's open property data — parcels, assessments, recorded sales, zoning, L&I, demolitions, tax delinquency, the Land Bank, and the city's vacancy model — into a single, decision-ready answer per parcel: the **Parcel Verdict**. The product is Philadelphia-only by design; depth in one market is the moat.

The full product specification is in [`docs/LotScope-PHL-Full-PRD.md.pdf`](docs/LotScope-PHL-Full-PRD.md.pdf).

### What it does

- **Map & discovery** — every parcel, vacant-lot layer, rich filters, and search.
- **Developability** — by-right zoning envelope (RSA/RM/CMX), variance likelihood, buildable area.
- **Valuation** — confidence-scored estimates from real recorded comps.
- **Risk & due diligence** — liens, tax delinquency, sheriff-sale risk, L&I/demolition, Land Bank ownership, flood, title flags.
- **Ask the Parcel** — grounded, cited, plain-English Q&A over the zoning code and recorded documents.

---

## Tech Stack

| Layer | Choice |
|---|---|
| Backend | Python 3.12+, FastAPI (async), Pydantic v2 |
| Data | PostgreSQL 16 + PostGIS 3.4 + pgvector, SQLAlchemy 2.0 (async) + GeoAlchemy2, Alembic |
| Search | Elasticsearch |
| Jobs / cache | Redis + ARQ |
| Tiles | Martin (vector tiles from PostGIS) |
| AI | Anthropic Claude API + pgvector RAG |
| Frontend | Quasar (Vue 3, `<script setup>`, TypeScript strict), Pinia, MapLibre GL JS, Vite |
| Tooling | uv (Python deps), pnpm (frontend deps), Ruff, mypy, ESLint, Prettier, pytest, Vitest, Playwright |
| Dev / infra | Docker Compose (local), GitHub Actions (CI), AWS (prod) |

---

## Repository Structure

```
.
├── CLAUDE.md                   # how we build (conventions, workflow, rules)
├── README.md
├── docs/
│   ├── PRD.md                  # full product spec
│   ├── architecture.md
│   ├── data-sources.md         # Philly dataset catalog, endpoints, gotchas
│   └── adr/                    # architecture decision records
├── docker-compose.yml
├── .env.example
├── Makefile
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   └── src/lotscope/
│       ├── core/               # config, db, logging, errors, deps
│       ├── parcels/            # parcel model + service (the spine)
│       ├── zoning/             # district resolution + Title 14 + buildability
│       ├── valuation/          # comps + AVM
│       ├── risk/               # liens, title, L&I, flood, land bank flags
│       ├── verdict/            # composes engines -> Parcel Verdict
│       ├── ingestion/          # ETL: carto/arcgis clients, loaders, reconciliation
│       ├── search/             # Elasticsearch indexing + query
│       ├── ai/                 # Claude client, prompts, RAG, structured outputs
│       └── api/                # FastAPI routers (thin)
└── frontend/
    ├── package.json
    └── src/                    # pages, components, composables, stores, boot, lib
```

---

## Prerequisites

- **Docker** + **Docker Compose**
- **Python 3.12+** with [**uv**](https://docs.astral.sh/uv/)
- **Node 20+** with [**pnpm**](https://pnpm.io/)

---

## Quick Start

```bash
git clone <repo-url> lotscope-phl
cd lotscope-phl

# 1. Configure environment
cp .env.example .env
# Fill in values — at minimum ANTHROPIC_API_KEY and the datastore URLs.

# 2. Start infrastructure (Postgres+PostGIS+pgvector, Redis, Elasticsearch, Martin)
make up

# 3. Backend
cd backend
uv sync
make migrate            # apply database migrations

# 4. Frontend
cd ../frontend
pnpm install

# 5. Run the app (backend API + frontend dev server)
make dev
```

Then load Philadelphia data:

```bash
make ingest             # runs the ETL pipelines (chunked Carto + ArcGIS Hub loaders)
```

---

## Environment Variables

Copy `.env.example` to `.env` and set:

| Variable | Purpose |
|---|---|
| `APP_ENV` | `local` / `staging` / `production` |
| `DATABASE_URL` | `postgresql+asyncpg://user:pass@db:5432/lotscope` |
| `REDIS_URL` | `redis://redis:6379/0` |
| `ELASTICSEARCH_URL` | `http://elasticsearch:9200` |
| `MARTIN_URL` | Tile server base URL |
| `ANTHROPIC_API_KEY` | Claude API key (required for the AI layer) |
| `ANTHROPIC_MODEL` | Default model id for general tasks |
| `SECRET_KEY` | App/JWT signing secret |
| `REGRID_API_TOKEN` | Optional — only for coverage beyond city data / future expansion |
| `STRIPE_API_KEY` | Optional — billing (later phase) |

Never commit `.env`. Keep `.env.example` updated whenever a new variable is introduced.

---

## Common Commands

All workflows go through the `Makefile`:

| Command | Does |
|---|---|
| `make up` | Start all services via Docker Compose |
| `make down` | Stop all services |
| `make dev` | Run backend API + frontend dev server |
| `make migrate` | Apply Alembic migrations |
| `make ingest` | Run data ingestion pipelines |
| `make test` | Run the full test suite |
| `make lint` | Ruff + ESLint |
| `make fmt` | Format (Ruff + Prettier) |
| `make typecheck` | mypy + vue-tsc |
| `make e2e` | Playwright end-to-end tests |

---

## Testing

Testing is a hard requirement, not an afterthought (see `CLAUDE.md` §12). Core domain logic — zoning resolution, buildability, valuation, verdict composition, ingestion transforms, parcel-key reconciliation — is written test-first. Spatial logic is tested against real PostGIS (testcontainers); external services (Carto, ArcGIS, Anthropic) are mocked with recorded fixtures. CI enforces lint, type-check, and tests on every PR.

```bash
make test          # unit + integration
make e2e           # critical user flows
```

---

## Documentation

- [`docs/LotScope-PHL-Full-PRD.md.pdf`](docs/LotScope-PHL-Full-PRD.md.pdf) — full product specification and feature catalog
- [`docs/architecture.md`](docs/architecture.md) — system architecture
- [`docs/data-sources.md`](docs/data-sources.md) — Philadelphia dataset catalog, endpoints, schemas, and gotchas
- [`docs/adr/`](docs/adr/) — architecture decision records
- [`CLAUDE.md`](CLAUDE.md) — engineering conventions, workflow, and the rules the project is built under

---

## Conventions

Read [`CLAUDE.md`](CLAUDE.md) before contributing. Highlights:

- **No code comments or docstrings** except text consumed by an LLM at runtime (tool/schema descriptions, prompts).
- **Conventional Commits**, scoped by module (`feat(verdict): ...`).
- **Modular monolith** with strict boundaries — modules talk through service interfaces only.
- **Plan before building**; ask when ambiguous; smallest change that works.
- **Provenance on every derived datum** (source + computed-at).

---

## Data Sources & Attribution

LotScope is built primarily on the City of Philadelphia's open data (OpenDataPhilly / city ArcGIS Hub) and other public sources. This data is provided **"as is," without warranty**, and the City disclaims liability for its accuracy. LotScope surfaces source and freshness for every data point; users must perform their own due diligence. Any third-party data (e.g., Regrid) is used under its respective license.

---

## Disclaimer

LotScope provides **informational** analysis only. It is **not** legal, financial, real-estate, or appraisal advice, and its outputs (including AI-generated answers, valuations, and buildability assessments) are estimates that may contain errors. Verify zoning, title, tax, and buildability with the City of Philadelphia, a qualified attorney, and other professionals before making any decision.

---

## License

Proprietary — all rights reserved. (License terms TBD.)