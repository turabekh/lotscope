# Claude Code Prompt — Expansion Phase P: Platform Prerequisites (B1–B4, B10)

## What this is

Execution orders for **Phase P** of `docs/PRD-amendment-02-geographic-expansion.md` (read it fully first — it is the spec; this prompt does not restate it). Phase P makes the codebase multi-market-capable with **zero user-visible change to Philadelphia**. No Harrisburg data, no new zoning, no branding changes — those are Wave 0+, under separate prompts.

Read `CLAUDE.md` first; every rule applies (no comments/docstrings, module-boundary imports, thin routers, provenance, tests for all domain logic). Gates for every slice: `make lint && make typecheck && make test`, plus `pnpm lint && pnpm typecheck && pnpm test` when `frontend/` is touched.

## Git & CI/CD standing rules (new — main now auto-deploys)

Every push to `main` triggers production deployment via GitHub Actions. Therefore, from now on:

1. **Never commit to `main` directly. Never force-push anything.** All work happens on a feature branch created from up-to-date `main`: `git checkout main && git pull && git checkout -b <branch>`.
2. **One branch per slice**, named as given in each slice below. Conventional commits on the branch exactly as before (multiple small commits per slice are fine and preferred).
3. **Merge to `main` only when**: the slice's definition of done is met, all gates are green locally **and in CI**, and I have explicitly approved the slice. Merging is deploying — treat it that way.
4. Merge mechanics: if the `gh` CLI is authenticated, open a PR (`gh pr create`) with the slice name as title and a body containing: what changed, migration yes/no, rollback plan, and post-deploy verification steps; merge with `gh pr merge --merge` after approval. If `gh` is unavailable, merge locally with `git merge --no-ff <branch>` and put the same information in the merge commit body. Delete the branch after merge.
5. **Migration-bearing slices** (Slice 1 especially): before asking me to approve the merge, (a) confirm how migrations run on deploy (inspect the deploy workflow / `deploy.sh` — `alembic upgrade head` must execute before or with the app restart; if it does not, fixing that is part of Slice 0), (b) print the exact backup command for me to run against prod (`pg_dump` or the `make` target if one exists) and wait for my confirmation that the backup completed, (c) state the rollback plan (restore command + `git revert` of the merge) in the PR body.
6. After any merge, watch for my confirmation that the deploy succeeded before starting the next slice.

## Sequencing context

The PRD gates Phase P on Amendment-01 Phases 0–1; we are starting it now with the understanding that Phase P is entirely user-invisible and can run alongside the sales push. Slice 0 must determine whether the Amendment-01 raw-landing/ELT layer already exists and adapt Slice 3 accordingly (build with it if present; build the minimal raw-capture path for `ExtractClient` only, if not).

**Phase P exit criterion (from PRD §6.1, verbatim intent):** Philadelphia runs on the multi-market codebase with zero user-visible change — `phl:`-prefixed keys resolving, old URLs working, verdicts identical modulo `computed_at` — and a synthetic two-market integration suite is green in CI. Verdict outputs must NOT change in this phase; no `VERDICT_VERSION` bump.

---

## Slice 0 — Recon, CI workflow, ADRs, plan
**Branch: `feat/expansion-adrs`** (docs + CI only; no behavior change)

**Recon (report findings before writing anything):**
1. Read the PRD end to end. Note every place §5 references current code, and verify each against the actual repo — the codebase has moved since the PRD was written (snapshot, overlays, RCO, ZBA, feed/top-plays/sheriff-sales). List discrepancies.
2. Inventory for B1: every table carrying a `parcel_number` FK (query `information_schema` or grep models); current `parcel_number` column widths; everywhere the bare 9-digit shape is assumed (regexes, validators, URL builders, PDF dossier links, MVT feature ids, frontend route params).
3. Inventory for B2: grep every cross-parcel spatial query (`ST_DWithin`, `ST_Intersects`, `ST_Touches`, `ST_Contains` in raw SQL) — this list becomes the market-predicate audit checklist. Note the exact `geom_2272` column declarations and index definitions.
4. Inventory for B3: current `INGEST_JOBS` shape, `dataset_freshness` schema, the Philly-singleton settings (`carto_sql_url`, `arcgis_hub_url`, `philadox_document_url_template`, `deal_*`), and whether a raw-landing layer exists.
5. Inventory for B10: how the deployed frontend's market routing (`/philadelphia/...`) currently communicates scope to the backend, if at all; where map center/bounds constants live.
6. CI/CD: read `.github/workflows/*`. Confirm deploy fires only on `push: branches: [main]`. Confirm whether migrations run during deploy.

