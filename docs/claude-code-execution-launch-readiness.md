# Claude Code Execution Orders — Launch Readiness Program

## What this document is

This document is the step-by-step implementation order for:

- `docs/PRD-amendment-03-launch-readiness.md`

The PRD amendment defines **what** the launch product must become. This document defines **how Claude Code must execute it safely**.

Do not treat this as permission to implement every slice automatically. Work one approved slice at a time.

---

## 1. Required reading order

Before planning or editing:

1. `CLAUDE.md`
2. `docs/PRD.md`
3. `docs/PRD-amendment-01-monetization.md`
4. `docs/PRD-amendment-02-geographic-expansion.md`
5. `docs/PRD-amendment-03-launch-readiness.md`
6. `docs/design/ia-and-layout.md`
7. relevant ADRs
8. `docs/runbook.md`
9. the latest relevant file under `docs/handoff/`
10. the files and tests for the slice being executed

When documents conflict during the launch phase:

- `CLAUDE.md` controls engineering conduct;
- accepted ADRs control architecture;
- Amendment 03 controls launch priority and product focus;
- the current code and migrations control actual implementation state;
- never assume a prompt document represents unfinished work without reconciling it against `main`.

---

## 2. Standing execution rules

### 2.1 One slice only

For each session:

1. identify the next incomplete approved slice;
2. inspect actual repository state;
3. report what already exists;
4. propose the smallest implementation plan;
5. wait for explicit owner approval when the change is architectural, migration-bearing, contract-changing, pricing-related, or broad;
6. implement only that slice;
7. run all required gates;
8. summarize changes, risks, migration state, rollback, and verification;
9. stop.

Do not begin the next slice automatically.

### 2.2 No feature expansion

During this program:

- do not add new markets;
- do not expand pilot-market scope;
- do not build unrelated features;
- do not redesign unrelated pages;
- do not replace the chosen stack;
- do not introduce speculative abstractions;
- do not delete stable secondary modules merely because they are de-emphasized.

### 2.3 Preserve trust

Any material computed output must preserve:

- source references;
- effective or as-of time;
- computed time;
- method or verdict version;
- missing-data state;
- limitations;
- user override state where applicable.

### 2.4 Do not invent external truth

Claude Code may build mechanisms, tests, templates, and admin workflows for:

- professional parcel review;
- legal copy;
- pricing approval;
- production credentials;
- customer interviews.

Claude Code must not fabricate:

- professional sign-off;
- gold-set results;
- legal approval;
- live Stripe prices;
- production credentials;
- user interviews;
- customer willingness to pay;
- launch-gate evidence.

### 2.5 Comments and docstrings

Follow `CLAUDE.md`: no human-facing code comments or docstrings. Runtime LLM-interface descriptions remain allowed.

### 2.6 Dependencies

Do not add a dependency unless:

- no existing dependency or standard-library solution is reasonable;
- the security, privacy, bundle, operations, and maintenance cost is evaluated;
- the owner approves;
- an ADR is created when the choice has lasting architectural impact.

### 2.7 PII and analytics

Never send the following to product analytics or error-monitoring payloads:

- owner names;
- owner mailing addresses;
- phone numbers;
- email addresses;
- skip-trace payloads;
- deed text;
- authentication tokens;
- exact private notes;
- payment details;
- raw search exports.

Use stable internal identifiers and redacted context.

---

## 3. Git, CI, migration, and deployment rules

1. Start from current `main`.
2. Pull before creating a branch.
3. Use one branch per slice.
4. Never force-push.
5. Never commit secrets, data dumps, gold-set private evidence, or production exports.
6. Use conventional commits.
7. Do not merge until local gates and CI are green.
8. Do not merge without explicit owner approval when requested.
9. Treat a merge to an auto-deploying branch as a deployment.
10. Include in every PR:
   - purpose;
   - PRD requirement IDs;
   - files and modules changed;
   - migration yes/no;
   - verdict-contract/version impact;
   - privacy impact;
   - tests;
   - rollback;
   - post-deploy verification.

### Migration-bearing slices

Before merge:

