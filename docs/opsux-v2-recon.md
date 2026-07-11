# Slice 0 — Ops Center + UX v2: recon & plan

Recon for the two-part batch (Market Operations Center + User Experience v2). Findings from a four-way
subsystem audit, the plan table, and the decisions that need sign-off **before any build**. Invariants:
`VERDICT_VERSION` stays **v8**; three-market goldens byte-unchanged; honest states everywhere; tier gating
through existing machinery.

## Load-bearing findings

### Pipeline / deals (Part B, Slice 3)
- `pipeline.Deal` (`pipeline/models.py:8-19`): `id, user_id, parcel_number(FK), stage(str default "lead"),
  note, target_price(Numeric)` + `created_at/updated_at`. Unique `(user_id, parcel_number)`. Stages:
  `lead→diligence→offer→under_contract→closed→lost` (`pipeline/schemas.py:6-8`, validated in Pydantic only).
- **No stage timestamps, no activity/history table today** — v2 adds `stage_entered_at` + `deal_activity`
  going forward, no backfill.
- MAO is a **stored** column: `parcel_verdict.max_allowable_offer` (`verdict/models.py:39`); the pipeline
  already LEFT JOINs `parcel_verdict` (`pipeline/service.py:12-22`, currently pulls only opportunity) — the
  economics chip just adds columns to that join, computes nothing.
- Stage moves = `update_deal` via `PATCH /pipeline/{parcel}` — the single place to write auto activity +
  `stage_entered_at`. Board: `PipelinePage.vue` + `stores/pipeline.ts`; economics reference UI already
  exists (`DealPanel.vue`). Cap: `PIPELINE_LIMITS` free=10 (`accounts/tiers.py:34`). Digest: **no** pipeline
  hook yet.

### Admin / ops (Part A, Slices 1-2)
- Admin is one page/route (`/admin`, `AdminPage.vue`, `requiresAdmin`). Ops Center = a **sibling** admin
  route, same guard.
- `job_run` (`admin/models.py`) is already a **generic, per-market (`market_code`), user-attributed
  (`triggered_by`), timestamped, success/failure/error/row-count history table** — reuse it directly for the
  fleet job feed, and copy its shape for gate-audit history.
- `dataset_freshness` (`ingestion/models.py:22-33`) has composite PK `(market_code, dataset)` — the right
  grain for cadence. It records `status/last_attempt_at/last_success_at/row_count/detail`. **No
  `expected_cadence` anywhere** — net-new.
- `Market.source_config` is a **flat, source-level JSONB** (endpoint URLs / resource IDs), *not* per-dataset
  → cadence does **not** belong there.
- `capabilities.py` is pure-Python dicts (checklist states, hidden_surfaces, coverage notes, forced-sale
  labels) → trivially rendered as a read-only matrix.
- Gate docs: `docs/hbg-graduation-gate.md` (8 items; states blocked/partial/met; owner inline) and
  `docs/wave1-pgh-parity-gate.md` (6 criteria; threshold/actual/verdict). Two vocabularies → the gate table
  needs a status enum spanning both + ordinal/title/evidence/owner.
- `Market`: `launch_status`, `coverage_note`, `assessment_ratio` present for the fleet rollup.
- `market_stats`, `market_gate_item` are net-new.

### Digest / notifications (Slices 2, 3)
- Digest = gather → content dataclass → f-string `render_*_html/text` → `EmailSender.send` (`notifications/
  service.py` + `digest.py`). A **new section** = add a field to `DigestContent` + a block in the renderers
  (purely additive). A **new ops digest** = a `send_ops_digest(ctx)` coroutine + two registrations in
  `worker.py` (functions list + cron), querying `role=="admin"` users. `EmailAttachment` already supports
  binary attachments.
- "What changed" diff already exists: `watchlist/changes.py::compute_changes` (severity-tagged changes incl.
  opportunity/distress deltas) — reuse read-only for the Today view's "changes on pipeline parcels."

### Verdict explainability (Slice 4)
- Opportunity formula **confirmed**: `0.6·buildability + 0.4·(100−risk)`, clamped (`composition.py:42`,
  weights `:12-13`). Both inputs stored → **fully reconstructable, no recompute**.
- `risk_flags` JSONB stores `{code, severity, label, detail, source}` per flag; `_WEIGHT` (high40/med20/
  low10/info0, `risk/scoring.py:8`) is a **deterministic constant** → the drawer can show each flag's point
  contribution from stored severity + the constant map (not a recompute).
