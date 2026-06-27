# 2. Scaffold stack and local infrastructure

Date: 2026-06-27

## Status

Accepted

## Context

Build-order step 1 (`CLAUDE.md` §11) is the scaffold: repository layout, the backend project, `core/` foundations, a runnable health-check API, local infrastructure, and the quality/CI gates. The stack is fixed by `CLAUDE.md` §2; this ADR records the concrete, non-obvious choices made while standing it up, and the boundaries of this first slice.

## Decision

**Backend project**
- `uv` workspace under `backend/`, Python pinned to **3.12** (the stack floor), `src/` layout, package built with hatchling.
- Quality gates: **Ruff** (lint + format), **mypy `strict`**, **pytest** + `pytest-asyncio` (auto mode). Generated Alembic migrations are excluded from Ruff.

**`core/` foundations**
- `Settings` via Pydantic Settings (env-backed, `.env` for local). Async SQLAlchemy 2.0 engine/session and a typed `DeclarativeBase`. Structured JSON logging via structlog. Typed domain exception hierarchy (`LotScopeError` + subclasses) mapped to HTTP status codes in the API layer.

**API**
- FastAPI app factory with a lifespan that owns the engine, session factory, and Redis client on `app.state`. Endpoints: `/health` (liveness, no I/O) and `/health/ready` (DB + Redis checks).

**Local infrastructure (`docker-compose.yml`)**
- **db** — custom image (`docker/postgres/Dockerfile`) extending official `postgis/postgis:16-3.4` plus the `postgresql-16-pgvector` package, because no single official image ships PostGIS **and** pgvector. An init script enables both extensions.
- **redis** — `redis:7-alpine`. **elasticsearch** — `8.13.4`, single-node, security disabled (local only). **martin** — `ghcr.io/maplibre/martin` reading PostGIS directly.
- `make up` starts **infrastructure only** (db, redis, elasticsearch, martin); `make dev` runs the API locally against it. The **api** container is defined behind a compose `app` profile for full-stack parity.

**Scope boundaries of this slice**
- **No database tables or migrations** yet — Alembic is wired (async `env.py`, empty metadata) but the baseline lands in step 2.
- **No `worker` service** yet — there are no ARQ jobs to run until the ingestion slice (step 3); adding an empty worker container now would be dishonest.
- **No frontend** yet — the Quasar app is build-order step 10 (and `pnpm` is not yet provisioned).

## Consequences

- The scaffold is runnable and fully green on lint, type-check, and tests from day one, giving a real Definition-of-Done baseline.
- Image tags (`martin`, `elasticsearch`) are pinned for reproducibility but were not pulled in the scaffold environment; verify on first `make up` and bump here if needed.
- `worker` and `api`-in-compose, DB migrations, and the frontend are explicit follow-ups tied to their build-order steps, keeping this slice small and honest.