**Build in this slice:**
- `.github/workflows/ci.yml` (if absent): runs backend gates and frontend gates on `pull_request` to `main` and on `push` to `feat/**` branches. Cache dependencies; Postgres+PostGIS service container for the integration tests (mirror the local testcontainer setup). This must be green before any later slice merges.
- Author three ADRs drawing their content from PRD §5 (Nygard format, house voice, next sequential numbers): market entity & prefixed canonical key including the composite-PK rejection rationale (B1); multi-CRS `geom_local` including the market-predicate rule and the mixed-SRID invariant (B2); ingestion transports & market-keyed registry including the source-config-as-data decision (B3/B4).

**Deliver and PAUSE for my approval:** the recon report, the plan table (slice → branch → files → migration? → tests → primary risk), and the three ADR drafts. Merge this branch only after I approve the ADRs.

---

## Slice 1 — B1: market entity + canonical parcel key  ⚠ the risky one
**Branch: `feat/expansion-b1-market-key`** · Spec: PRD §B1 · ADR: the first authored above

- `market` table per the PRD field list; seed the `phl` row (SRID 2272, timezone `America/New_York`, map center/bounds/zoom lifted from the frontend constants found in Slice 0, `recorder_url_template` from the PhilaDox setting, `launch_status='live'`).
- `parcel`: add `market_code` (FK, indexed, default `'phl'`) and `local_key`; widen `parcel_number` to `String(40)` on `parcel` **and every FK column** from the Slice-0 inventory.
- **Alembic migration**, transactional: rewrite `parcel_number → 'phl:' || parcel_number` across `parcel` and every child table, in an order safe for the FK graph (or with constraints deferred); backfill `local_key`; embed verification (pre/post row counts per table, prefixed-shape assertion, spot-check joins) that raises on any mismatch; implement `downgrade()` (strip prefix) symmetrically.
- **Compatibility resolver**: a single normalization dependency/path-converter at the API boundary — an incoming parcel id without `:` is treated as `phl:<id>`. Old URLs, bookmarks, and previously generated PDF dossiers must keep resolving forever. Apply the same normalization to any parcel id arriving via saved-search criteria, watchlist payloads, or pipeline routes.
- Ingestion: Philly loaders compose the canonical key at the reconciliation boundary (prefix applied in exactly one place).
- Frontend: update anything the Slice-0 inventory flagged as assuming the bare 9-digit shape (route params, id parsing, dossier links). The UI may continue to *display* the local key; it must *round-trip* the canonical one.
- **Tests**: migration test against a PostGIS testcontainer (seed old-shape rows across parent+children, upgrade, assert integrity and prefix, downgrade, assert restoration); resolver unit tests; end-to-end equivalence `GET /parcels/056219700 ≡ GET /parcels/phl:056219700`; one golden-parcel verdict recompute asserting output unchanged.
- **Merge ritual** (rule 5 above): backup confirmed → approval → merge → I run the post-deploy spot-checks you list in the PR body (old bare URL, a saved watchlist item, a regenerated PDF).

---

## Slice 2 — B2: `geom_local` and the market-predicate audit
**Branch: `feat/expansion-b2-geom-local`** · Spec: PRD §B2 · ADR: the second authored above

