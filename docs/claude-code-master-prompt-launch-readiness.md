# Master Prompt for Claude Code — Execute LotScope Launch Readiness

Copy this prompt into Claude Code at the beginning of a launch-readiness session.

---

You are working in the LotScope repository.

Your objective is to execute the commercial launch-readiness program defined by:

- `docs/PRD-amendment-03-launch-readiness.md`
- `docs/claude-code-execution-launch-readiness.md`

## Required reading

Read, in this order:

1. `CLAUDE.md`
2. `docs/PRD.md`
3. `docs/PRD-amendment-01-monetization.md`
4. `docs/PRD-amendment-02-geographic-expansion.md`
5. `docs/PRD-amendment-03-launch-readiness.md`
6. `docs/claude-code-execution-launch-readiness.md`
7. `docs/design/ia-and-layout.md`
8. all ADRs relevant to the selected slice
9. `docs/runbook.md`
10. the latest relevant handoff documents
11. the actual implementation and tests

Do not rely on prompt or handoff documents as proof that work is incomplete or complete. Reconcile everything against current `main`, migrations, routes, services, frontend code, configuration, and tests.

## Product direction

Until the launch gates pass:

- Philadelphia is the flagship commercial market.
- The primary customer is a small Philadelphia infill developer, land investor, or acquisition operator.
- The primary journey is:
  `Define buy box → Find lots → Open verdict → Inspect likely program → Inspect risks → Adjust underwriting → Save to pipeline → Take next action`.
- Launch readiness, truth, usability, billing, observability, and real customer validation take priority over new markets and new broad features.
- Do not add another market.
- Do not expand unrelated features.
- Do not delete stable secondary capabilities; de-emphasize them when required.
- Do not introduce an unvalidated composite score.
- Do not present missing data as no risk or zero.
- Do not present a base-district dimensional check as final permission to build.

## Engineering rules

Follow every rule in `CLAUDE.md`, including:

- no human-facing code comments or docstrings;
- full typing;
- thin API routers;
- domain module boundaries;
- deterministic pure core logic;
- provenance and computed timestamps;
- safe parameterized SQL;
- idempotent ingestion;
- no secrets or raw production data;
- tests for domain logic;
- smallest vertical slice;
- ADRs for lasting decisions.

Do not add dependencies or vendors without explicit approval.

Do not invent legal approval, professional parcel review, Stripe configuration, production credentials, customer interviews, or paid-beta evidence.

## Git and deployment

- Inspect current branch, SHA, clean status, and Alembic head.
- Work from an up-to-date `main`.
- Create one feature branch for one slice.
- Never commit directly to `main`.
- Never force-push.
- Use conventional commits.
- Do not merge or deploy without explicit owner approval.
- For migrations, inspect deployment order, provide the exact backup command, wait for backup confirmation, and document rollback.
- Treat a merge to an auto-deploying branch as a deployment.

## Session objective

Execute only this slice:

`[INSERT APPROVED SLICE, FOR EXAMPLE: LR-0]`

Do not start a later slice.

## First response required before editing

Produce a recon containing:

### 1. Current repository state

- branch and SHA;
- clean or dirty worktree;
- Alembic head;
- relevant existing implementation;
- relevant tests;
- relevant documents and ADRs;
- production or credential dependencies;
- current open handoff items.

### 2. Requirement matrix

Create a table:

| Requirement | Current implementation | Gap | Priority | Proposed change | ADR/migration |
|---|---|---|---|---|---|

### 3. Proposed slice plan

Include:

- exact scope;
- files and modules likely to change;
- tests to add or update;
- migration impact;
- verdict-contract or version impact;
- privacy/security impact;
- analytics impact;
- rollback plan;
- manual verification;
- owner decisions needed.

### 4. Risks and pushback

Identify:

- ambiguous requirements;
- over-engineering risk;
- duplicated existing work;
- data-quality risk;
- legal or PII risk;
- external blockers;
- anything that should be deferred.

For an architectural, contract-changing, migration-bearing, pricing, navigation, vendor, or legal-policy decision, stop after the plan and wait for explicit approval.

For a small, obvious, already-approved implementation within the selected slice, proceed only after presenting the plan.

## Implementation behavior

While implementing:

1. keep changes inside the selected slice;
2. write tests before or with core domain changes;
3. preserve compatibility where reasonable;
4. update docs and ADRs in the same branch;
5. never fake external evidence;
6. never mark a launch gate complete without evidence;
7. surface discoveries immediately;
8. do not silently fix unrelated issues;
9. record unrelated issues in the backlog;
10. use real repository commands, not assumed commands.

## Required gates

Run:

```bash
make lint
make typecheck
make test
```

When frontend code changes, also run:

```bash
cd frontend
pnpm lint
pnpm typecheck
pnpm test
```

When the critical customer journey changes, run:

```bash
make e2e
```

If a command does not exist or fails for an environmental reason, report the exact failure. Do not claim success.

## Completion response

At the end, provide:

### Delivered

- PRD IDs;
- files;
- user-visible changes;
- backend and data changes;
- ADRs and docs.

### Verification

- exact commands;
- pass/fail results;
- tests added;
- manual checks;
- browser checks.

### Risk

- remaining limitations;
- privacy/security;
- data quality;
- compatibility;
- performance.

### Deployment

- migration yes/no;
- backup command;
- rollback;
- config or credential changes;
- post-deploy smoke steps.

### Remaining

- owner actions;
- blocked items;
- intentionally deferred items;
- recommended next slice.

Stop after completing the selected slice. Do not merge, deploy, or begin the next slice unless explicitly instructed.
