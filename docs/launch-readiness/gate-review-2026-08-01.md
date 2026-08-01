# Public-launch gate review — 2026-08-01

Slice LR-12. Reviews every gate in `docs/PRD-amendment-03-launch-readiness.md` against measured state and records one decision.

**Measurement date:** 2026-08-01 · **Reviewed by:** Claude Code · **`main`:** `72fa77b` · **production:** `54cd4a5`

**Decision: PAUSE.** Do not open the paid beta. Detail in §3.

---

## 1. Why this review does not simply restate `gates.md`

`gates.md` records the LR-0 baseline. Several of its `Current state` entries are now wrong in the product's favour, and one backlog status is wrong in the product's favour in a way that would have mattered.

Every finding below was measured against code, the production database, or a live endpoint on the review date. Where a status could not be confirmed to its acceptance criteria, it is marked *unconfirmed* rather than closed.

### 1.1 Backlog statuses that did not survive measurement

| Ticket | Backlog said | Measured 2026-08-01 |
|---|---|---|
| LR-B-001 field-state taxonomy | Not started | **Substantially shipped** — ADR-0065, `verdict/trust.py` with per-field method versions and explicit not-evaluated reasons; 550,976 of 550,976 phl verdicts carry `field_trust`. Full acceptance not confirmed (see §2 G3) |
| LR-B-004 correction workflow | Not started | **Partial** — reporting is live and reachable; operator triage is not (§1.2) |
| LR-B-002 by-right qualifier | Not started | **Accurate.** No qualifier string exists on by-right wording; searched `VerdictPanel.vue` and sibling components |
| LR-B-029 support route | Not started | **Accurate.** No support address anywhere in `backend/src`, `frontend/src`, or `.env.example`; the only match is a test fixture |
| LR-B-033 backup and restore | Not started | **Closed 2026-08-01** — weekly schedule installed, restore performed (`gates.md` G6) |

Four of eleven open P0 statuses were wrong. **This is the third consecutive slice in which stale statuses changed the shape of the work** — LR-10 found the same for LR-B-026/027, and LR-B-033 was mostly built. The backlog is not a reliable statement of what exists; measurement is.

### 1.2 A defect found by this review

**LR-9C's admin correction endpoints have no consumer.** `GET /admin/corrections` and `PATCH /admin/corrections/{id}` exist and are tested. No page, component, or API-client method in `frontend/src` calls either. `frontend/src/lib/api.ts` has `reportCorrection` and `getOwnCorrections` and nothing for triage.

LR-B-004's acceptance criteria require that *"triage status is visible to an operator."* Today an operator would have to call the API by hand. The correction *route* is live — a user can report, and see their own reports — so the G1 criterion "correction route live" is met. **LR-B-004 itself is not.**

This is the pattern the programme keeps repeating, one layer up each time: ADR-0065's `field_trust` shipped without persistence; LR-6A/6C/6D were unreachable until 6E; LR-9C found service functions with no endpoint and built the endpoints — then stopped before the UI that consumes them. **Check the call path to a user, not to the next layer.**

Not fixed here: LR-12 is documentation-only unless a newly discovered P0 defect requires its own branch. This is a P0 acceptance gap rather than a production defect — nothing is broken for users, and no data is at risk — so it is recorded and left for its own slice.

---

## 2. Gate-by-gate

Each gate carries the seven fields LR-12 requires.

### G1 — Controlled paid beta

| Field | |
|---|---|
| **Status** | **Not met** |
| **Evidence source** | `backlog.md` parsed 2026-08-01 (37 tickets); production database; live endpoints |
| **Measurement date** | 2026-08-01 |
| **Owner** | Owner (commercial, legal); Claude Code (implementation) |
| **Open risk** | Selling to an invited cohort with no published terms, no verified billing, and no error visibility |
| **Exception** | None taken. LR-B-028 and LR-B-033 are no-exception; LR-B-033 is now closed |
| **Decision** | **Reject.** Do not open the beta |