1. inspect deployment migration behavior;
2. show the exact production backup command;
3. receive confirmation that the backup completed;
4. confirm migration upgrade and downgrade behavior;
5. include a data rollback plan when downgrade is destructive or insufficient;
6. include `git revert` instructions;
7. verify the resulting Alembic head.

### Required gates

At minimum:

```bash
make lint
make typecheck
make test
```

When frontend is touched:

```bash
cd frontend
pnpm lint
pnpm typecheck
pnpm test
```

When critical flows are touched:

```bash
make e2e
```

Use the repository's actual Makefile targets if they differ. Do not claim a gate passed without running it.

---

## 4. Mandatory recon format

Before editing each slice, report:

### Current state

- branch and SHA;
- Alembic head;
- relevant routes, stores, services, schemas, models, migrations, tests, and docs;
- which requirements are already implemented;
- documentation drift;
- known open handoff items;
- production configuration dependencies.

### Gap matrix

| Requirement | Current implementation | Gap | Priority | Proposed change | ADR/migration |
|---|---|---|---|---|---|

### Plan

- exact scope;
- likely files;
- tests;
- migration impact;
- contract impact;
- privacy/security impact;
- rollback;
- manual verification.

Do not edit until the recon is adequate.

---

# Slice LR-0 — Launch baseline and backlog

**Branch:** `docs/launch-readiness-baseline`

## Goal

Reconcile Amendment 03 against the actual repository and create the authoritative implementation backlog.

## Required work

1. Confirm every relevant feature and route currently present.
2. Confirm current verdict version and contract.
3. Confirm current pricing and entitlement configuration.
4. Confirm current navigation and onboarding.
5. Confirm current analytics and monitoring, if any.
6. Confirm billing, email, backup, E2E, legal, and support state.
7. Confirm market launch statuses and public visibility.
8. Identify stale or superseded documents.
9. Create:
   - `docs/launch-readiness/status.md`;
   - `docs/launch-readiness/backlog.md`;
   - `docs/launch-readiness/gates.md`.
10. Mark every PRD requirement as:
    - complete;
    - partial;
    - absent;
    - blocked by owner/external action;
    - deferred.

## Restrictions

- Documentation and tests-of-assumptions only.
- Do not change runtime product behavior.
- Do not trust old prompt documents as current state.
- Do not mark a feature complete merely because a migration or route exists.

## Definition of done

- Owner can see the actual P0/P1/P2 sequence.
- No duplicate work is scheduled.
- Every later slice has a named dependency.
- Architectural and migration risks are identified.
- Documentation gates pass.

---

# Slice LR-1 — Launch market and feature visibility

**Branch:** `feat/launch-market-focus`

## Goal

Make Philadelphia the unmistakable flagship without deleting pilot-market work.

## Required work

1. Confirm market status and capability mechanisms.
2. Add or refine launch-status presentation:
   - flagship or commercially verified;
   - pilot;
   - incomplete or unavailable.
3. Ensure pilot limitations appear before the user relies on the result.
4. Add configuration or capability flags needed to de-emphasize non-launch modules.
5. Preserve direct links and existing stable behavior where reasonable.
6. Avoid hardcoding Philadelphia throughout reusable domain code.

## Acceptance criteria

- A new user understands which market is the verified launch market.
- Pilot markets cannot look equally complete.
- No pilot market is silently promoted.
- No market data is deleted.
- Capability and visibility logic is centralized and tested.

## Tests

- market capability unit tests;
- route and navigation tests;
- pilot notice component tests;
- entitlement interaction tests where relevant.

## ADR review

Required if changing the market-status model, route structure, or capability architecture.

---

# Slice LR-2 — Trust contract and correction workflow

**Branch:** `feat/verdict-trust-contract`

## Goal

Expose verified, calculated, estimated, and unavailable states consistently for material outputs.

## Required work

1. Inventory current provenance fields and source models.
2. Define a shared field-state contract.
3. Decide whether the contract belongs:
   - in the verdict schema;
   - in a presentation schema;
   - in a reusable provenance structure.
4. Preserve backward compatibility where practical.
5. Add source age and limitation data needed by the frontend.
6. Implement a compact freshness panel.
7. Implement missing-data-safe presentation.
8. Add `Report incorrect data`.
9. Store correction reports with verdict and source context.
10. Add admin or support triage access sufficient for paid beta.

