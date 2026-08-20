# CLAUDE.md — LotScope PHL

This file is the operating manual for building **LotScope PHL**, a Philadelphia-only vacant-land / infill-lot intelligence platform. You (Claude) read this at the start of every session. Follow it. When a rule here conflicts with a request, surface the conflict and propose a resolution before acting.

The full product scope lives in `docs/PRD.md`. This file governs *how* we build, not *what* we build.

---

## 0. Golden Rules (read first, never violate)

1. **No code comments. No docstrings.** Code is self-documenting through naming, types, and structure. The only exception is text an LLM reads at runtime (see §8). This is the most-broken rule — do not break it.
2. **Plan before you build.** For anything non-trivial, produce a short plan and confirm direction before editing files (see §4).
3. **Ask when ambiguous.** If requirements are unclear or there's a real trade-off, ask one focused question or present options with a recommendation. Do not guess on architecture (see §5).
4. **Test the core.** Domain logic (zoning resolution, buildability, valuation, verdict composition, ingestion transforms, parcel-key reconciliation) is test-first. Nothing merges without passing tests and lint (see §12).
5. **Build in modular vertical slices.** One module at a time, in dependency order, each independently testable and committed (see §10–11).
6. **Every derived datum carries provenance.** Any computed field (verdict outputs, scores, estimates) records its source(s) and a computed-at timestamp. This is a product requirement and a debugging lifeline.
7. **Never trust upstream.** City/third-party data is "as-is." Validate, parse defensively, and make ingestion idempotent and restartable.
8. **Never commit secrets, `.env`, data dumps, or large binaries.**
9. **Smallest change that works.** No speculative abstraction. Solve the task in front of you; note adjacent ideas separately.
10. **No new feature without three named ICP requests** recorded in `docs/feature-ledger.md`. A capability nobody asked for is cost, not product. Ideas go to the ledger at 0-of-3 and wait there; curating, labelling, or documenting what already exists is not a new feature and is not gated by this rule.

---

## 1. What We're Building (one paragraph)

A single screen that tells anyone — investor, builder, agent, or owner — what can be built on any Philadelphia vacant lot, what it's worth, and what's wrong with it, with reasoning shown and sources cited. The moat is Philadelphia data depth plus a reasoning/answer layer on top of the city's full data stack, plus real recorded comps. The core output is the **Parcel Verdict**. See `docs/PRD.md` for the complete feature catalog and §15 here for the domain glossary.

---

## 2. Tech Stack (authoritative)

**Backend**
- Python 3.12+, package/deps via **uv** (`uv add`, `uv run`, `uv sync`). Do not use pip/poetry/conda in this repo.
- **FastAPI** (async), **Pydantic v2** for all schemas/validation, **Pydantic Settings** for config.
- **SQLAlchemy 2.0** (async, typed `Mapped[]` style) + **GeoAlchemy2** for PostGIS. **Alembic** for migrations.
- **PostgreSQL 16 + PostGIS 3.4 + pgvector** (single primary datastore; pgvector for RAG embeddings).
- **Search via PostgreSQL `pg_trgm` + full-text** (address/owner/parcel search). Elasticsearch was dropped for this phase as overkill at single-city scale — see `docs/adr/0005-postgres-search-instead-of-elasticsearch.md`. The `search` module stays behind a service interface so a dedicated engine can return later if scale demands it.
- **Redis** (cache + job broker). **ARQ** for async background jobs and scheduled ingestion. (If you ever need heavy workflow orchestration, propose it via ADR first — do not pull in Airflow casually.)
- **Anthropic Claude API** for the AI layer (model choice per task — see §9).
- **Martin** (vector tile server reading directly from PostGIS).

**Frontend**
- **Quasar (Vue 3)**, Composition API, `<script setup lang="ts">` only. **TypeScript strict**.
- **Pinia** for state, **Vue Router**, **MapLibre GL JS** for the map, **Vite** build. Deps via **pnpm**.