- Rename `geom_2272 → geom_local` everywhere (models, raw SQL, MVT functions) via an Alembic column rename; relax the geometry typmod so the column accepts per-row SRIDs (determine the PostGIS-safe path — constraint drop vs. typed alter — and preserve or rebuild the GiST indexes; state which in the PR body). All existing rows remain SRID 2272; **no data transform**.
- Ingestion derives `geom_local` via `ST_Transform(..., market.local_srid)` — for `phl` this is a no-op by construction.
- **Market-predicate audit**: work through the Slice-0 checklist of cross-parcel spatial queries (comps, assemblage neighbors, street access, flood/historic intersects, area search, any new modules' queries) adding a `market_code` join/predicate to each. Check each item off in the PR body.
- **Synthetic two-market isolation test** (the Phase-P keystone test, runs in CI from now on): plant a fake `zzz` market whose parcels sit at coordinates that would collide with Philadelphia if the predicate were missing; assert comps, assemblage, street access, and area search never cross markets; assert a `zzz` parcel's verdict computes without touching `phl` data.
- Assert the golden-parcel verdicts are unchanged.

## Slice 3 — B3: transports + market-keyed ingestion registry
**Branch: `feat/expansion-b3-ingestion-registry`** · Spec: PRD §B3 · ADR: the third authored above

- Registry re-keyed `(market, dataset)`; `ingest_all` becomes `ingest_market('phl')`; worker cron updated; admin datasets page groups by market.
- `dataset_freshness` gains `market_code` (migration, backfill `'phl'`, uniqueness updated).
- Per-market **source config as data** per the ADR decision (market row jsonb or a `market_source` table): migrate the Philly singleton endpoints into it with a `Settings` fallback so nothing breaks if a row is missing.
- New transport clients, built and tested but wired to no live market yet: `CkanDatastoreClient` (keyset-chunked datastore SQL, mirroring the Carto client's discipline — Wave 1 consumer) and `ExtractClient` (checksummed file download → staging, idempotent re-runs — Wave 0 consumer). Unit tests plus one recorded-fixture integration test each. If Slice 0 found a raw-landing layer, `ExtractClient` writes through it; otherwise implement the minimal raw-capture path for `ExtractClient` only and note the Amendment-01 alignment in the ADR's consequences.
- Nightly Philadelphia ingestion must run unchanged — verify by running `ingest_market('phl')` against dev and diffing freshness rows.

## Slice 4 — B4: per-market key normalization protocol
**Branch: `feat/expansion-b4-normalizers`** · Spec: PRD §B4

- Extract the existing reconciliation logic into a `KeyNormalizer` protocol with `PhlKeyNormalizer` as the first implementation (behavior byte-identical; the existing golden-file tests move over unmodified and must pass unchanged).
- Registry keyed by market; the canonical-key composition from Slice 1 becomes the protocol's job (one place, per market).
- Do **not** implement `hbg`/`pgh` normalizers — those belong to their waves. The protocol, the registry, and `phl` only.

## Slice 5 — B10: backend market scope (meeting the shipped frontend)
**Branch: `feat/expansion-b10-market-scope`** · Spec: PRD §B10

- `/search`, `/search/area`, `/leads`, and `SearchCriteria` accept a `market` parameter defaulted to `'phl'`, populated from however the frontend's route scope communicates it (per the Slice-0 finding — add the smallest bridge if it currently sends nothing).
- `saved_search` and `neighborhood` gain `market_code` (migrations, backfill `'phl'`); the saved-search matcher and leads queries scope by it.
- MVT functions add `market_code` to feature properties (tiles regenerate live; no backfill).
- New tiny endpoint `GET /markets` (code, name, center, bounds, zoom, launch_status) and switch the frontend's map fly-to/bounds to consume it instead of hardcoded Philadelphia constants — smallest change that removes the hardcode; if the constants are deeply embedded, flag it and defer the wiring to Wave 0 rather than refactoring broadly.
- Regression: full golden-parcel pass (search by address, area search, leads, saved-search match run) asserting identical results to pre-Phase-P behavior.

---

## Phase P definition of done

- Five branches merged in order, each deploy confirmed healthy, with these production spot-checks passing after the final merge: an old bare-key URL resolves; a pre-existing watchlist item still diffs correctly; a PDF dossier regenerates; nightly `ingest_market('phl')` runs green; admin freshness shows the market dimension; map loads and flies to Philadelphia via `/markets`.
- The synthetic two-market isolation suite runs in CI on every PR.
- Golden-parcel verdicts unchanged end to end (no version bump occurred).
- ADRs merged; PRD §5 discrepancy list from Slice 0 recorded as a note in `docs/` for the Wave-0 prompt.
- Out of scope, deliberately untouched: Harrisburg/Dauphin data, zoning authoring, non-2272 SRIDs in production, branding, per-market deal assumptions, Amendment-01 features.

## After Phase P

Stop. Wave 0 (Harrisburg pilot) gets its own prompt after we review Phase P in production for a few days. Do not begin any Wave-0 work under this prompt.