12 P0 tickets. **Two closed** (LR-B-003 §8.4 audit, LR-B-033 backup). Of the ten remaining:

| Blocked on | Tickets |
|---|---|
| **Owner or external** | LR-B-018, LR-B-019 (vendor approval) · LR-B-028 (legal copy) · LR-B-029 (support address) · LR-B-030 (Stripe) · LR-B-032 (email) · LR-B-034 (GitHub plan) |
| **Unblocked engineering** | LR-B-002 (by-right qualifier) · LR-B-004 (operator triage UI) |
| **Unconfirmed** | LR-B-001 (appears shipped; needs acceptance check) |

**Only two open P0s are engineering work this team can start today.** The gate is owner-gated, not engineering-gated — the single most useful fact in this review.

### G2 — Broad public launch

| Field | |
|---|---|
| **Status** | **Not met** |
| **Evidence source** | G1; `backlog.md` P1 counts |
| **Measurement date** | 2026-08-01 |
| **Owner** | Owner |
| **Open risk** | Unvetted customers arriving with no founder contact against unreviewed Philadelphia output |
| **Exception** | None available — G2 requires G1 |
| **Decision** | **Reject.** Not assessable until G1 and G4 move |

23 P1 tickets: 2 done, 1 partial (LR-B-035), 2 owner-blocked, 18 not started. §17.4 beta-success evidence cannot exist because no beta has run.

### G3 — Product trust

| Field | |
|---|---|
| **Status** | **Not met — closest to met of any gate** |
| **Evidence source** | `verdict/trust.py`; production `parcel_verdict`; `missing-data-audit.md`; `ParcelDossier.vue`; component search for qualifier strings |
| **Measurement date** | 2026-08-01 |
| **Owner** | Claude Code (implementation); owner (contract approval) |
| **Open risk** | A user reads a by-right conclusion as a zoning determination |
| **Exception** | **No exception** for §8.4 — and §8.4 is satisfied |
| **Decision** | **Conditionally accept on closing LR-B-002.** One criterion outstanding, and it is unblocked |

| Criterion | State |
|---|---|
| Field-state taxonomy live across material fields | **Met** — `trust.py`, 100% `field_trust` coverage on phl (550,976/550,976) |
| Freshness visible at point of use | **Met** — `_source_ages` feeds the dossier's data-coverage chip |
| §8.4 audit complete, zero prohibited translations | **Met** — LR-B-003 marked Complete 2026-07-28, six findings closed |
| Correction workflow live | **Met** for users (report + own view, reachable from every dossier); **operator triage missing** (§1.2) |
| By-right wording carries the LR-B-002 qualifier | **Not met** — no qualifier found |

ADR-0067's *"Screening result"* framing improves the recommendation surface, but it is not the by-right qualifier LR-B-002 specifies, and should not be counted as one.

### G4 — Philadelphia gold set

| Field | |
|---|---|
| **Status** | **Not met** |
| **Evidence source** | `backend/data/goldset/`; `docs/launch-readiness/gold-set/README.md` |
| **Measurement date** | 2026-08-01 |
| **Owner** | Owner (engage a qualified reviewer); Claude Code (framework) |
| **Open risk** | Philadelphia output has never been checked against reality by someone qualified to judge it |
| **Exception** | **No exception** for unresolved Critical errors (LR-Q003) |
| **Decision** | **Reject.** Blocked on a human the project has not engaged |

The framework is built and honest about its own limits: `review_status` defaults to `unreviewed` and the schema refuses `reviewed` without a named reviewer and date. The only committed data is `phl-sample.jsonl` — **three synthetic cases**. The real set (`phl.jsonl`) is gitignored and does not exist on this machine.

Requirement is ≥100 parcels across every LR-Q001 category with professional review. Current: **0 reviewed**. This is the largest single distance to launch, and no engineering effort shortens it.

### G5 — Commercial infrastructure