## Restrictions

- Do not wrap every trivial field in an unnecessarily large object.
- Do not duplicate provenance already available.
- Do not call a field `Verified` without an identified source policy.
- Do not allow analytics to receive correction attachments or PII.

## Definition of done

- Material verdict fields have a consistent state.
- Missing data cannot render as a clean result.
- Users can see source age.
- A correction can be traced to the exact computed result.
- Contract and integration tests pass.

## ADR and migration

Likely required if changing the verdict API contract or adding correction tables.

---

# Slice LR-3 — Philadelphia gold-set framework

**Branch:** `test/phl-gold-set-framework`

## Goal

Build a reproducible framework for real-world parcel validation without fabricating professional conclusions.

## Required work

1. Create a documented gold-set schema.
2. Support at least:
   - parcel identifier;
   - category;
   - expected official facts;
   - expected preliminary conclusion;
   - reviewer;
   - review date;
   - evidence references;
   - severity;
   - status;
   - notes.
3. Add a safe location for non-sensitive fixtures.
4. Keep licensed, private, or sensitive evidence out of Git.
5. Add deterministic evaluation commands.
6. Produce discrepancy reports.
7. Add admin or CLI support for reviewing current verdict output against expected facts.
8. Document the professional review workflow.
9. Seed only synthetic or publicly reproducible sample cases unless the owner supplies approved evidence.

## Acceptance criteria

- The framework supports at least 100 cases.
- Critical, material, and minor discrepancies are distinct.
- A verdict-version change can rerun the set.
- Results are exportable without PII.
- The system never claims professional approval automatically.

## Definition of done

- Evaluation is reproducible.
- Sample cases demonstrate the workflow.
- Owner has a clear process for filling and reviewing the real set.

---

# Slice LR-4 — Decision-first Parcel Verdict

**Branch:** `feat/decision-first-verdict`

## Goal

Make the top of the dossier answer pursue, investigate, or pass in approximately 30 seconds.

## Required work

1. Add or refine the deterministic screening recommendation.
2. Add the likely development-program sentence.
3. Add a compact financial headline.
4. Rank and show the top three deal killers.
5. Generate required next checks.
6. Show buildability, economics, acquisition access, and risk as separate dimensions.
7. De-emphasize the legacy composite score as a sole headline.
8. Preserve detailed evidence below.
9. Use conditional wording and trust states.

## Restrictions

- Do not introduce an unvalidated new composite score.
- Do not use AI free-form output as the decision source.
- AI may explain deterministic results only when grounded and validated.
- Do not bump the verdict version solely for frontend composition.
- If persisted verdict logic changes, assess and document the version bump.

## Tests

- deterministic recommendation unit tests;
- missing-data cases;
- conflicting-signal cases;
- snapshot or component tests;
- API integration tests;
- accessibility checks for critical alerts.

## Definition of done

- A parcel with critical unknowns cannot show a confident positive result.
- The user can identify the reason and next step without opening every panel.
- Detailed source evidence remains reachable.

---

# Slice LR-5 — Buildability checklist and wording

**Branch:** `feat/buildability-checklist`

## Goal

Replace overly broad buildable/by-right impressions with an explicit checklist of evaluated and unevaluated conditions.

## Required work

1. Map existing zoning and context outputs to checklist items.
2. Define `Pass`, `Fail`, `Potential issue`, `Not evaluated`, and `Not applicable`.
3. Include base rules, overlays, historic context, access, parking, utilities, deed/easement, and subdivision status where data exists.
4. Never infer unavailable checks from silence.
5. Update by-right wording.
6. Rename variance output to historical approval context where applicable.
7. Display sample size and qualification.

## Acceptance criteria

- Base-district eligibility and final development approval are visibly different.
- A user can see exactly which checks LotScope did not perform.
- Master-plan and special-purpose conditions are prominent.
- Thin variance evidence cannot show a misleading percentage.

## ADR review

Required if the domain buildability contract changes substantially.

---

# Slice LR-6 — Professional underwriting

