# Launch gates — LR-0

> **This file is the LR-0 baseline.** Several `Current state` entries below have been overtaken by later slices — G3, G6, and G7 in particular. The measured position, with per-gate evidence and an acceptance decision, is **`gate-review-2026-08-01.md`** (decision: **PAUSE**). Read that first; treat this file as the definition of each gate rather than a report of where it stands.

**Baseline SHA:** `e68f16baa14a2b892ff9d9f62c7b74228dfb137f` · **Assessed:** 2026-07-28
**Requirement source:** `docs/PRD-amendment-03-launch-readiness.md` §16, §17, §18, §23

Every gate below is **not met** at the baseline. No gate is marked met without evidence that exists and can be produced on request. Amendment 03 §16 states explicitly that automated tests do not substitute for real parcel validation, and §24 forbids calling free registrations proof of product-market fit.

**Exception policy (applies to all gates unless a gate states otherwise):** a gate may be waived only by explicit, recorded owner acceptance naming the specific risk accepted and the compensating control. A waiver is recorded in this file with a date. Gates marked *no exception* cannot be waived — they represent legal exposure, data-loss exposure, or material customer harm.

---

## G1 — Controlled paid beta

**Definition:** the product can be sold to a small invited cohort without material risk of customer harm or unrecoverable failure.

| Field | Value |
|---|---|
| **Evidence required** | All P0 backlog tickets closed or explicitly waived; billing verified end to end; correction route live; error visibility live; backup with one performed restore; published legal surfaces; a support route |
| **Evidence source** | `backlog.md` P0 status; Stripe test-mode verification record; restore-test record; deployed `/terms` and `/privacy`; monitoring dashboard |
| **Owner** | Owner (commercial and legal); Claude Code (implementation) |
| **Current state** | **Not met** — 12 P0 tickets open |
| **Blocker** | LR-B-001, LR-B-002, LR-B-003, LR-B-004, LR-B-018, LR-B-019, LR-B-028, LR-B-029, LR-B-030, LR-B-032, LR-B-033, LR-B-034 |
| **Exception policy** | LR-B-028 (legal) and LR-B-033 (backup) are **no exception**. Others may be waived with recorded compensating controls |

---

## G2 — Broad public launch

**Definition:** the product can be sold to unvetted customers arriving without founder contact.

| Field | Value |
|---|---|
| **Evidence required** | G1 met; all P1 tickets closed or waived; §17.4 beta-success evidence; gold set complete (G4); §20 metrics reportable; the §4.1 first session completable unassisted |
| **Evidence source** | `backlog.md`; beta feedback records; gold-set review records; launch dashboard |
| **Owner** | Owner |
| **Current state** | **Not met** — G1 not met; 23 P1 tickets open |
| **Blocker** | G1, G4, G9 |
| **Exception policy** | Standard. §23 defines the definition of done for the amendment |

---

## G3 — Product trust

**Definition:** a user can tell, for every material output, where it came from, how fresh it is, whether it was verified or estimated, and what was not evaluated — and can report it when wrong.

| Field | Value |
|---|---|
| **Evidence required** | Field-state taxonomy live across material fields; freshness visible at point of use; §8.4 missing-data audit complete with zero prohibited translations; correction workflow live; by-right wording carries the §LR-B002 qualifier |
| **Evidence source** | `verdict/schemas.py` contract; §8.4 audit inventory; dossier; correction records |
| **Owner** | Claude Code (implementation); owner (contract approval) |
| **Current state** | **Not met** — trust state exists only at market-category granularity (`markets/capabilities.py`); provenance only at verdict level (`verdict/schemas.py:32-33`); no correction route exists |
| **Blocker** | LR-B-001, LR-B-002, LR-B-003, LR-B-004, LR-B-005 |
| **Exception policy** | **No exception** for §8.4 (missing data presented as clear) — Amendment 03 §22 classes this as material trust risk |

---

## G4 — Philadelphia gold set

**Definition:** Philadelphia output has been checked against reality on a representative parcel set by someone qualified to judge it.