**Quality tooling**
- Python: **Ruff** (lint + format), **mypy** (strict). **pre-commit** runs both.
- Frontend: **ESLint** (flat config) + **Prettier**, type-check via **vue-tsc**.
- Tests: **pytest** + **pytest-asyncio** + **coverage** (backend, PostGIS via **testcontainers**); **Vitest** + **Vue Test Utils** (frontend); **Playwright** (e2e).

**Infra / dev**
- **Docker + docker-compose** for local (services: `db`, `redis`, `martin`, `api`, `worker`, `web`).
- **GitHub Actions** CI (lint, type-check, test on every PR). **AWS** for prod.

If you believe a different tool is genuinely better for a task, raise it in discussion with reasoning; do not swap stack components unilaterally.

---

## 3. Repository Layout (modular monolith)

```
/
├── CLAUDE.md
├── README.md
├── docs/
│   ├── PRD.md                  # the full product spec (source of truth for scope)
│   ├── architecture.md
│   ├── data-sources.md         # Philly dataset catalog, endpoints, schemas, gotchas
│   └── adr/                    # Architecture Decision Records (NNNN-title.md)
├── docker-compose.yml
├── .env.example
├── backend/
│   ├── pyproject.toml
│   ├── alembic/
│   └── src/lotscope/
│       ├── core/              # config, db, logging, errors, types, deps
│       ├── parcels/           # parcel model + service (the spine)
│       ├── zoning/            # district resolution + Title 14 standards + buildability
│       ├── valuation/         # comps + AVM
│       ├── risk/              # liens, title, L&I, flood, land bank flags
│       ├── verdict/           # composes the above -> Parcel Verdict
│       ├── ingestion/         # ETL: carto client, arcgis client, loaders, reconciliation
│       ├── search/            # Postgres trigram/full-text search
│       ├── ai/                # Claude client, prompts, RAG, structured outputs
│       └── api/               # FastAPI routers (thin; compose services)
└── frontend/
    ├── package.json
    └── src/
        ├── pages/  components/  composables/  stores/  boot/  lib/  router/
```

`components/` hosts the persistent **app shell** — `AppShell` (layout) + `AppSidebar` + `AppTopBar`, with `MarketSwitcher`, `GlobalSearch`, and `DataCoverageChip` — which wraps the authenticated routes; market scope is a first-class URL segment (`/:market/...`) resolved via `stores/market`. The frontend information architecture, layout, and redesign sequence are specified in `docs/design/ia-and-layout.md` (and ADR-0029).

Each backend domain package owns its `models.py`, `schemas.py`, `service.py`, and `tests/`. The `api` layer is thin and only orchestrates services. **Modules talk through service interfaces, never by reaching into another module's internals or models.**

---

## 4. Planning Instructions

Before writing code for any non-trivial task:

1. Restate the goal in one or two sentences.
2. Produce a short plan: the steps, the files/modules you'll touch, the tests you'll add, and any data/migration impact.
3. Call out anything that crosses module boundaries, changes the data model, or affects the verdict contract — these need extra care and usually an ADR.
4. Confirm direction before large or architectural changes. For small, obvious changes, a one-line plan is enough.

Always anchor scope to `docs/PRD.md` and respect module boundaries. Prefer the smallest vertical slice that produces something runnable and tested. Do not expand scope beyond the request; note adjacent improvements as follow-ups rather than doing them silently.

For decisions with lasting impact (datastore choices, the verdict schema, ingestion strategy, auth model, tiling approach), write an ADR in `docs/adr/` (context → decision → consequences) and get agreement before implementing.

---

## 5. Discussion Instructions

- **Ask before assuming.** When requirements are ambiguous or there are meaningful trade-offs, ask one focused question, or present 2–3 options with a clear recommendation and the trade-offs. Do not silently pick a path on anything architectural.
- **Surface risks early.** Flag edge cases, data gotchas (§7/§11), performance concerns, and legal/compliance implications (§9, §13) proactively.
- **Push back with reasoning.** If a request conflicts with these standards, the architecture, or the PRD, say so and propose an alternative. Be direct and constructive.
- **No over-engineering.** Call out premature abstraction, unnecessary generality, and gold-plating. Default to simple.
- **Be honest about uncertainty.** If you're unsure a Philadelphia dataset behaves a certain way, say so and verify rather than asserting.