**Branch:** `feat/pro-underwriting`

## Goal

Make MAO, profit, and margin transparent, editable, scenario-based, and reusable.

## Recommended sub-slices

This slice is large. Execute as separately approved sub-slices:

### LR-6A — Assumption inventory and calculation contract

- map existing deal assumptions;
- identify missing cost categories;
- define input origins;
- define deterministic formulas;
- write ADR if contract changes.

### LR-6B — User underwriting profiles

- model reusable defaults;
- market and user precedence;
- CRUD API;
- privacy and ownership tests.

### LR-6C — Scenarios

- base, downside, upside;
- deterministic copy and versioning;
- scenario persistence.

### LR-6D — Sensitivity

- one two-dimensional grid;
- pure calculation;
- no new charting dependency unless approved.

### LR-6E — Dossier experience

- assumption editor;
- reset to defaults;
- show input origin;
- show formula and exclusions;
- save profile and scenario.

## Restrictions

- Unknown required inputs cannot become zero.
- Do not allow stale profile changes to rewrite historical deal results silently.
- Do not mix user-specific assumptions into global parcel truth.
- Store money and percentages with appropriate precision.
- Protect data ownership between users.

## Definition of done

- Two users can underwrite the same parcel differently without changing parcel truth.
- Every headline figure is explainable.
- Base/downside/upside results are reproducible.
- MAO cannot appear falsely precise when required inputs are unavailable.

---

# Slice LR-7 — Focused navigation and onboarding

**Branch:** `feat/launch-acquisition-flow`

## Goal

Reduce cognitive load and make the first session produce a real acquisition result.

## Required work

1. Reconcile Amendment 03 with ADR-0029.
2. Decide whether to:
   - use `Home, Find Lots, Pipeline, Saved, Account`; or
   - retain existing labels while consolidating secondary routes.
3. Create a superseding ADR when required.
4. Preserve route compatibility or add redirects.
5. Consolidate opportunity sources under one discovery mental model.
6. Add buy-box onboarding.
7. Show immediate matching parcels.
8. Guide the first verdict, assumption change, save, and alert.
9. Keep advanced profile setup progressive.
10. Verify mobile behavior.

## Restrictions

- Do not rewrite MapLibre or the entire component system.
- Reuse existing stores and route logic.
- Do not delete secondary modules.
- Do not create a separate mobile product.

## Tests

- router tests;
- navigation tests;
- onboarding-store tests;
- component tests;
- Playwright first-session flow;
- mobile viewport flow;
- keyboard and focus tests.

## Definition of done

- A new user reaches a useful result without founder explanation.
- Primary navigation has no competing duplicate concepts.
- Secondary features remain discoverable without dominating the launch experience.

---

# Slice LR-8 — Product analytics and error monitoring

**Branch:** `feat/launch-observability`

## Goal

Measure the launch funnel and detect failures without leaking sensitive property or owner data.

## Required work

1. Recon existing logging, analytics, and monitoring.
2. Produce a privacy event dictionary.
3. Select vendors only with owner approval.
4. Add centralized frontend analytics abstraction.
5. Add centralized backend event or analytics abstraction when needed.
6. Add error monitoring with redaction.
7. Instrument the PRD events.
8. Add correlation IDs between frontend, API, jobs, and error reports where practical.
9. Add internal launch queries or dashboard instructions.
10. Document disablement and local-development behavior.

## Restrictions

- No owner/contact PII.
- No raw notes or deed text.
- No secrets or tokens.
- No vendor SDK scattered directly across components.
- No analytics failure may block the user workflow.

## Definition of done

- Activation and checkout funnels can be measured.
- Critical frontend and backend failures are visible.
- Event payloads pass privacy tests or inspection.
- Monitoring can be disabled by environment.

---

# Slice LR-9 — Commercial plumbing, support, and policy wiring

**Branch:** `feat/paid-beta-readiness`

## Goal

Make paid-beta account operations reliable and supportable.

## Recommended sub-slices

### LR-9A — Billing verification

- checkout;
- portal;
- plan changes;
- cancellation;
- failed payment;
- webhook replay;
- credits where enabled.

### LR-9B — Email verification

