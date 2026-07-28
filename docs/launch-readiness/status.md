# Launch-readiness status — LR-0 baseline

**Assessment date:** 2026-07-28
**Repository SHA at assessment:** `e68f16baa14a2b892ff9d9f62c7b74228dfb137f`
**Branch:** `docs/launch-readiness-baseline`
**Verdict version:** `v8` (`backend/src/lotscope/verdict/composition.py:9`)
**Alembic head:** `e7d9c1a4b820` — single head, database in sync
**Governing requirement source:** `docs/PRD-amendment-03-launch-readiness.md`

This document records what the repository actually contains as of the SHA above, measured against Amendment 03. It supersedes `docs/handoff/0029-2026-07-28.md` as the description of current launch state; the handoff remains the historical record of how the code got here.

---

## 0. Governing-document conflict and the resolution in force

**Amendment 03 §21 and `docs/claude-code-execution-launch-readiness.md` use incompatible LR-numbering.** The same identifiers name different work:

| Identifier | Amendment 03 §21 | Execution document |
|---|---|---|
| LR-1 | Truth and trust foundation | Launch market and feature visibility |
| LR-2 | Decision-first Parcel Verdict | Trust contract and correction workflow |
| LR-3 | Professional underwriting | Philadelphia gold-set framework |
| LR-4 | Focused acquisition experience | Decision-first Parcel Verdict |
| LR-5 | Commercial and observability hardening | Buildability checklist and wording |
| LR-6 | Operational hardening | Professional underwriting |

**Resolution in force for this program, pending owner correction:**

- The **execution document** is authoritative for **slice identity, numbering, and branch names**.
- **Amendment 03** is authoritative for **requirements, acceptance criteria, and priority rules**.

Every slice reference in `backlog.md` uses execution-document numbering. If the owner prefers Amendment 03 numbering, the slice column in `backlog.md` is the only thing that changes; requirement IDs (`LR-V001`, `LR-U003`, …) are stable across both.

Neither document was edited to resolve this.

---

## 1. Flagship and pilot markets

| Market | Launch status | Parcels | Vacant | Geometry | Zoning (effective) |
|---|---|---:|---:|---:|---:|
| **Philadelphia (`phl`)** | **live — flagship** | 550,939 | 36,768 | 98.7% | 99.2% |
| Harrisburg (`hbg`) | pilot | 19,502 | 1,664 | 100.0% | 100.0% |
| Pittsburgh (`pgh`) | pilot | 143,355 | 22,438 | 99.9% | 89.8% |
| Wilmington (`wlm`) | pilot | 26,197 | 2,403 | 99.0% | 99.6% |

Zoning percentage is `coalesce(nullif(base_zoning_code,''), resolved_zoning_code)` — `hbg` and `pgh` resolve districts spatially (ADR-0056/0058) and carry no `base_zoning_code`, so a naive count of that column alone understates them.

Measured against the local development database at the assessment SHA. Production parcel counts were not queried (admin endpoints require authentication); production was confirmed to serve all four markets and non-empty Wilmington tiles.

Per Amendment 03 §0, pilots may remain available but must not drive launch scope. No market expansion is in this backlog.

---

## 2. Product surfaces present

**Frontend routes** (`frontend/src/router/index.ts`): landing, login, register, account, admin, admin/ops, admin/ops/:market, and market-scoped `home`, `explore`, `leads`, `feed`, `sheriff-sales`, `buyers`, `buyers/:buyerKey`, `top-plays`, `market`, `pipeline`, `lists`, plus redirects from `watchlist`, `compare`, `saved-searches`, and the deep-linkable `/parcel/:market/:id`.

**Primary navigation** (`frontend/src/components/AppSidebar.vue:30-43`): 10 destinations — Home, Explore, Feed, Sheriff sales, Top plays, Cash buyers, Market, Leads, Pipeline, Lists. Amendment 03 §12.1 targets 5.

**Parcel dossier** (`frontend/src/components/ParcelDossier.vue`): 5 tabs — Verdict, Deal, Land, Risk, Docs.

**Backend domain modules** (`backend/src/lotscope/`): accounts, admin, ai, appeal, assemblage, assessment, buyers, checklist, compare, core, deal, distress, documents, feed, historic, ingestion, market, markets, neighborhoods, notifications, ops, outreach, owners, parcels, pipeline, risk, search, sheriff, skiptrace, streets, subdivision, tiles, vacancy, valuation, verdict, watchlist, zba, zoning.