---

## 6. Git & Versioning

- **Conventional Commits**, scoped by module: `feat(verdict): ...`, `fix(ingestion): ...`, `refactor(zoning): ...`, `test(valuation): ...`, `perf(search): ...`, `docs: ...`, `chore: ...`, `build:`, `ci:`.
- **Small, atomic commits.** Each commit compiles, passes lint/type-check, and passes tests. No "WIP" commits on `main`.
- **Branching:** short-lived branches off `main`, named `type/short-desc` (e.g., `feat/carto-ingestion`). Trunk-based; merge fast, keep branches small.
- **PRs:** description references the PRD section or issue and summarizes what/why. CI must be green. Squash-merge.
- **SemVer** for releases; tag from `main`.
- **Never commit:** secrets, `.env`, credentials, API keys, raw data exports, large binaries, generated artifacts. Keep `.env.example` current whenever a new env var is introduced.
- Write commit messages that explain *why*, not *what* (the diff shows what). Commit messages and PR descriptions are where human-facing rationale lives — not code comments.

---

## 7. Coding Standards — Backend (Python)

- **Full type annotations everywhere.** mypy strict must pass. No untyped public functions, no `Any` unless unavoidable and justified.
- **Pydantic v2** for all I/O boundaries (API request/response, ingestion records, LLM structured outputs). Domain models via SQLAlchemy 2.0 typed mappings.
- **Async by default** for I/O (DB, HTTP, LLM, Redis). No blocking calls in async paths.
- **Pure core, isolated side effects.** Keep computation (zoning logic, scoring, valuation) pure and deterministic; push DB/HTTP/LLM access to thin adapters at module edges. This keeps the core trivially testable.
- **Small, single-purpose functions.** If a function needs a comment to be understood, rename it or extract a well-named helper instead.
- **Config via `Settings`** (Pydantic Settings, env-backed). No hardcoded URLs, keys, paths, or magic numbers — name constants.
- **SQL safety:** always parametrize. When building Carto SQL API queries, construct them safely; never string-interpolate untrusted input. Same for any dynamic SQL.
- **Errors:** define typed domain exceptions per module; never swallow exceptions silently; let ingestion fail loudly with retry/backoff.
- **Logging:** structured (JSON) via the central logger in `core/`. No `print`. Never log secrets or owner PII.
- **Imports/structure:** no circular deps; domain modules depend inward on `core/`, not sideways on each other except through declared service interfaces.

---

## 8. Code Comments & Docstrings — Strict Policy

**Do not write code comments or docstrings.** Achieve clarity through precise names, complete types, small functions, and clean structure. If you feel the urge to explain code inline, refactor instead. Human-facing explanation goes in `docs/` and ADRs, never in the source.

