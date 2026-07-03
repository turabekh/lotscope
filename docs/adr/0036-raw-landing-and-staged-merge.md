# 36. Raw landing layer & staged merge with event emission

Date: 2026-07-03

## Status

Accepted

Gates PRD-amendment-01 **D1** (Phase 2) and unblocks **A2 Deal Feed**. Supersedes ADR-0004's "raw capture deferred"; extends ADR-0017 (watchlist-change taxonomy).

## Context

Today's loaders (ADR-0004) transform validated upstream records straight into the normalized core tables via idempotent `ON CONFLICT DO UPDATE` upserts. That was the right call for a read model, but it is **destructive of history**: after a load, yesterday's value is overwritten and unrecoverable. The **Deal Feed (A2)** — "since yesterday in your buy box: 14 new sheriff-sale flags, 31 new delinquencies, 6 dangerous-building designations, 4 assessment drops" — is the amendment's retention feature, and it needs exactly the deltas the in-place upsert throws away. Change detection at read time is impossible; it has to happen **at load time**, comparing the incoming batch against the current core state before the core is overwritten.

The amendment (§D1) promotes raw capture + staged merge from "architecture hygiene" to a **product prerequisite** and resolves two previously-open questions, adopted here:
- **Where normalization lives:** in the **merge step** (staging → core), so event emission sees both the new and old sides.
- **Staging schema vs separate DB:** a **`staging` schema in the same Postgres**, because event emission and merge need transactional access to the core tables in one transaction.

## Decision

**Move ingestion to ELT with three layers in one Postgres — raw landing → staging (the contract) → transactional merge that diffs against core and emits `parcel_event` — keeping loaders dumb.**

### Layers

1. **Raw landing (`raw` schema, append-only).** Each fetch writes the upstream rows as-is: `raw.<dataset>(ingest_run_id, natural_key, payload JSONB, fetched_at)`. Immutable, restartable (keyed by run + natural key so a resumed chunked load is idempotent), and the replay/debug substrate ADR-0004 anticipated. Retained per a dataset policy (raw is the biggest storage cost — see retention below).

2. **Staging (`staging` schema, current-batch contract).** The loader normalizes-lightly into `staging.<dataset>` — typed columns matching what core needs, keyed by the reconciled parcel key. Staging holds **one run's full batch** before merge, so the merge can diff batch-vs-core. The staging table *shape* is the contract between fetch and merge; changing it is the reviewable interface, not the loader internals.

3. **Merge (staging → core, one transaction).** A per-dataset merge step:
   - **Diffs** each staging row against the matching core row on the fields that carry meaning (e.g. `is_delinquent`, `total_due`, `in_sheriff_sale`, L&I danger flags, assessment values, new deeds/permits/demos).
   - **Emits `parcel_event`** rows for changes, then **upserts** staging → core via the existing `upsert` helper. Both sides are visible in the same transaction, so an event and the core write commit atomically.
   - **Normalization lives here**, not in the loader.

### `parcel_event` (the Deal Feed spine)

`parcel_event(id, parcel_number FK, dataset, code, severity, old_value JSONB, new_value JSONB, detected_at, ingest_run_id)`. Event **codes reuse the watchlist-change taxonomy (ADR-0017)** verbatim — `sheriff_sale`, `delinquent`, `tax_up`, `li_new`, `danger`, `vacancy`, `assessment` — plus `new_deed`, `new_permit`, `new_demo`. Emission is part of the merge (loaders stay dumb). This table is what A2's `GET /feed?since=&criteria=` reads (filtering reuses `savedsearch.matching.build_where` verbatim, so a saved search doubles as a feed filter).

### Run tracking

An `ingest_run(id, dataset, started_at, finished_at, status, raw_rows, merged_rows, event_count)` row ties raw rows and events to a run and extends the existing `dataset_freshness` observability. The ARQ job layer owns run lifecycle and the transaction boundary (consistent with ADR-0004: loaders don't commit).

### Loaders stay dumb

A loader's job becomes: fetch (chunked, keyset — unchanged) → write `raw` → write `staging`. It contains **no** business logic and **no** event logic. The merge is a separate, dataset-configured step (a diff spec: which core table, key, and which fields → which event codes/severities). This keeps the "no business logic in ingestion beyond normalization and reconciliation" rule (§10) intact and makes the diff spec the tested unit.

### Retention

Keep `parcel_event` **18 months** (also the seed of the longitudinal-history moat). Raw payloads get a shorter default TTL (replay window, e.g. 30–90 days per dataset) since they are the storage-heavy layer; the exact per-dataset policy is a config knob, and the retention sweep is a worker cron.

### Rollout (incremental, not big-bang)

Establish the pattern + tables + the generic merge/diff machinery first, then migrate loaders **in the order A2 needs them**: tax/delinquency, L&I (violations/permits/demolitions), sheriff sales (A4's new source), and OPA assessment. Direct-upsert loaders (ADR-0004) and staged-merge loaders **coexist** during migration — a dataset is either "direct" or "staged," switched one at a time behind the same `INGEST_JOBS` entry, so the app never has a flag day.

## Consequences

- **A2 becomes possible**: deltas are computed where the old and new state coexist, and `parcel_event` is a queryable, criteria-filterable, retained feed. A4/A6/A8 also benefit (sheriff timing, portfolio history, overlay changes).
- **Storage grows** (raw + staging + events). Mitigated by per-dataset raw TTL and the 18-month event cap; both are worker-cron sweeps. This is the deliberate cost of a longitudinal moat.
- **The merge is now the transactional heart** of ingestion and the place correctness matters most — the diff spec per dataset is written test-first (fixtures: unchanged row → no event; each meaningful field change → the right code/severity; new parcel → no spurious "change" events).
- **Migration risk is bounded**: coexistence means we prove the staged path on one low-stakes dataset (tax) before moving others; a staged dataset that misbehaves can revert to direct-upsert without touching others.
- **First-load semantics**: the initial staged load of a dataset has no prior core state to diff against — it must **not** emit a spurious event per parcel. The merge treats "no matching core row" and "first run for this dataset" as baseline (no event), matching how ADR-0024/0017 baseline saved-search/watchlist state.
- **Deferred**: backfilling historical events for the pre-D1 period (we start accumulating from cutover — no synthetic history); the Deal Feed API/page/email (A2, its own slice); moving GIS/ArcGIS loaders to staged (start with tabular Carto datasets, where deltas matter most).