- account;
- reset;
- alert;
- digest;
- billing;
- support.

### LR-9C — Support and correction operations

- support route;
- triage;
- escalation;
- correction status;
- user notification.

### LR-9D — Policy surfaces

- wire owner-approved Terms, Privacy, disclaimers, disclosures, refund, and correction policies.

## Restrictions

- Do not invent final legal copy.
- Do not create production Stripe objects unless explicitly instructed and credentials are available.
- Never place secret values in docs, tests, logs, or commits.
- Test webhooks using provider-supported signatures and fixtures.

## Definition of done

- A paid user can subscribe, manage billing, receive required emails, request help, and report incorrect data.
- Support can trace the relevant account, parcel, and verdict safely.

---

# Slice LR-10 — Operations and critical E2E

**Branch:** `chore/launch-operations-hardening`

## Goal

Make the product recoverable and the critical acquisition journey continuously testable.

## Required work

1. Confirm protected-branch state.
2. Add or document required CI checks.
3. Confirm deployment and migration order.
4. Implement or document scheduled backups.
5. perform and record a restore test using a safe environment.
6. Document RTO and RPO for owner approval.
7. Add monitoring for:
   - stale datasets;
   - failed jobs;
   - queue health;
   - billing webhooks;
   - email;
   - disk and database capacity.
8. Complete critical Playwright flows.
9. Add post-deploy smoke verification.
10. Update incident and rollback runbooks.

## Restrictions

- Never test restore against production destructively.
- Never prune database volumes.
- Do not claim branch protection is active without checking the repository settings.
- External owner actions must be recorded as blocked, not silently skipped.

## Definition of done

- A failed deploy, migration, job, or data refresh is detectable.
- A tested recovery path exists.
- The complete primary workflow is covered in a production-like browser test.

---

# Slice LR-11 — Paid-beta instrumentation

**Branch:** `feat/paid-beta-ops`

## Goal

Support 10–15 paid design partners and record real evidence against launch gates.

## Required work

1. Add a beta cohort flag or safe account classification if needed.
2. Add internal notes or CRM linkage without duplicating sensitive data unnecessarily.
3. Add interview and deal-evaluation templates under `docs/launch-readiness/`.
4. Add a launch-gate evidence document.
5. Add admin summaries for:
   - active paid-beta users;
   - activation;
   - weekly usage;
   - correction reports;
   - support issues;
   - subscription state.
6. Ensure manual evidence entry is clearly distinguished from automatically measured data.

## Restrictions

- Do not fabricate participants or outcomes.
- Do not turn private customer interviews into public repository data.
- Keep sensitive feedback outside Git; commit only templates and aggregate safe results.

## Definition of done

- The owner can run the paid beta and make a launch decision from recorded evidence.

---

# Slice LR-12 — Public-launch gate review

**Branch:** `docs/public-launch-gate-review`

## Goal

Decide whether to launch, extend beta, or pause.

## Required evidence

For every gate in Amendment 03:

- status;
- source of evidence;
- measurement date;
- owner;
- open risk;
- exception;
- acceptance decision.

## Allowed decisions

- **Launch:** every P0 is closed and P1 exceptions are explicitly accepted.
- **Extend paid beta:** product is safe but evidence or retention is insufficient.
- **Pause:** trust, commercial, legal, or operational risk remains unacceptable.

## Restrictions

- Documentation only unless a newly discovered P0 defect requires a separate branch.
- Do not mark owner/external actions complete without evidence.
- Do not redefine metrics after seeing weak results without documenting the change.

---

## 5. Slice completion report template

At the end of every slice, report:

### Delivered

- PRD requirements completed;
- user-visible behavior;
- backend behavior;
- data/migration changes;
- docs and ADRs.

### Verification

- commands run;
- test counts;
- manual checks;
- browser checks;
- production-like checks.

### Risk

- remaining limitations;
- privacy/security;
- data quality;
- compatibility;
- performance.

### Deployment

- migration;
- backup;
- rollback;
- configuration;
- post-deploy smoke steps.

### Remaining

- blocked owner actions;
- next approved slice;
- items intentionally deferred.

Then stop.
