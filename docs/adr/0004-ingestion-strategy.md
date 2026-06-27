# 4. Ingestion strategy

Date: 2026-06-27

## Status

Accepted

## Context

Build-order step 3 ingests Philadelphia open data into the normalized schema. The upstream sources are "as-is", keyed inconsistently, and rate/timeout sensitive (Carto times out on full-table dumps; OPA/PWD/RTT keys are misaligned). Ingestion must be idempotent, restartable, and observable. The approach is a lasting decision, recorded here.

## Decision

**Two thin upstream clients, shared retry.** `CartoClient` (tabular: OPA, RTT, tax, L&I) and `ArcGisClient` (GIS: parcels, zoning, vacancy, flood) wrap `httpx` with a shared `request_with_retry` helper (exponential backoff on timeouts, connection errors, 429, and 5xx). Query building is pure and unit-tested; the network is exercised only through a mocked transport.

**Mandatory chunking, never full-table dumps.** Carto reads use **keyset pagination by `parcel_number`** (`WHERE key > :last ORDER BY key LIMIT n`), not OFFSET, because Carto times out on large offsets and full scans. ArcGIS reads use `resultOffset`/`resultRecordCount` and stop on a short page.

**Safe SQL without bind parameters.** The Carto SQL API has no bind parameters, so SQL identifiers and column lists are code constants only, and keyset bound values are escaped-and-quoted. Untrusted input is never interpolated.

**Normalized-only for now; raw capture deferred.** Loaders transform validated records straight into the normalized tables. Persisting raw upstream payloads to a staging store is a deliberate follow-up, added when a loader needs replay/debugging against original bytes.

**Idempotent upserts + freshness.** Writes go through a generic Postgres `ON CONFLICT DO UPDATE` helper that touches `updated_at` and only the columns a loader owns, so re-runs are safe and loaders compose without clobbering each other's fields (e.g. OPA writes attributes, PWD writes geometry). A `dataset_freshness` row records per-dataset last-attempt/last-success/row-count/status.

**Parcel-key reconciliation is first-class.** OPA account / BRT numbers are normalized to a canonical 9-digit key; records arriving under misaligned keys reconcile to one parcel, and unresolvable records are reported, not dropped. This is pure and fully unit-tested.

**Loaders are units of work; orchestration owns the transaction.** A loader (e.g. `load_opa`) performs transform → chunked upsert → success-freshness within a caller-provided session and does not commit. Transaction boundaries, failure-path freshness, and retry/scheduling belong to the ARQ job layer (a later slice). This keeps loaders pure-ish and testable under transaction-rollback isolation.

## Consequences

- Re-running any loader is safe and converges; partial failures don't corrupt prior data.
- Column mappings (e.g. the OPA `opa_properties_public` field names) are plausible but must be verified against the live API and recorded in `docs/data-sources.md`; the defensive Pydantic transforms tolerate missing/renamed fields.
- The deferred pieces — raw-payload staging, the ARQ job/commit/retry wrapper, and the remaining loaders (PWD, RTT, tax, L&I, Vacant Indicators, Zoning, FEMA) — are explicit follow-ups, each a small vertical slice over this foundation.