| Field | |
|---|---|
| **Status** | **Not met** |
| **Evidence source** | `.env.example` (six empty `STRIPE_*` variables); `accounts/billing.py` |
| **Measurement date** | 2026-08-01 |
| **Owner** | Owner (Stripe account, pricing approval) |
| **Open risk** | Charging customers through a path never exercised against Stripe |
| **Exception** | Standard |
| **Decision** | **Reject.** Blocked on LR-B-030 |

Implementation exists and handles four subscription events. No products created, pricing unapproved, never exercised. This also blocks E2E flows 10–11 (G6).

### G6 — Operations

| Field | |
|---|---|
| **Status** | **Not met — one blocker, and it is a purchase** |
| **Evidence source** | `gates.md` G6 restore record; VM crontab; CI run 30678138666; `ci.yml` |
| **Measurement date** | 2026-08-01 |
| **Owner** | Owner (GitHub plan); Claude Code (implementation) |
| **Open risk** | A red merge can reach `main`; two billing flows are unautomated |
| **Exception** | Branch protection may be waived with a recorded compensating control — one is in force (below) |
| **Decision** | **Conditionally accept** with the compensating control recorded, pending LR-B-034 |

| Criterion | State |
|---|---|
| Scheduled off-machine backups | **Met** — weekly cron + pre-migration; 30-day retention at script and bucket |
| Performed restore test | **Met** — 2026-08-01, rc=0, all counts identical to live |
| Documented RTO/RPO | **Met** — RPO 7 days (matching the weekly schedule), RTO 1 hour, now evidence-based |
| Migration rollback | **Met** — documented; every migration has `downgrade()` |
| Incident runbook | **Met** — `docs/runbook.md` |
| 14 E2E flows in CI | **12 of 14** — flows 10–11 await Stripe |
| Protected `main` | **Not met** — 403, Pro-only |

