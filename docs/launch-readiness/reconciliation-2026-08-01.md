# Launch-readiness backlog reconciliation — 2026-08-01

Every LR-B item checked against running code, the live API, and production data rather than against its recorded status. Performed because the recorded statuses had drifted far enough to misrepresent the board in both directions.

**Headline: 13 items marked "Not started" are shipped.** Three more are partially shipped. No item claimed Done turned out to be undone.

The drift runs the opposite way from the last audit (`measure-dont-trust-ticket-status`, where five consecutive slices overstated progress). The lesson survives the reversal and generalises: **the status field is unreliable in both directions and must be measured, never read.**

## Method

- Feature presence checked by calling the running API, not by finding a file.
- Counts (`checklist` items, `freshness` sources, gold-set records, screening labels) read from live responses or production SQL.
- Where an acceptance criterion needs a judgement the code cannot settle, the item is marked **Needs criteria review** rather than guessed either way.

## Corrections

### Marked "Not started", actually shipped (13)

| Item | Evidence |
|---|---|
| LR-B-005 source freshness | `GET /parcels/{n}/freshness` returns **8 sources**, matching the §8.3 requirement; `FreshnessPanel.vue` renders them on the Docs tab |
| LR-B-006 flagship framing | `MarketSwitcher` carries a `flagship` badge for Philadelphia and `pilot` for the others; visible in the rendered accessibility tree |
| LR-B-009 screening recommendation | `verdict/decision.py` + ADR-0067; **all six labels present in production data** (`strong_candidate`, `worth_investigating`, `high_entitlement_risk`, `economics_unattractive`, `insufficient_data`, `likely_pass`) |
| LR-B-011 financial headline | `DealPanel.vue` with "Show assumptions and formula"; every assumption carries an `origin` |
| LR-B-012 top deal killers | `lib/deal-killers.ts` + `rank_deal_killers`, deterministic by (severity, decision impact, code) and unit-tested |
| LR-B-013 required next checks | `ChecklistPanel.vue` + ADR-0068; checklist is gap-driven with `not_evaluated` surfaced |
| LR-B-014 score dimensions | `WhyScoreDrawer.vue` + `lib/verdict-explain.ts` exposing weighted dimensions; existing score preserved |
| LR-B-017 variance guardrails | `VarianceOutlookLine.vue` + ADR-0050 (9,687 appeals) |
| LR-B-021 assumption inventory | `GET /parcels/{n}/underwriting` returns **12 assumptions**, each with `origin`, plus MAO `formula`, `inputs`, `exclusions`, `unavailable_inputs` |
| LR-B-022 underwriting profiles | `/underwriting/profiles` CRUD, `profile_id`-addressable |
| LR-B-023 scenarios | **3 cases** returned with a `case_version` |
| LR-B-024 sensitivity | Real 2-D table (`exit_multipliers` × `cost_multipliers`) with `available` / `unavailable_reason` gating |
| LR-B-025 dossier underwriting | `UnderwritingPanel.vue` mounted on the dossier Deal tab |

### Marked "Not started", partially shipped (3)

| Item | Done | Outstanding |
|---|---|---|
| LR-B-007 gold-set structure | Record format, `make gold-set` evaluator, README, category schema | **3 synthetic records against the required 100.** This is the G4 blocker |
| LR-B-015 buildability checks | The five-value `ChecklistStatus` enum the ticket asks for | **10 live checks against LR-B001's ~17.** Yards, unit density, parking and loading, utilities, deed restrictions, subdivision, master-plan requirement are still absent |
| LR-B-020 metrics dashboard | `OpsPage.vue` + `/admin/ops/{fleet,gates,markets,sheriff-coverage}` | Whether all 12 required metrics are reportable is unverified |

### Needs criteria review (2)

| Item | Why |
|---|---|
| LR-B-010 likely development program | `recommended_units` and assumptions exist, but "distinguishes verified rules from calculated geometry and assumptions; cites standards version" is a wording judgement not settled by the code |
| LR-B-016 buildability confidence rules | The invariant is stated in the PRD, not the ticket; verifying "holds across all markets" needs that definition |

### Statuses that were accurate (19)

Done and confirmed: **LR-B-001** (550,976 of 550,976 phl verdicts carry `field_trust`), **LR-B-002**, **LR-B-003**, **LR-B-004**, **LR-B-026**, **LR-B-027**, **LR-B-033** (restore performed).

Genuinely not started: **LR-B-029** (no support address anywhere in `backend/src`, `frontend/src`, or `.env.example` — the only match is a test fixture), **LR-B-031** (no audit performed).

Blocked, and the block is real: **LR-B-008** (needs LR-B-007's 100 parcels plus human reviewers), **LR-B-018** (no analytics instrumentation in the codebase), **LR-B-019** (no correlation ID in `core/logging.py` or the app factory), **LR-B-028**, **LR-B-030**, **LR-B-032**, **LR-B-034**, **LR-B-036** (no feedback endpoint exists).

Partial and correctly described: **LR-B-035** — 12 of 14 flows automated; flows 10 and 11 are `test.skip` in `10-billing.spec.ts`, declared rather than silently missing.

Deferred by PRD: **LR-B-037**.

## What this changes

**Engineering is much closer to launch-ready than the board showed.** Of 37 items, 20 are shipped, 4 partial, 2 need a criteria judgement, 10 are blocked on owner or external action, and 1 is deferred.

**The critical path is unchanged, and is not engineering.** The P0s that remain are LR-B-028 (legal copy), LR-B-030 (Stripe — which also unblocks e2e flows 10–11), LR-B-018/LR-B-019 (vendor approvals), LR-B-032 (email), LR-B-034 (branch protection), and LR-B-029 (support address, which needs an address before there is a surface to build).

**The longest pole is LR-B-007 → LR-B-008.** The gold-set framework exists; it holds 3 synthetic records against a required 100, and the review is human work. Nothing in engineering shortens it, which is the argument for starting it first.

**One real engineering gap surfaced that the board had buried under "Not started".** LR-B-015 is not untouched work — it is a two-thirds-complete feature missing seven named checks. That is a far more actionable statement than "Not started", and it is P1.
