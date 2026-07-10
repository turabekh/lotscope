# ADR-0059 — Admin job console (trigger ingestion/maintenance jobs from the browser)

Status: accepted (2026-07-10)

## Context
Ingestion and maintenance jobs (dataset loaders in `INGEST_JOBS`, the `recompute_*` batch jobs) are
only runnable via `make`, the `python -m lotscope.ingestion.cli` entrypoint, or the ARQ cron schedule —
all requiring shell access to the production VM. Two operational facts make a browser trigger valuable:

1. Some Harrisburg sources are IP-blocked from the build/dev environment but reachable from the US-based
   prod VM (Dauphin tax-claim, FEMA flood). The person operating the platform needs to *run those pulls
   where they work* — on the server — without SSH.
2. Onboarding a market and keeping data fresh is an operational loop (load → recompute → inspect
   freshness). Doing it from the existing admin page, next to the `dataset_freshness` table that already
   reports outcomes, closes that loop.

The admin surface already exists: `/admin` (`AdminPage.vue`), gated by `require_admin` (backend) and a
route guard (frontend); an ARQ worker running in the prod `app` profile with `ingest_dataset`,
`ingest_all`, and every `recompute_*` already registered; and `dataset_freshness` provenance. What is
missing is a *trigger path* from a request to the worker, and a record of individual triggered runs.

## Decision
Add an admin-only, ARQ-backed job console.

- **Execution is async via ARQ**, never inline in the request. Ingestion jobs run for minutes; they must
  run in the worker (which is already the prod execution context), not tie up an API worker or die on a
  request timeout. The API gains an ARQ pool (`app.state.arq_pool`) alongside its existing plain Redis
  connection.
- **A whitelist catalog is the only runnable set.** `admin/catalog.py` builds `JobSpec`s from the
  existing `INGEST_JOBS` keys (market × dataset) plus a static list of recompute jobs. The API accepts a
  `job_id` from this catalog only — there is no path to invoke an arbitrary callable, and job arguments
  are the catalog's own constrained `(market, dataset)`, never free-form input. This keeps a
  remote-execution surface from becoming an RCE surface.
- **Every triggered run is recorded** in a new `job_run` table (job id, kind, market, arq job id, status
  `queued|running|success|failed`, started/finished, result count, error, **triggered_by** user). This
  is the provenance/audit trail the golden rule requires for derived actions, and it is what the UI polls.
- **One worker wrapper, `run_admin_job(ctx, job_run_id)`**, owns status transitions: it loads the run,
  marks it running, dispatches to the underlying callable via the catalog, and records success/failure.
  The existing `ingest_dataset`/`recompute_*` arq functions and the underlying Python callables are
  unchanged — the wrapper calls the same callables directly. Concurrency is guarded at enqueue time: a
  second run of a job that is already `queued`/`running` is rejected (409) rather than double-run.
- **Endpoints** (all `require_admin`): `GET /admin/jobs` (catalog + each job's latest run),
  `POST /admin/jobs/run` (enqueue), `GET /admin/jobs/runs` (recent runs, polled by the UI).

## Consequences
- New API→ARQ enqueue path; the API opens an ARQ pool at startup and closes it at shutdown.
- New `job_run` table (migration; down-rev the current head). No change to the verdict contract or any
  domain model — `VERDICT_VERSION` is unaffected.
- The catalog and the worker's recompute dispatch map are two halves of one contract; a test asserts they
  stay in sync (every catalog id resolves to a dispatch, every ingest id exists in `INGEST_JOBS`) so drift
  fails CI rather than at runtime.
- Typed job parameters (follow-up, landed 2026-07-10). `JobSpec` gained a `params` schema; a parameter
  registry `PARAM_INGEST_JOBS` holds jobs that take runtime inputs; `job_run.params` (JSONB, migration
  `e5a1c8b0f2d9`) records what an operator supplied. `POST /admin/jobs/run` validates params against the
  spec (required present, dates parseable) and stores them; the worker coerces and passes them to the
  loader. The UI shows a "Run…" button that opens a parameter dialog. First parameterized job registered:
  **`hbg tax_claim`** (list URL + date) — the Dauphin upset/judicial list is reachable from the prod VM,
  so an operator can now pull it from the browser.
- `load_hbg_violations` stays deferred: it needs an uploaded export plus a field map, and the export does
  not exist until the RTKL request is answered — building its upload/column-mapping now would be
  speculative and untestable. `load_hbg_flood` is likewise out of scope until the loader is written.
- Failures are recorded, not retried: `run_admin_job` records a failed run and does not re-raise, so ARQ
  does not silently retry an ingestion. The operator sees the failure in the console and re-runs
  deliberately.