| Field | Value |
|---|---|
| **Evidence required** | ≥100 parcels covering every LR-Q001 category; each with a review status; no unresolved Critical error category; standard-parcel outcomes professionally reviewed; owner acceptance of the residual material-error profile |
| **Evidence source** | Gold-set records under `docs/launch-readiness/gold-set/`; reviewer attestation |
| **Owner** | Owner (engage reviewer); Claude Code (framework and selection) |
| **Current state** | **Not met** — no Philadelphia gold set exists. The 25-parcel packets that exist are Harrisburg and Pittsburgh, both still pending reviewer sign-off |
| **Blocker** | LR-B-007, LR-B-008 |
| **Exception policy** | **No exception** for unresolved Critical errors (LR-Q003: wrong district, wrong permitted use, wrong unit conclusion, missed master-plan requirement, false street access, seriously misleading valuation, missing major restriction presented as clear). Material and Minor may be accepted with a recorded profile |

---

## G5 — Commercial infrastructure

**Definition:** money can be taken, changed, refunded, and reconciled without manual intervention or silent failure.

| Field | Value |
|---|---|
| **Evidence required** | All 11 LR-P001 behaviours verified against Stripe; webhook retry and replay proven idempotent; entitlements consistent across all six §14.4 surfaces; refund procedure documented |
| **Evidence source** | Stripe verification record; entitlement audit; `docs/runbook.md` |
| **Owner** | Owner (products, credentials, pricing approval); Claude Code (verification) |
| **Current state** | **Not met** — implementation complete (`api/billing.py:59-167`, four subscription events handled) but never exercised against Stripe; no products created; pricing unapproved |
| **Blocker** | LR-B-030, LR-B-031; owner Stripe setup |
| **Exception policy** | **No exception** — §22 lists broken billing as P0. Pricing changes must not be combined with entitlement changes (§24) |

---

## G6 — Operations

**Definition:** a production defect can be detected, contained, and recovered from.

| Field | Value |
|---|---|
| **Evidence required** | Protected `main` with required checks; scheduled encrypted off-machine backups with a **performed** restore test; documented RTO/RPO; migration rollback procedure; the 14 LR-P007 E2E flows in CI; incident runbook |
| **Evidence source** | GitHub settings; restore-test record; `docs/runbook.md`; CI run |
| **Owner** | Owner (GitHub plan, backup destination, Playwright approval); Claude Code (implementation) |
| **Current state** | **Not met, one blocker remaining.** CI is armed; deploy has a SHA-drift guard and `/health` verification; **E2E covers 12 of the 14 flows** (ADR-0071); backups are scheduled weekly plus pre-migration, retention is 30 days at both script and bucket, RTO/RPO are documented, and **a restore has been performed** (record below). Outstanding: **branch protection is plan-blocked** (403, Pro-only) and **flows 10–11 await Stripe** |
| **Blocker** | LR-B-034 (LR-B-033 closed 2026-08-01; LR-B-035 partial, awaiting LR-B-030) |
| **Restore-test record** | **2026-08-01** — `lotscope-pre-migration-20260801T000847Z.dump` (454 MB) restored into `lotscope_restore` on the VM. `pg_restore` rc=0, no stderr. Counts identical to live: parcels 550,976 phl / 143,355 pgh / 26,197 wlm / 19,502 hbg; `parcel_verdict` 740,030; `app_user` 10; `deal` 5; `deal_activity` 2; `saved_search` 3. Tables 44 vs 45 — `policy_document` absent and `alembic_version` at `d9f3b1c7e485`, correct for a pre-migration dump. Elapsed 4s download + 4m19s restore. Scratch database dropped; production untouched throughout. **Next test due 2026-09-01.** |
| **Exception policy** | **No exception** for backups (LR-B-033) — data loss is unrecoverable. Branch protection may be waived only with a recorded interim control; the current interim control is: wait for `gh pr checks` to show `lint-type-unit`, `integration`, and `web` green before merging, because `gh pr merge --auto` silently degrades to an immediate merge when no required checks exist |

---

## G7 — Legal and policy

**Definition:** the commercial and informational posture is documented, published, and owner-approved.

