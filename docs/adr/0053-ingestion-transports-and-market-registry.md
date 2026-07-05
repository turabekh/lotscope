# 53. Ingestion transports and market-keyed loader registry

Date: 2026-07-05

## Status

Proposed

Implements PRD Amendment-02 workstreams **B3** and **B4**. (PRD calls this "ADR-0031".)

## Context

`INGEST_JOBS: dict[str, Job]` is a flat registry of 17 Philadelphia jobs; `Job = Callable[[SessionFactory, Settings], Awaitable[int]]` — no market parameter. `ingest_all` (worker) loops every key nightly at 04:00. `dataset_freshness` has `dataset` (`String(120)`) as its **sole PK** — no market dimension, so two markets ingesting the same dataset would collide. Two transports exist: `CartoClient` (base URL from `settings.carto_sql_url`, keyset-chunked `paginate_by_key`) and `ArcGisClient` (per-call layer URLs, offset-paginated); no CKAN/Extract/Socrata client. Source endpoints and the `deal_*` assumptions are flat Philly-singleton `Settings` fields. `reconciliation.py` normalizes OPA/BRT to a 9-digit key — pure, golden-file-tested, entirely Philadelphian.

**A raw-landing ELT layer already exists** (contrary to the PRD's "raw capture deferred" note — the codebase moved): a `raw` schema with `RawRecord`, a `write_raw(session, rows)` path, `IngestRun` ledger, five `staging.*` tables, and a `merge.py` raw→core path. Several loaders (`opa`, `tax`, `rtt`, `li`, `sheriff`) already write through it. None of it carries a market dimension.

## Decision

**Re-key the ingestion registry and freshness on `(market, dataset)`, move source endpoints into per-market config-as-data, and add two transports (`CkanDatastoreClient`, `ExtractClient`) built and tested but wired to no live market yet — `ExtractClient` writing through the existing raw-landing layer.**

- **Registry** re-keyed `(market, dataset) → job`; `ingest_all` becomes `ingest_market(market)`; the CLI and ARQ worker take a market; the admin datasets page groups by market. `dataset_freshness` gains `market_code` (migration, backfill `'phl'`, PK/uniqueness becomes `(market_code, dataset)`). `IngestRun`/`raw_record`/`staging` gain `market_code` so raw capture is replayable per market.
- **Source config as data** (the ADR-0006 "standards are data" principle applied to ingestion): per-market endpoints move from `Settings` into the market registry — either the `market` row (jsonb) or a `market_source` table — with a `Settings` fallback so a missing row never breaks Philadelphia. Philly's `carto_sql_url`, `arcgis_hub_url`, and `*_min_*_date` filters migrate in.
- **Transport roster**: keep `CartoClient` (Philly-only — no other selected market uses Carto) and `ArcGisClient` (most GIS layers, FEMA, Detroit/Baltimore/Cuyahoga/Dauphin); add **`CkanDatastoreClient`** (WPRDC + Milwaukee — datastore SQL with the same keyset-chunking discipline as Carto, a Wave-1 consumer) and **`ExtractClient`** (checksummed file download → staging, idempotent re-runs — a Wave-0 consumer for Dauphin/MPROP/tax-sale/delinquent-list extracts). A `SocrataClient` is specced but deferred to the Chicago gate. Each new client ships with unit tests + one recorded-fixture integration test; neither is wired to a live market in Phase P.
- **`ExtractClient` writes through the existing raw-landing layer** (`write_raw`) rather than a new path — the layer is mature, so this is minimal work and makes every new-market loader replayable during field-mapping. (This supersedes the PRD's assumption that the raw layer still needed building.)
- **B4 — key reconciliation** (`feat/expansion-b4-normalizers`): extract the existing logic into a `KeyNormalizer` protocol with `PhlKeyNormalizer` as the first implementation, behavior byte-identical (the existing golden-file tests move over unmodified and must pass unchanged). A market-keyed registry selects the normalizer; the canonical-key composition from B1 becomes the protocol's single responsibility (one place, per market). `hbg`/`pgh`/etc. normalizers belong to their waves — Phase P ships the protocol, the registry, and `phl` only. Same contract as today: misaligned records reconcile or are *reported, never dropped*.

## Consequences

- Nightly Philadelphia ingestion runs unchanged — verified by running `ingest_market('phl')` against dev and diffing `dataset_freshness` rows before/after.
- Building the two transports now (behind fixtures, no live market) front-loads the per-wave adapter cost and lets Wave 0/1 focus on field-mapping, not plumbing.
- The `market_code` addition to `dataset_freshness`/`IngestRun`/`raw_record`/`staging` is a migration with a `'phl'` backfill; low risk (append-only dimension), but the freshness PK change must preserve existing rows.
- Source-config-as-data with a `Settings` fallback means the Philly singleton keeps working if a market row is absent — no big-bang cutover.