- Distress is **not** on the verdict; it's a separate `DistressResult/DistressFactor` — the drawer fetches
  it read-only (already has a factor breakdown).
- **GAP (flag, don't smuggle a scorer change):** granular **buildability reasons** are NOT persisted — only
  the score + booleans (`can_build_by_right/needs_variance/by_right_units/max_height/buildable_area`) +
  citation `sources`. So the buildability breakdown renders stored facts + citations; persisting the
  reason strings is a **bump-queue** item, out of this batch (invariant 1).
- Frontend hooks: `VerdictHero.vue` (gauge + pillars) and `VerdictPanel.vue` (already renders flags +
  `SEVERITY_HINT`/`SOURCE_LABELS`).

### Tiers / export (Slice 5) — smaller than it reads
- **CSV export infra already exists**: `exports.py` (`_reserve_export`, `_csv_response`), `reports/
  csv_export.py::stream_csv` + `EXPORT_DISCLAIMER`, `EXPORT_MONTHLY_LIMITS` (free=0/pro=10) + `EXPORT_ROW_
  LIMITS` (free=0/pro=2000), and **live `/leads/export` + `/saved-searches/{id}/export`** endpoints. Free is
  blocked by `export_monthly_limit==0`.
- Slice 5 therefore = **add a List export** + **enrich the column contract** (verdict headline, flags,
  distress tier, value range+confidence, MAO, `data_as_of`, truthful-state passthrough) + **frontend export
  buttons with the upgrade affordance**. Market-scoping already implicit in the queries.

### Onboarding (Slice 6)
- Fresh user lands on `/:market/home` (guaranteed by `marketGuard`); **no onboarding exists**. Hook a
  first-run flow in `App.vue` `onMounted` / `AppShell.vue` gated on a new user flag.
- SavedSearch seed is easy: clone `emptyCriteria()` + set goal fields + `savedSearches.create({name,
  criteria})`. **UX note:** free tier = **1** saved search, so seeding one spends the whole free allowance —
  state that in the goal step.
- **User model has no JSON/settings column → funnel timestamps need a migration** (add nullable
  `first_run_started/completed/skipped`, `first_verdict_viewed` DateTimes). Expose via `UserRead`/`getMe`.
- Market pick = `router.push({name:'home', params:{market: slug}})` (guard sets store); pilot badges via
  `statusOf==='pilot'`. Search entry: `GlobalSearch`/`SearchBox` needs a `defineExpose(focus)` to focus
  programmatically; `areaSearch.toggle()/setCenter()` — but **`MarketInfo` has no center coordinate today**
  (area-search-on-center needs a center; use `map_center` which exists on the `Market` model but isn't in
  `MarketInfo` → expose it, small addition).
- Admin activation metric = extend `_COUNTS_SQL` + `AdminOverview` (mirrors `saved_searches_total`).

### Mobile (code-level audit — report only; visual pass deferred to a future batch)
Foundations exist: viewport meta present, `$q.screen.lt.md/sm` used in AppShell/AppTopBar/ParcelDossier/
ExplorePage, `MobileTabBar` + collapsing `q-drawer` in `AppShell.vue`, dossier goes full-width on mobile.
**Preliminary top breakages (need on-device confirmation):**
1. **Pipeline Kanban** — 6 horizontal columns + **HTML5 drag-drop (doesn't fire on touch)** → the board is
   effectively unusable on phone; the new Today view mitigates this.
2. Fixed-width dialogs/pages overflow <375px: `AccountPage` (520/960px), `AdminPage` param dialog
   (min-340px), `OutreachMailerDialog` (min-380px), `AuthPage` (400px).
3. Wide data tables (Leads/Lists/Admin) → horizontal overflow.
4. Map controls overlay touch-target sizing; Explore map+panel split at phone width.
5. Topbar crowding (GlobalSearch 420px + MarketSwitcher + icons) at narrow width.
*Caveat: no screenshots — headless environment. The future batch's deliverable is a real-device pass; this
is the code-signal starting list.*

## Plan table

| Slice | Branch | Key files | Migration? | Tests | Risk |
|---|---|---|---|---|---|
| 0 recon | `feat/opsux-recon` | this doc | no | — | — |
| 1 health dashboard | `feat/ops-health-dashboard` | new `ops/cadence.py` (code-config map + pure eval fn), `ops/stats.py` (nightly `market_stats` snapshot job + worker cron), `api/ops.py`, new `pages/OpsPage.vue` + `MarketHealthPage.vue`; reads `dataset_freshness`, `job_run`, `capabilities`, `zoning_standard`, `Market` | **yes — `market_stats`** (snapshot table). Cadence is a **code-config map** (like `capabilities.py`), not a column | cadence eval truth-table (exhaustive, incl. seasonal/manual), stats snapshot job, per-market endpoint/render, goldens | med — pure eval fn + a read-heavy page; snapshot job must be idempotent |
| 2 alerts + gates | `feat/ops-alerts-gates` | `notifications/{service,digest}.py` (ops digest), `worker.py` (cron + failure alert hook in `run_admin_job`), new `market_gate_item` model + `admin` gate CRUD + audit (reuse job_run-style), seed from gate docs, ops page gate card | **yes — `market_gate_item`** | digest suppress-when-green, failure alert, gate CRUD+audit, readiness render, goldens | med — "quiet when green" logic must be exact; alerting must not spam |
| 3 pipeline v2 | `feat/pipeline-v2` ⚠ centerpiece | `pipeline/{models,schemas,service}.py`, `api/pipeline.py`, `deal_activity` model, `PipelinePage.vue` + new Today tab + detail drawer, `stores/pipeline.ts`, digest section | **yes — deal cols (`next_action,next_action_due,contact_*,stage_entered_at`) + `deal_activity` table** | schema round-trip, auto-activity on stage change, Today queries (due/overdue/stalled), economics-chip math vs fixture verdict, digest section, tier unchanged, **3-market goldens** | med-high — schema + the batch's UX centerpiece; fresh-context session |
| 4 explainability | `feat/score-explainability` | `VerdictHero.vue`/`VerdictPanel.vue` drawer, small distress fetch, `reports/dossier.py` one-line score note | no | per-pillar render ×3 markets, missing-field state, coverage-qualifier passthrough, snapshot prompt untouched | low — UI reading stored data; **buildability-reasons gap noted → bump queue** |
| 5 CSV export | `feat/csv-export` | extend `exports.py` (+List export), `reports/csv_export.py` column contract, `api/lists`/frontend export buttons | no (infra exists) | column-contract golden, gating per tier, cap enforcement, truthful-state passthrough, market-scoping (no cross-market leak) | low — reuses built export pipeline |
| 6 first-run | `feat/first-run` | new `FirstRun*.vue` (App.vue/AppShell hook), `accounts/{models,schemas,service}.py` + `getMe`, seed-search per goal, expose `map_center` on `MarketInfo`, `SearchBox` `defineExpose(focus)`, admin overview counts | **yes — user funnel cols** (`first_run_started/completed/skipped`, `first_verdict_viewed`) | flow state machine, seeded-search per goal, skip/resume, tier-limit interaction, no effect on existing accounts | low-med — a migration the prompt didn't flag |

## Decisions needing sign-off (deviations from the prompt)

1. **Cadence as code-config, not a DB column.** The prompt says "source config gains `expected_cadence`,"
   but `source_config` is source-level and there's no per-dataset config table. Cleanest + no migration:
   a `ops/cadence.py` `(market,dataset)→cadence` map + derived `stale_after`, mirroring `capabilities.py`
   (reviewable, testable). **Alternative:** add `expected_cadence`/`stale_after` columns to
   `dataset_freshness` (migration, config-on-runtime-row). **Recommend code-config.**
2. **Slice 6 needs a migration** (user funnel columns) — the prompt's ceremony listed migrations for 1/2/3
   only. So the batch has **4 migration slices** (1 market_stats, 2 gate items, 3 deal cols+activity, 6 user
   funnel), each getting the backup ritual.
3. **Buildability granular reasons are not persisted** → Slice 4's buildability breakdown shows stored facts
   + citations only; persisting reasons is a **bump-queue** item, out of scope (invariant 1). Confirm that's
   acceptable (vs. deferring the buildability sub-panel).
4. **Slice 5 is mostly done** — export infra + Pro gating + row caps already exist; the slice adds List
   export + column enrichment + frontend buttons. Smaller than written; no objection expected, just noting.
5. **Onboarding area-search-on-center** needs a market center coordinate exposed on `MarketInfo`
   (`Market.map_center` exists; add to the schema) — a tiny addition folded into Slice 6.

## Suggested order (matches the prompt)
1 → 2 (ops first; Slice 6 reports into Slice 1's page) → **3** (centerpiece, fresh session) → 4/5/6 any order.
Out of scope confirmed: skip-trace/enrichment, cross-market surfaces, mobile fixes, dossier IA, any verdict/
scoring change, Baltimore.