**The only exception:** strings that an LLM consumes at runtime as part of an AI interface. These are functional code, must exist, and must be written carefully:
- Tool/function descriptions in Anthropic tool-use schemas or MCP tool definitions (the description *is* the model's interface).
- `Field(description=...)` on Pydantic models used as LLM structured-output or tool schemas.
- Prompt templates, system prompts, and instruction strings the model reads.
- Any text whose purpose is to steer model behavior.

Illustration of the policy:

```python
# DISALLOWED — human-facing comment
# resolve the zoning district for a parcel by centroid
def resolve_district(...): ...

# DISALLOWED — docstring for humans
def resolve_district(...):
    """Resolve the zoning district for a parcel."""
    ...

# CORRECT — self-documenting, no comment, no docstring
def resolve_zoning_district_for_parcel(parcel: Parcel) -> ZoningDistrict | None: ...

# ALLOWED — description is an AI interface, required and kept accurate
class BuildabilityAnswer(BaseModel):
    can_build_by_right: bool = Field(description="True only if the use is permitted with no variance under the cited code section")
    cited_section: str = Field(description="The Title 14 section number the determination is based on")
```

When in doubt: if a human is the audience, omit it; if the model is the audience at runtime, keep it.

---

## 9. AI / LLM Integration Conventions

- **Centralize all model access** behind the `ai/` module's client. No scattered `anthropic` calls across the codebase.
- **Prompts are versioned templates** in `ai/prompts/` (these are the allowed AI-facing strings). Treat prompt changes like code changes — reviewed and tested.
- **Structured outputs are validated.** Any LLM output that feeds logic must be parsed into a Pydantic schema and validated; reject/repair on failure. Never trust free-form model text in a code path.
- **Grounding is mandatory** for zoning/legal/value answers. Retrieve source text (Title 14, deeds, city rules via pgvector) and pass it in; the model must answer *from* retrieved sources and return citations. Never let it answer a zoning question from parametric memory.
- **Framing & provenance:** every answer is informational (not legal/financial advice), carries a confidence signal, and cites its source. This is both a product and a legal requirement.
- **Model selection by task:** use a cheaper/faster model for summaries and extraction, a stronger model for multi-step reasoning. Make the choice explicit and configurable; set sensible token limits; cache where inputs repeat.
- **Testability:** the AI client is mockable. Test the deterministic scaffolding (retrieval, prompt assembly, schema validation, citation extraction) with fixtures; assess answer *quality* with an eval harness, not by asserting exact prose.

---

## 10. Architecture & Module Boundaries

A modular monolith. Dependency direction is inward toward `core/`. Cross-module use goes through each module's `service.py` interface only — never import another module's `models.py` or internal helpers.

- `parcels` is the spine; most modules read parcel context from it.
- `zoning`, `valuation`, `risk` are independent engines that produce structured results.
- `verdict` composes those engines into the Parcel Verdict and is the single source of the verdict contract. Changing that contract is an ADR-level decision.
- `ingestion` writes raw + normalized data; it does not contain business logic beyond normalization and reconciliation.
- `search` and `ai` are services consumed by `api`; they do not own domain truth.
- `api` is thin glue. No business logic in routers.

The **frontend** is a market-scoped app shell (persistent sidebar + top bar wrapping the authenticated routes) with jurisdiction as a first-class URL scope; its information architecture and module layout are specified in `docs/design/ia-and-layout.md` (rationale in ADR-0029). Business logic lives in Pinia stores + `lib/`, not components; the shell and dossier are structural, not domain owners.

---

## 11. Step-by-Step Modular Build Order

Build in this order. Each step ends with: passing tests, passing lint/type-check, and a conventional commit. Do not start a step until the previous one is green.

1. **Scaffold & infra.** Repo layout, `uv` project, docker-compose (db+postgis+pgvector, redis, es, martin), `core/` (settings, db session, logging, errors), base FastAPI app, pre-commit, CI. Health-check endpoint.
2. **Data model & migrations.** Tables: `parcel`, `zoning_district`, `zoning_standard`, `sale`, `tax_status`, `li_event`, `parcel_verdict`. Alembic baseline. Geometry in EPSG:2272 (analysis) + 4326 (tiles); GiST indexes on all geometry.
3. **Ingestion.** Carto SQL client with **mandatory chunking** (paginate by parcel-number ranges; never full-table dump). ArcGIS Hub client. Loaders for OPA, PWD parcels, RTT transfers, tax delinquency, L&I, Vacant Indicators, Zoning Base Districts, FEMA flood. **Parcel-key reconciliation** (OPA ↔ PWD ↔ RTT) as a tested, first-class concern. Idempotent upserts + freshness tracking.
4. **Search.** Postgres `pg_trgm`/full-text indexes on parcels; address/owner/parcel queries (ADR-0005).
5. **Tiles.** Martin config over PostGIS; serve vacant-lot + parcel layers in 4326.
6. **Domain engines.** `zoning` (district resolution + Title 14 standards table + buildability/by-right), then `valuation` (RTT comps + confidence-scored AVM), then `risk` (liens, L&I, Land Bank, flood, title flags).
7. **Verdict engine.** Compose engines into `parcel_verdict` (batch recompute + on-demand). Record provenance + computed-at on every field.
8. **API.** Endpoints: search, parcel detail, verdict, comps, layers. Consistent error schema. Pagination.
9. **AI layer.** RAG over Title 14 + deeds (pgvector). "Ask the Parcel" Q&A: grounded, cited, schema-validated, confidence-scored.
10. **Frontend.** MapLibre map on Martin tiles → parcel panel → Parcel Verdict screen → search → auth shell.
11. **Accounts & billing.** Auth, roles, tiers, Stripe, usage metering.
12. **Iterate up the PRD tiers** (watchlists/alerts, reports, pipeline, outreach, owner-side, etc.) one vertical slice at a time.

---

## 12. Testing (non-negotiable)

Testing is not optional and not an afterthought. A feature without tests is not done.

- **Test pyramid:** many unit tests (pure logic), fewer integration tests (DB/PostGIS via testcontainers, real spatial queries), a few e2e (Playwright on critical flows: search → verdict).
- **Test-first for core logic:** zoning resolution, buildability/by-right, valuation, verdict composition, ingestion transforms, and parcel-key reconciliation are written test-first. These are where wrong answers cost users money — prove them.
- **A new ingested column is not done until a test carries a value the whole way.** The pipeline is loader → row-mapper → staging model → merge SQL, and every one of them enumerates its columns. A column added to three of the four is silently discarded, and the ingest still reports success. The test must call the *real* mapping functions rather than constructing the intermediate dict itself — a test that builds its own staging row tests the row it built, not the one the system builds. Confirm the test fails when the column is removed; if it passes either way it is proving nothing. Cost: one test per column. This trap re-arms for every new column. **The test is necessary but not sufficient: a migration that adds an ingested column is not done until a post-ingest query against the destination table shows populated coverage.** Run the ingest, then count non-null values in the destination and record the number. A green end-to-end test proves the pipeline can carry a value; only the coverage query proves it did.
- **Deterministic & isolated:** no network in unit tests. Mock Carto/ArcGIS/Anthropic; use recorded fixtures (sample parcels, sample API responses, sample deeds). No flaky tests — fix or delete.
- **Spatial tests use real PostGIS** (testcontainers), with small fixture geometries, not mocks of spatial functions.
- **AI tests:** assert on the deterministic parts (retrieval results, prompt inputs, output schema validity, citation presence). Use a small **eval set** for answer quality; never assert exact model wording.
- **Coverage:** aim for strong coverage on `zoning`, `valuation`, `risk`, `verdict`, and `ingestion` (target ~85%+ on core logic). Don't chase 100% or test trivial glue.
- **Run before every commit;** CI enforces lint + type-check + tests on every PR. Red CI never merges.
- Provide and use `make test`, `make lint`, `make typecheck`, `make up` (compose), `make migrate`, `make docker-prune`. Use these exact entrypoints.

---

## 13. Security, Privacy & Compliance

- Secrets via env locally and a secret manager in prod; never in code, logs, or VCS.
- **Owner PII** (names, mailing addresses, skip-trace results) is sensitive: restrict access by role, encrypt at rest, never log it, and minimize retention.
- Parametrize all SQL; validate and sanitize all external input at the boundary.
- **Outreach features** must respect TCPA/DNC (SMS/calls) and CAN-SPAM (email), and any list-based targeting must respect Fair Housing — bake these constraints into the relevant modules, don't bolt them on.
- Honor data licenses: city data is "as-is / hold-harmless"; surface appropriate disclaimers in product output. Respect any third-party (e.g., Regrid) license terms.
- The AI advice layer is **informational, cited, and confidence-scored** — never presented as legal/financial determination.

---

## 14. Error Handling, Logging & Performance

- Typed domain exceptions; consistent API error responses; never swallow errors.
- Structured logging with correlation IDs; no PII/secrets in logs.
- Ingestion: retry with backoff, fail loudly, record per-dataset freshness and last-success.
- Performance: GiST indexes on all geometry; serve map via Martin tiles (not raw GeoJSON); do verdict computation in batch with on-demand refresh; async I/O; paginate; cache hot reads in Redis; avoid N+1 in both SQL and API composition.
- Map interactions target sub-second; verdict render target ~2s.
- **Dev-box Docker disk hygiene:** the local box runs tight and an ENOSPC event can wedge the Docker engine. Reclaim with `make docker-prune` (`docker builder prune -f` + `docker image prune -af`). **Never** add `--volumes` — it destroys the local Postgres dev volume.

---

## 15. Maintainability

- Keep modules small and boundaries clean; isolate side effects behind adapters; prefer composition over inheritance.
- Config and constants are named and centralized; no magic values.
- Dependency hygiene: pin versions, review before adding any dependency, prefer the stdlib or an existing dep over a new one.
- **Decisions live in ADRs**; reference material lives in `docs/`. When a convention changes, update this `CLAUDE.md` and the relevant doc in the same PR.
- Idempotent, restartable jobs; reproducible verdicts (provenance + computed-at on every derived field).
- Leave the code better than you found it within the scope of your change; do not refactor unrelated code in a feature PR (note it as a follow-up).

---

## 16. Definition of Done

A change is done when all of these are true:
- It delivers a working vertical slice of the requested behavior.
- Tests are added and passing; lint, format, and type-check pass.
- No code comments or docstrings (except the §8 AI-interface exception).
- Derived data records provenance and computed-at.
- Security/PII/compliance constraints (§13) are respected.
- `docs/` or an ADR is updated if a convention, contract, or decision changed.
- It's a clean conventional commit; PR CI is green.

---

## 17. Domain Glossary (Philadelphia)

- **OPA** — Office of Property Assessment; `opa_properties_public` (assessments, owner, values). Carto SQL.
- **RTT** — recorded real-estate transfers (`rtt_summary`); the source of real sale comps. Carto SQL.
- **PWD parcels** — authoritative parcel polygons. Carto SQL.
- **L&I** — Licenses & Inspections (violations, permits, demolitions).
- **Vacant Property Indicators** — the city's per-parcel vacancy model (ArcGIS Hub); the core vacant-lot set.
- **Tax delinquency dataset** — Dept. of Revenue; liens/sheriff-sale signal.
- **Land Bank / PHDC** — public land-holding/disposition entities; flags city-owned lots.
- **Zoning Base Districts** — Title 14 districts (ArcGIS Hub): **RSA** (single-family attached / rowhouse), **RM** (multi-family), **CMX** (commercial mixed-use), etc.
- **Title 14** — the Philadelphia zoning code; source text for the AI grounding and the `zoning_standard` table.
- **ZBA** — Zoning Board of Adjustment (variances/special exceptions).
- **RCO** — Registered Community Organization (zoning notification requirement).
- **Sheriff sale** — auction of tax/mortgage-foreclosed property.
- **Act 135** — PA conservatorship statute for blighted property.

**Data gotchas to always respect:** Carto times out on full-table dumps → chunk by parcel-number ranges; OPA/PWD/RTT join keys are not aligned → reconcile explicitly; analysis geometry is EPSG:2272 (feet), tiles are 4326; Carto SQL is case-sensitive → use `ILIKE`; city data is "as-is" → parse and validate defensively.

---

## 18. Anti-Patterns (never do these)

- Writing comments or docstrings for humans.
- Editing files before presenting a plan for non-trivial work.
- Reaching across module boundaries into another module's internals.
- Full-table Carto dumps; unparametrized SQL; trusting upstream data shape.
- LLM output used in logic without schema validation; ungrounded zoning/legal answers.
- Business logic in API routers or in ingestion.
- Merging without tests, or with red CI.
- Adding dependencies or swapping stack components without discussion.
- Committing secrets, `.env`, data dumps, or large binaries.
- Speculative abstraction and unrequested refactors inside a feature change.

---

*Keep this file current. If we change how we work, change this file in the same PR.*