| Field | Value |
|---|---|
| **Evidence required** | Published Terms of Service, Privacy Policy, informational-analysis disclaimer, data-source and license disclosures, contact-data and outreach restrictions, refund policy, correction policy — all owner-approved |
| **Evidence source** | Deployed routes; `docs/data-licenses.md`; owner approval record |
| **Owner** | **Owner** — Amendment 03 §LR-P003 states Claude Code may wire approved copy but must not invent final legal terms |
| **Current state** | **Not met** — no Terms, Privacy, refund, or correction policy exists anywhere. Disclaimer fragments only ("Informational only" ×7, "not legal advice" ×1, "not financial advice" ×1). No `/terms` or `/privacy` route |
| **Blocker** | LR-B-028; owner-approved copy |
| **Exception policy** | **No exception.** Taking payment while publishing zoning and valuation conclusions without published terms is direct legal exposure |

---

## G8 — Analytics and monitoring

**Definition:** product usage and production failure are both visible, without leaking personal data.

| Field | Value |
|---|---|
| **Evidence required** | The 16 LR-A001 events emitted; the LR-A002 funnel reconstructable; the nine LR-A003 error categories captured; correlation IDs end to end; the 12 LR-A004 metrics reportable; PII redaction enforced at the interface and tested |
| **Evidence source** | Analytics dashboard; error-monitoring dashboard; redaction tests |
| **Owner** | Owner (vendor and dependency approval, privacy review); Claude Code (implementation) |
| **Current state** | **Not met** — no analytics and no error monitoring exist. Verified by exhaustive search for PostHog, Mixpanel, Amplitude, Google Analytics, Plausible, Sentry, OpenTelemetry, Datadog, Rollbar, Bugsnag, Segment, New Relic, and Honeycomb across source and both dependency manifests; one false positive (`subdivision/service.py:27 _plausible_width`). No correlation identifier exists. `structlog` JSON logging and `ops/alerts.py` dataset-failure alerting do exist, the latter inert until SMTP is configured |
| **Blocker** | LR-B-018, LR-B-019, LR-B-020; owner vendor approval |
| **Exception policy** | Error monitoring is **no exception** — operating a paid product with zero production error visibility is unacceptable. Product analytics may be deferred for a small invited beta if the owner accepts manual measurement, recorded here. PII redaction is **no exception** (§LR-A001) |

---

## G9 — Customer evidence

**Definition:** real customers pay for the product and use it on real acquisition decisions.

| Field | Value |
|---|---|
| **Evidence required** | ≥5 paying customers; ≥5 paying users returning weekly; ≥3 using LotScope on a genuine acquisition decision; ≥1 documented pursue/pass/offer decision materially supported by LotScope; no unresolved critical product-safety issue; a measured support and correction process |
| **Evidence source** | Beta feedback records (§17.3); billing records; correction records |
| **Owner** | **Owner** |
| **Current state** | **Not met** — no paid beta has begun. Production currently has 10 user accounts, of which 9 appear to be test accounts |
| **Blocker** | G1; cohort recruitment; LR-B-036 |
| **Exception policy** | **No exception.** Amendment 03 §24 forbids calling free registrations proof of product-market fit, and §27 states the amendment is complete only when gates are measured with real users and real Philadelphia parcels |

---

## Gate summary

| Gate | State | Primary blocker |
|---|---|---|
| G1 Controlled paid beta | Not met | 12 open P0 tickets |
| G2 Broad public launch | Not met | G1, G4, G9 |
| G3 Product trust | Not met | No field-state taxonomy; no correction route |
| G4 Philadelphia gold set | Not met | No gold set exists |
| G5 Commercial infrastructure | Not met | Billing unverified; no Stripe products |
| G6 Operations | Not met | No backups; branch protection plan-blocked; no E2E |
| G7 Legal and policy | Not met | No published policies |
| G8 Analytics and monitoring | Not met | Neither exists |
| G9 Customer evidence | Not met | Beta not started |

**No gate is met at the baseline.** This is the expected state for LR-0 and reflects that the product is feature-rich but has not yet been made commercially defensible — not that the engineering is weak.
