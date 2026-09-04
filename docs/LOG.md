# Log

One entry per session. Date, branch, what shipped, what is verified, what was not done.

## 2026-09-04 — chore/product-doc
Shipped: deleted 183 docs (85 ADRs, 46 handoffs, PRDs, wave/recon/launch-readiness/preflight/design) and the old CLAUDE.md; deleted rather than archived, per instruction. Wrote docs/PRODUCT.md, docs/PLAN.md (the rebuild plan, verbatim), docs/LOG.md, and a one-line CLAUDE.md.
Kept: architecture.md, data-sources.md, runbook.md, email.md, data-licenses.md.
Verified: no code reads any deleted file — the only reference is a string in an assertion message (accounts/tests/test_entitlement_consistency.py:106) that dies with tiers in Step 1.5. mynotes.txt / lotscope.txt are untracked and were never committed (`git log --all` on both paths is empty), so nothing leaked through git.
Not done: Step 0.1 item 3 — data-sources.md still carries hbg/pgh/wlm, architecture.md still describes four markets. Both are honest only after Step 0.2 removes those code paths; fold them into that session.
Not done: no gates run (docs-only change, no code touched).
