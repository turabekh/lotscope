# Log

One entry per session. Date, branch, what shipped, what is verified, what was not done.

## 2026-09-04 — chore/product-doc
Shipped: deleted 183 docs (85 ADRs, 46 handoffs, PRDs, wave/recon/launch-readiness/preflight/design) and the old CLAUDE.md; deleted rather than archived, per instruction. Wrote docs/PRODUCT.md, docs/PLAN.md (the rebuild plan, verbatim), docs/LOG.md, and a one-line CLAUDE.md.
Kept: architecture.md, data-sources.md, runbook.md, email.md, data-licenses.md.
Verified: no code reads any deleted file — the only reference is a string in an assertion message (accounts/tests/test_entitlement_consistency.py:106) that dies with tiers in Step 1.5. mynotes.txt / lotscope.txt are untracked and were never committed (`git log --all` on both paths is empty), so nothing leaked through git.
Not done: Step 0.1 item 3 — data-sources.md and architecture.md deferred to refactor/philadelphia-only, where they can be written from the real tree. (Done there.)
Not done: no gates run (docs-only change, no code touched).

## 2026-09-04 — refactor/philadelphia-only
Shipped: Pittsburgh, Harrisburg and Wilmington removed. 61 files deleted, ~10,100 lines net. markets/ and core/markets.py replaced by core/market.py; capability tables, hidden surfaces, forced-sale labels, distress profiles and comp-selection policy all collapsed to one path; the market query parameter is gone from every endpoint; frontend lost /:market/, stores/market.ts and MarketSwitcher. Migration a1c7e4f90b62 drops repository_listing, market_gate_item and 16 foreign keys to market.code. Gate board and Dauphin repository went with their markets.
Verified: lint + typecheck clean both sides; backend 1100 unit / 540 integration, 0 failed, 0 skipped; frontend 424. Migration up/down round-tripped against the real DB. grep for the nine market terms across backend/src, backend/scripts, frontend/src, frontend/e2e returns nothing.
Not done: ai/scope.py keeps one unreachable non-Philadelphia branch — Step 0.3 owns deleting it. The market table is kept (one row, still read by deal/service.py's override path, which Step 1.1 owns). Old migrations keep their seed data as replay history. The DB still holds 189k non-Philadelphia parcels; no data migration was in scope.
Branch is stacked on chore/product-doc, which must merge first.

## 2026-09-04 — fix/ci-green (merged to main)
Shipped: merged refactor/philadelphia-only to main (ebe827d) and pushed. CI ran for the first time in weeks — billing is evidently fixed — and caught two things my local gate did not: a Playwright test asserting on the deleted MarketSwitcher, and three prettier failures. Both fixed; `make lint` now runs `pnpm format:check` so its "mirrors what CI runs" comment is true.
Verified: main at d11479f, all four CI jobs green (lint-type-unit, web, integration, e2e). Locally: 1100 unit, 540 integration 0 skipped, 424 vitest, Playwright 42 passed serially.
Not done: production is untouched — deploy is workflow_dispatch only and last ran 2026-08-16, so prod still serves the pre-refactor code. Next: owner items for 0.3 (corpus artifacts to /srv/lotscope/corpus/, paid ANTHROPIC_API_KEY with a spend cap).

## 2026-09-04 — feat/corpus-live (Part A: purge)
Shipped: `lotscope data purge-other-markets [--dry-run|--yes]` (exactly one flag required). It builds its deletion graph by walking foreign keys out of `parcel` transitively from SQLAlchemy metadata, plus twelve hand-listed convention-keyed tables, each with a documented reason; a test fails if any `parcel_number` table is missing from the graph. Deletes run child-first in one transaction. Also `docker-compose.yml shm_size: 1gb` and the cd43ff9+ deploy procedure in the runbook.
Verified: purged the local DB — 189,097 parcels and 962,495 rows across 28 tables, 51.3s, after-table all zeros, 588,612 phl parcels untouched. Integration 542 passed / 0 failed / 0 skipped against the purged database; unit 1107; vitest 424; lint and typecheck clean. Playwright not run and not required — this session deletes no component or route.
Found: `lotscope/models.py` imports only 21 of 29 model modules, so walking it sees 8 descendants of parcel where the DB has 15 — the command imports every `lotscope.*.models` instead. This is also why alembic autogenerate proposes destructive drops.
Not done: Part B (corpus load) — blocked on artifacts reaching /srv/lotscope/corpus/ and a paid ANTHROPIC_API_KEY. Nothing has been run against production.

## 2026-09-04 — feat/corpus-load
Shipped: `lotscope corpus load --path <dir> [--dry-run]`, idempotent and resumable — documents carry a content_hash and only changed ones are embedded, rows left without a vector are retried. `GET /health/corpus` (unauthenticated, 503 below 25,000 provisions or 99% coverage). phillycode is now the only retrieval scope: ai/corpus.py, the dual-scope branch, _incumbent_context, source_override, zoning_retrieval_source and fetch_district_documents are gone. models.py registers all 29 model modules with a drift test against information_schema.
Verified: 29,297 provisions / 24 titles / 21,512 documents, 100% embedded, represented 98.19%. Cold load 525.7s, unchanged re-run 6.7s (0 embedded, 21,512 reused). /health/corpus returns 200 ok. A real ask_the_parcel on phl:282038200 (RSA5, vacant) cited 14-701(2)(b) and 14-701(2)(b)[11]#table1 — canonical provision ids, including a derived table document. lint + typecheck clean; unit 1105, integration 540 (0 skipped), vitest 424. Playwright not required: no component or route was deleted (AskBox has no scope toggle; its per-citation source label is provenance and stays).
Corrected: last session's claim that the models.py gap caused destructive autogenerate drops was wrong — env.py's _include_object already skipped unregistered tables. `alembic check` still fails on 58 ops (staging/raw schemas, GeoAlchemy2 geometry reflection, HNSW/partial/expression indexes); migrations stay hand-written.
Not done: nothing run against production. Coverage floor semantics changed mid-session after the first load read 73.43%.
