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