---

## 3. Implementation summary

### Parcel Verdict
`verdict/` composes buildability, valuation, risk, and deal into a versioned result. The contract (`verdict/schemas.py:10-33`) carries `opportunity_score`, `buildability_score`, `risk_score`, `deal_score`, `summary`, buildability outputs, valuation range with `value_confidence`, `arv`/`est_profit`/`est_margin`/`max_allowable_offer`, `risk_flags[]`, `sources[]`, and `computed_at`. Provenance exists at **verdict level**, not field level. There is no screening-recommendation label.

### Buildability
Zoning standards seeded per market (phl 48, hbg 9, pgh 24, wlm 24) via `zoning/seed*.py`, all four markets covered by one `seed_all_zoning_standards` since #40. District resolution is deterministic (ADR-0056) and materialized (ADR-0058), except Wilmington, which reads the parcel `ZONECODE` attribute and holds **no** `zoning_district` polygons. Overlays/RCO (ADR-0040), historic (ADR-0028), street access (ADR-0027), ZBA outlook (ADR-0050).

### Valuation and underwriting
`valuation/` produces comp-based estimates with confidence and exclusion rules (ADR-0032 related-party, ADR-0049 package deeds, `future_sale_exclusion_sql` since #38). `deal/analysis.py` computes MAO, profit, margin, ROI, `confidence`, and `reasons[]` from **6 assumptions** (`analysis.py:15-20`). `deal/scenarios.py` varies **unit count**, not case. Endpoints accept **5 override query params**; the dossier exposes **2** editable inputs (`DealPanel.vue:155-164`). No persistence of user assumptions.

### Risk and distress
`risk/` flags with market-scoped wording (#33), `distress/` with per-market versioned profiles (ADR-0057) and a tripwire that blocks precompute for unregistered markets. Distress surfaced as a header chip and Verdict-tab panel since #44.

### Discovery
Explore (map + list + area search), Leads, Feed (ADR-0037), Sheriff sales (ADR-0038), Top plays (ADR-0041), Cash buyers (ADR-0061), Market intelligence. Six of these are discovery variants competing for one user intent.

### Pipeline
`pipeline/` with Kanban stages (ADR-0020), deal activities, `offer_price_override`, LOI generation (ADR-0062), appeal packets (ADR-0042).

### Saved searches and alerts
`saved_search` with match generation (ADR-0024), watchlist change alerts (ADR-0017), email digests (ADR-0018), web push (ADR-0019), parcel events.

### Accounts and billing
`accounts/tiers.py` centralizes entitlements: per-tier limits (`parcel_view_daily_limit`, `watchlist_limit`, `pipeline_limit`, `saved_search_limit`, `export_monthly_limit`, `lead_list_limit`, `ask_daily_limit`) and access predicates (`feed_access`, `buyer_intel_access`, `offer_generation_access`, `sheriff_calendar_access`, `top_plays_access`, `report_access`, `market_stats_access`). Tiers: free, pro, investor, enterprise. `api/billing.py` exposes `/plans`, `/checkout`, `/appeal-packet/checkout`, `/portal`, `/webhook`; the webhook handles `checkout.session.completed` and the three `customer.subscription.*` events. 13 Stripe variables in `.env.example`. **Not verified against Stripe in production-like conditions.**

### Analytics and monitoring
**No product analytics and no error monitoring exist.** An exhaustive search across `*.py`, `*.ts`, `*.vue`, `*.json`, `*.toml`, `*.yml` for PostHog, Mixpanel, Amplitude, Google Analytics, Plausible, Sentry, OpenTelemetry, Datadog, Rollbar, Bugsnag, Segment, New Relic, and Honeycomb returned a single false positive (`subdivision/service.py:27`, a function named `_plausible_width`). Neither `backend/pyproject.toml` nor `frontend/package.json` contains such a dependency.

What does exist: `structlog` JSON logging (`core/logging.py:12`) with **no correlation identifier** (zero matches for `correlation_id|request_id|x-request-id|trace_id` in backend source), and `ops/alerts.py` providing dataset-failure detection, ops digests, and admin email alerts — real, but inert until SMTP is configured.

### Operations and deployment
CI (`.github/workflows/ci.yml`) runs backend ruff check, ruff format check, mypy, unit tests, and a containerised integration job; the frontend job runs lint, **format check** (added #45), typecheck, and tests. Deployment is `workflow_dispatch`-only via `scripts/deploy.sh` with a SHA-drift guard and `/health` verification. Admin job console (ADR-0059), `dataset_freshness`, `market_gate_item` gate board.

**Absent:** any end-to-end test framework (no Playwright reference anywhere; `make e2e` exits with "not implemented yet"), and any documented backup, retention, or restore procedure (`docs/runbook.md` contains no match for backup, restore, or `pg_dump`; the only `sync-db.sh` is gitignored and local-only).

### Legal, privacy, support
No Terms of Service, Privacy Policy, refund policy, or correction policy exists in `docs/`, `frontend/src`, or `backend/src`. No `/terms` or `/privacy` route. Disclaimer fragments exist in components ("Informational only" ×7, "not legal advice" ×1, "not financial advice" ×1). **No "Report incorrect data" capability** — zero matches repository-wide.

---

## 4. Requirement completion counts

Counted over the 40 requirement rows assessed in `backlog.md` and the LR-0 reconnaissance.

| Status | Count |
|---:|---|
| Complete | 0 |
| Partial | 18 |
| Absent | 15 |
| Needs verification | 2 |
| Blocked by owner action | 3 |
| Blocked by external dependency | 1 |
| Deferred by PRD | 1 (§5.2 group) |

No requirement is marked **Complete**. Several are close — centralized entitlements, the checklist module, verdict-level provenance — but each falls short of an Amendment 03 acceptance criterion, and Amendment 03 §0 forbids treating existing functionality as satisfying a launch requirement without evidence.

---

## 5. Known documentation drift

| Document | Drift | Disposition |
|---|---|---|
| Amendment 03 §21 vs execution document | Incompatible LR-numbering | Recorded in §0 above; **neither document edited** |
| `docs/PRD.md` §5.1/§5.15/§14 | Names Elasticsearch | Superseded by ADR-0005; already annotated in the PRD's own provenance line |
| `docs/PRD.md` §9 | Pricing $49–99 / $199–399 | Amendment 03 §14.1 proposes higher ranges; **neither is implemented and neither is owner-approved** |
| `docs/PRD.md` | Philadelphia-only framing | Superseded by Amendment 02, re-narrowed by Amendment 03; chain is coherent |
| `docs/design/ia-and-layout.md` | "Status: Proposed" (2026-07-01); describes the 10-item shell | Partially implemented; §12.1 supersedes parts — **requires an ADR decision in LR-7, not a silent edit** |
| ADR-0029 | Defines the current app shell and navigation | Conflicts with Amendment 03 §12.1; **requires a superseding or amending ADR before navigation changes** |
| `docs/runbook.md` | No backup/restore section | To be added in LR-10 |
| `docs/handoff/0029-2026-07-28.md` | Accurate to `3672afe`; predates #44–#46 | Superseded by this document; retained as history |

No historical document was edited or deleted.

---

## 6. Owner and external blockers

1. Approve Amendment 03 (status is still "Proposed for owner approval").
2. Confirm or overturn the LR-numbering resolution in §0.
3. **GitHub Pro or a public repository** — branch protection is plan-blocked, not settings-blocked. Verified: `PUT /repos/turabekh/lotscope/branches/main/protection` and `GET /repos/turabekh/lotscope/rulesets` both return 403 *"Upgrade to GitHub Pro or make this repository public"* with an `admin: true` token.
4. Pricing approval; no Stripe products created.
5. Stripe production credentials and live billing verification.
6. SMTP/email credentials — alerts and digests are inert without them.
7. Analytics and error-monitoring vendor approval (new dependency + privacy review).
8. Owner-approved legal copy — Terms, Privacy, refund, correction, disclaimers.
9. Professional reviewer for the Philadelphia gold set.
10. Paid-beta cohort recruitment.
11. Playwright dependency approval (CLAUDE.md forbids adding dependencies without discussion).

---

## 7. Next recommended slice

**LR-2 — Trust contract and correction workflow.**

Promoted ahead of LR-1 because the field-state taxonomy (§8.1/8.2) is a contract that LR-4 (decision-first verdict), LR-5 (buildability checklist), and LR-6 (underwriting) all consume. Building any of those before the taxonomy means building them twice. LR-1 (market and feature visibility) is comparatively cosmetic and has no dependents, so it can land at any point before the beta.

The LR-B002 by-right wording fix is P0 and small; it is scheduled inside LR-2 rather than waiting for LR-5.

See `backlog.md` for the ordered tickets and `gates.md` for the launch gates.