**Compensating control for branch protection:** wait for `gh pr checks` to show all four jobs green before merging, because `gh pr merge --auto` silently degrades to an immediate merge when no required checks exist. This is a convention, not an enforcement, and it has failed once (#35 merged with checks pending).

### G7 — Legal and policy

| Field | |
|---|---|
| **Status** | **Not met** |
| **Evidence source** | `GET /api/policies` on production, 2026-08-01; `policy_document` table |
| **Measurement date** | 2026-08-01 |
| **Owner** | **Owner** — Amendment 03 §LR-P003 forbids Claude Code inventing final legal terms |
| **Open risk** | Taking money with no Terms, Privacy, refund, or correction policy in force |
| **Exception** | **No exception** (LR-B-028) |
| **Decision** | **Reject.** Hard blocker; nothing but owner-supplied copy moves it |

The baseline entry — *"no Terms, Privacy, refund, or correction policy exists anywhere... No `/terms` or `/privacy` route"* — is **stale**. LR-9D shipped the surfaces: all six required policies are declared and served at `/legal/:slug`, and `GET /api/policies` returns them.

**All six are `published: false`, and `SELECT count(*) FROM policy_document WHERE published_at IS NOT NULL` returns 0.** The machinery is complete and the content is absent. An unpublished policy renders an explicit notice and nothing else — deliberately, since placeholder legalese is indistinguishable from the real thing to a reader.

So the gate is exactly as far from met as before; only the reason changed, from "not built" to "not written."

### G8 — Analytics and monitoring

| Field | |
|---|---|
| **Status** | **Not met** |
| **Evidence source** | Dependency search across `backend/pyproject.toml` and `frontend/package.json`, 2026-08-01 |
| **Measurement date** | 2026-08-01 |
| **Owner** | Owner (vendor approval) |
| **Open risk** | A production error is invisible unless a user reports it; no funnel evidence for §17.4 |
| **Exception** | Standard |
| **Decision** | **Reject.** Blocked on LR-B-018/019 vendor approval |

Confirmed unchanged: no PostHog, Sentry, Mixpanel, Amplitude, Plausible, OpenTelemetry, or Datadog in either manifest. `structlog` JSON logging and `ops/alerts.py` dataset-failure alerting exist, the latter inert until SMTP is configured (LR-B-032). No correlation identifier.

This gate compounds: without error monitoring, a paid beta produces anecdotes instead of the §17.4 evidence G2 requires.

### G9 — Customer evidence

| Field | |
|---|---|
| **Status** | **Not met** |
| **Evidence source** | Production `app_user`, 2026-08-01 |
| **Measurement date** | 2026-08-01 |
| **Owner** | Owner |
| **Open risk** | No evidence any customer finds the verdict trustworthy or useful |
| **Exception** | Standard |
| **Decision** | **Reject.** Cannot begin until G1 |

10 accounts, of which **1 is not obviously a test account**. Zero corrections filed. No paid beta has begun, so no §17.3 feedback record exists.

---

## 3. Decision

**PAUSE.**

Of the three allowed decisions, *extend paid beta* is unavailable — the beta never started, so there is nothing to extend. *Launch* requires every P0 closed. The remaining option is the correct one on its own terms: **legal, commercial, and observability risk are unacceptable for taking money today.**

Three things make this concrete, and none is an engineering opinion:

1. **No published legal terms** (G7) — a no-exception gate; six policies exist and none is written.
2. **Billing never exercised against Stripe** (G5) — the first real charge would be the first real test.
3. **No error monitoring** (G8) — a failure in a paying customer's session would be invisible.

### What this pause is not

It is not a judgement that the engineering is weak. Measured today: 881 backend unit tests and 199 frontend, 12 of 14 E2E flows automated, a proven backup with a performed restore, 100% field-trust coverage on 550,976 Philadelphia verdicts, and a four-market platform in production. G3 and G6 are each one blocker from acceptance, and **only two open P0s are work this team can start without the owner.**

The gap to a paid beta is overwhelmingly **owner actions**: legal copy, Stripe credentials, a support address, two vendor approvals, a GitHub plan, and engaging a reviewer for the gold set.

### Recommended sequence

**Owner, in dependency order:**

1. **LR-B-028 legal copy** — hard blocker, no exception, and every other item is wasted without it
2. **LR-B-030 Stripe** — unblocks G5 and E2E flows 10–11, closing G6's E2E criterion
3. **LR-B-018/019 vendor approval** — G8, and the precondition for §17.4 evidence
4. **LR-B-029 support address** and **LR-B-032 email** — both small; email also activates the correction and ops mail already built and dormant
5. **LR-B-034 GitHub Pro** — closes G6's last blocker for roughly $4/month
6. **LR-B-008 gold-set reviewer** — longest lead time of anything on this list; worth starting first even though it gates last

**Engineering, available now:**

1. **LR-B-002** — the by-right qualifier; the only thing standing between G3 and acceptance
2. **LR-B-004 operator triage UI** — closes the acceptance gap in §1.2
3. **LR-B-001 acceptance confirmation** — likely a status correction rather than work

### Next review

When LR-B-028 and LR-B-030 have both landed, or in one month, whichever comes first. G4 should be re-measured whenever a reviewer is engaged, since it has the longest lead time and gates G2 alone.

---

## 4. Method and limits

Measured on 2026-08-01 against `main` `72fa77b` and production `54cd4a5`: the production database over `gcloud compute ssh`; live endpoints on `parcelphl.online`; source and dependency manifests; CI run 30678138666; the VM crontab.

**No owner or external action was marked complete.** Every such item is recorded as blocked with its blocking ticket.

**No metric was redefined after seeing the result.** One figure was restated *before* this review and for a stated reason: the RPO moved from 24 hours to 7 days when the schedule was set to weekly, because the configuration never supported 24 hours.

**Limits.** Three claims rest on code inspection rather than execution: LR-B-001's "every material field exposes a state" was verified by structure, not by enumerating fields against the contract; G3's freshness criterion was checked at one dossier; and no authenticated production session was exercised by a human — E2E covers those flows against a CI fixture database, which is strong evidence and not the same thing.
