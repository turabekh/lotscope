# ADR-0071 — Playwright for critical end-to-end flows

Status: accepted (2026-08-01)

Required by `docs/PRD-amendment-03-launch-readiness.md` §LR-P007 (Slice LR-10 — Operations and critical E2E). Backlog ticket LR-B-035. Gate G6.

## Context

The repository has 1,174 backend tests and 138 frontend unit tests, and no end-to-end coverage at all. `make e2e` has existed since the frontend slice as a stub that prints "not implemented yet" and exits 1. CLAUDE.md §2 names Playwright in the stack, but nothing was ever installed — no config, no dependency, no CI job. LR-P007 names fourteen flows that must be automated.

The gap is not theoretical. This is the specific failure it leaves open:

> A deploy on 2026-08-01 shipped a five-item navigation and a `FirstSteps` checklist to production. Both were verified only by reading the built JavaScript bundle for the expected route names, because confirming that either actually *renders* requires an authenticated browser session. Unit tests proved the components were correct in isolation; nothing proved a real user reaching them.

Reading a bundle is not a substitute for loading the page. Every flow LR-P007 names has the same shape: correct parts, unproven whole.

Three constraints shape the decision.

**A new dependency needs approval.** CLAUDE.md §18 forbids adding dependencies unilaterally, which is why LR-B-035 sat as "blocked by owner action" rather than as engineering work.

**CI minutes are a real budget.** `ci.yml` runs on every branch push, which is deliberate: branch protection is impossible on the current GitHub plan (both classic protection and rulesets return 403 — see `docs/handoff/0029-2026-07-28.md`), so CI-on-push is the only enforcement-adjacent control that exists. Measured cost today is three jobs and 229 job-seconds, roughly five billable minutes per run against the 2,000-minute monthly allowance.

**Two of the fourteen flows cannot be built yet.** Flows 10 (start checkout) and 11 (upgrade) require Stripe, which has no credentials configured — six empty `STRIPE_*` variables in `.env.example` — and is blocked on LR-B-030.

The dependencies LR-B-035 declares, LR-B-026 (navigation consolidation) and LR-B-027 (buy-box onboarding), are both marked "Not started" in the backlog. Both have in fact shipped, as LR-7A and LR-7B respectively. The backlog is stale, not the code; nothing blocked this work except the approval.

## Decision

**Adopt Playwright for end-to-end coverage of the LR-P007 flows, Chromium only, running on every branch push.**

### 1. Chromium only

One browser engine. Flow 14 (the core mobile path) is covered by a second Playwright *project* using device emulation against the same Chromium build, not by a separate engine.

Cross-engine rendering bugs are real but rare, and they are not what LR-P007 is protecting against — it is protecting against a broken flow, which reproduces identically across engines. Firefox and WebKit would roughly triple browser install and run time to defend against a failure mode this product has never had.

### 2. Every branch push, alongside the existing jobs

The e2e job joins `lint-type-unit`, `integration`, and `web` on the same `push: branches: ['**']` trigger.

The cheaper alternative — running e2e only on `main`, or only nightly — was rejected because it inverts the purpose. With branch protection plan-blocked, the working control is that a branch is green *before* a human merges it. An e2e suite that runs after the merge tells you about a regression you have already shipped.

To keep that affordable, all four jobs gain `paths-ignore: ['docs/**']`. Documentation-only commits are frequent in this repository — handoffs, ADRs, backlog updates — and currently cost a full CI run each.

### 3. Twelve flows now, two on Stripe

Flows 1–9 and 12–14 are built now. Flows 10 and 11 land with LR-9A when Stripe credentials arrive.

Deferring the whole suite until all fourteen are buildable was rejected: LR-B-030 has no date, and it would trade twelve flows of real coverage for an acceptance criterion met on paper. `make e2e` therefore reports the two Stripe flows as explicitly skipped rather than silently absent, so the gap is visible in the run output and cannot be mistaken for coverage.

### 4. A dedicated e2e fixture, not the demo dataset

`backend/data/demo/demo.sql` cannot seed CI. It predates market scoping: it inserts parcels with no `market_id` and bare parcel numbers (`888000001`) where the schema now expects the market-prefixed form (`phl:888000001`). Reviving it would mean maintaining a preview dataset and a test fixture in one file with two different consumers.

The e2e fixture is separate, owned by this slice, and seeds the minimum needed to drive the flows: one market, a small set of parcels with geometry, zoning, comps, and computed verdicts.

### 5. Selectors

Prefer accessible selectors — role, label, text. Add `data-test` attributes only where no stable accessible handle exists. This matches the existing convention: the repository already uses `data-test` (29 attributes across 12 files), concentrated in recently-built components.

E2E fixtures never use production credentials. Each run registers its own user against the test database, which is also what flow 1 exercises.

## Consequences

**Cost.** One added job, estimated 5–9 minutes per run, against ~5 today. The `paths-ignore` filter offsets part of it by removing docs-only runs entirely.

**A slower feedback loop on every push.** The e2e job will be the long pole in CI. This is the price of the coverage and is accepted.

**Flakiness is a real risk and is treated as a defect.** CLAUDE.md §12 requires no flaky tests — fix or delete. A flaky e2e suite is worse than none, because it trains people to ignore a red gate that is also the only gate. Any flake is fixed or the test is removed.

**Fourteen-of-fourteen is not claimed.** Gate G6 stays unmet on the E2E criterion until flows 10 and 11 exist. What this ADR delivers is twelve flows and the infrastructure; the gate closes with LR-9A.

**Not addressed here.** The other two G6 blockers are untouched: LR-B-033 (backup retention and a performed restore test) and LR-B-034 (branch protection, which needs a GitHub plan change). Note that the pre-migration backup *mechanism* now works unattended and was proven on 2026-08-01, but retention policy, RTO/RPO, and a restore test remain undocumented.
