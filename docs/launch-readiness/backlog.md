# Launch-readiness backlog — LR-0

**Baseline SHA:** `e68f16baa14a2b892ff9d9f62c7b74228dfb137f` · **Assessed:** 2026-07-28
**Requirement source:** `docs/PRD-amendment-03-launch-readiness.md`
**Slice numbering:** `docs/claude-code-execution-launch-readiness.md` (see `status.md` §0)

Ordered by dependency and risk. Slice headings follow the recommended sequence, which reorders the execution document in two places — both changes are explained in `status.md` §7 and repeated on the affected tickets.

**Priorities:** P0 blocks a controlled paid beta or risks material customer harm · P1 required before broad public launch · P2 after launch evidence · P3 deferred.

**Status values:** `Not started` · `Blocked by owner action` · `Blocked by external dependency` · `Deferred by PRD`.

---

# Slice LR-2 — Trust contract and correction workflow

*Promoted ahead of LR-1: every later slice consumes this contract.*

## LR-B-001 — Field-state taxonomy and material-field metadata

- **PRD requirement:** §8.1, §8.2
- **Priority:** P0 · **Status:** **Done — confirmed 2026-08-01** against acceptance criteria (ADR-0065). Scope is the phase this ticket names: the verdict contract's buildability, valuation, and deal fields.
- **Problem:** Trust state exists only at market-category granularity (`no_data_source`, `pending_load`, `available`) and provenance only at verdict level (`sources[]`, `computed_at`). No material field declares whether it is Verified, Calculated, Estimated, or Unavailable.
- **User impact:** An infill developer cannot tell whether "buildable" is a verified district rule, a calculated geometry inference, or an estimate. Amendment 03 §6.2 forbids exactly this ambiguity, and it is the difference between a defensible screen and a guess.
- **Current implementation:** `backend/src/lotscope/markets/capabilities.py:3-14` (category states); `backend/src/lotscope/verdict/schemas.py:32-33` (`sources`, `computed_at`); `frontend/src/components/WhyScoreDrawer.vue:31-33` (renders verdict sources).
- **Proposed solution:** Introduce a shared field-state enum and a metadata envelope for material outputs. Extend the existing capabilities system rather than replacing it — capability state becomes one input to field state. Apply first to the verdict contract's buildability, valuation, and deal fields.
- **Dependencies:** none — foundational.
- **Likely files/modules:** `core/` (shared enum), `verdict/schemas.py`, `verdict/composition.py`, `markets/capabilities.py`, `frontend/src/lib/types.ts`, dossier panels.
- **ADR:** **Required** — changes the verdict contract (CLAUDE.md §10; ADR-0003/0007 govern it).
- **Migration:** Likely, if states are persisted on `parcel_verdict` rather than computed at read time. Decide in the ADR.
- **Security/privacy:** None directly; `source_refs` must not leak internal connection strings or credentials.
- **Tests:** Unit tests per field-state derivation; a test asserting no material field can report Verified without a source reference; verdict golden-file review across phl/hbg/pgh/wlm.
- **Acceptance criteria:** Every material verdict field exposes a state from the four-value enum; frontend wording and API enum are identical; a field with no evidence reports Unavailable, never a default; contract change is ADR-recorded and verdict-version reviewed.
- **Owner action:** Approve the ADR and any verdict-version bump.

## LR-B-002 — By-right wording and preliminary-screening framing

- **PRD requirement:** LR-B002, §6.3, §24
- **Priority:** P0 · **Status:** **Done 2026-08-01** — the hero and panel already carried the qualifier; the drawer and map popup are now reworded and the qualifier is bound to the checklist's `not_evaluated` categories via `lib/by-right.ts`
- **Problem:** `can_build_by_right` is a boolean rendered as a definitive statement. Amendment 03 §24 explicitly names "treat a base-district check as final approval" an anti-pattern.
- **User impact:** A developer reading "buildable by right" as permission may pursue or bid on a parcel that fails on overlays, access, utilities, or title — none of which the base-district check evaluates.
- **Current implementation:** `backend/src/lotscope/verdict/schemas.py:15`; wording throughout `frontend/src/components/VerdictHero.vue`, `VerdictPanel.vue`.
- **Proposed solution:** Reword to the §LR-B002 preferred form — dimensional eligibility under listed base-district standards, subject to the checks below — and bind the wording to the list of checks not evaluated. No scoring change.
- **Dependencies:** LR-B-001 (uses the Not-evaluated state to enumerate what is outstanding).
- **Likely files/modules:** `frontend/src/components/VerdictHero.vue`, `VerdictPanel.vue`; verdict `summary` composition.
- **ADR:** Not required — presentation, not contract.
- **Migration:** No.
- **Security/privacy:** None.
- **Tests:** Frontend assertions that unconditional approval wording is absent; a test that the qualifier renders whenever any check is Not evaluated.
- **Acceptance criteria:** No surface presents a base-district pass as unconditional approval; the qualifier is always accompanied by the outstanding checks.
- **Owner action:** None. *Pulled forward from LR-5 because it is P0 and small.*

## LR-B-003 — Missing-data audit against §8.4

- **PRD requirement:** §8.4
- **Priority:** P0 · **Status:** Complete (2026-07-28) — results in `docs/launch-readiness/missing-data-audit.md`
- **Problem:** Missing-data handling appears strong (66 `None`-guards in `verdict/composition.py`; capabilities distinguish no-source from pending), but this has never been audited field-by-field against the §8.4 prohibition list. It is currently **Needs verification**, not Complete.
- **Outcome:** Six findings, all fixed. Three were false clearances reaching users (unknown tax balance stored as not-delinquent; a delinquent parcel rendering "$0 owed"; the checklist passing `liens_taxes` when the feed reported no balance). Two were conflations of unknown with a determined value, and one ran in the conservative direction and was never a §8.4 violation. `VERDICT_VERSION` unaffected.
- **User impact:** A single place where absent evidence renders as "no risk", "clear", or zero would be a material trust failure, and the most likely one to go unnoticed.
- **Current implementation:** `verdict/composition.py`, `markets/capabilities.py`, `risk/`, `checklist/logic.py`.
- **Proposed solution:** Enumerate every material output; assert for each that absent input produces Unavailable rather than a falsy default. Record results as a checked inventory. Fix any violations found.
- **Dependencies:** LR-B-001 (needs the Unavailable state to fix violations properly).
- **Likely files/modules:** `verdict/`, `risk/`, `valuation/`, `deal/`, `checklist/`.
- **ADR:** Only if a violation requires a contract change.
- **Migration:** No.
- **Security/privacy:** None.
- **Tests:** A parameterised test per material field feeding absent inputs and asserting the output is not `0`, `false`, "clear", or "no risk".
- **Acceptance criteria:** Documented inventory of every material field with its missing-input behaviour; zero prohibited translations remain.
- **Owner action:** None.

## LR-B-004 — Correction workflow ("Report incorrect data")

- **PRD requirement:** §8.5, §6.7
- **Priority:** P0 · **Status:** **Done 2026-08-01** — reporting shipped earlier (LR-9C); the operator triage UI (`CorrectionsQueue.vue`, mounted on the admin page) closes the last acceptance clause.
- **Problem:** No correction capability exists anywhere in the repository. *(Superseded: reporting and the admin endpoints were built; the endpoints simply had no frontend consumer, which the 2026-08-01 gate review found — see its §1.2.)*
- **User impact:** When LotScope is wrong about a real parcel, the customer has no route to say so and the product gets no signal. This is the difference between a beta that improves and one that silently loses trust — and Amendment 03 §22 lists "no correction route" as P0.
- **Current implementation:** None. Zero repository matches.
- **Proposed solution:** New `corrections/` domain module capturing user, parcel + market, field/section, verdict version, computed timestamp, source refs and freshness state, description, optional attachment reference, triage status, resolution and resolution timestamp. Dossier entry point on every parcel. Admin triage view reusing the existing admin console patterns.
- **Dependencies:** LR-B-001 (a correction must record the field state it disputes).
- **Likely files/modules:** new `backend/src/lotscope/corrections/`, `api/parcels.py` or a new router, `frontend/src/components/ParcelDossier.vue`, admin surface.
- **ADR:** **Required** — new domain module and data model.
- **Migration:** **Required** — new table(s).
- **Security/privacy:** Captures user-authored text and optional attachments; must follow CLAUDE.md §13 retention and access rules. Attachments must not be world-readable. Correction text must never be forwarded to analytics.
- **Tests:** Service tests for capture and triage transitions; API authorization tests; a test that verdict version and computed timestamp are captured at report time, not at resolution time.
- **Acceptance criteria:** Every dossier offers the action; a submitted correction preserves parcel, verdict version, source state, and evidence; triage status is visible to an operator; PII rules hold.
- **Owner action:** Decide attachment storage and retention policy.

## LR-B-005 — Source freshness at the point of use

- **PRD requirement:** §8.3, §6.5
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `GET /parcels/{n}/freshness` returns all eight §8.3 sources; `FreshnessPanel.vue` renders them
- **Problem:** `dataset_freshness` is exposed only through the admin API. The customer-facing `DataCoverageChip` shows a static per-market note, not data age.
- **User impact:** A developer underwriting against a six-month-old assessment or a stale L&I feed has no way to know. §6.5 requires source age near the result it qualifies.
- **Current implementation:** `backend/src/lotscope/api/admin.py:58` (admin only); `frontend/src/components/DataCoverageChip.vue:8-23` (static note + pilot flag).
- **Proposed solution:** Expose per-source age for the §8.3 list (geometry, assessment, zoning, recorded sales, L&I, tax status, forced sale, verdict computation) through a customer-facing read, rendered as a compact dossier panel.
- **Dependencies:** LR-B-001.
- **Likely files/modules:** `ingestion/service.py` (freshness reads), a parcels endpoint, new dossier panel.
- **ADR:** Not required.
- **Migration:** No — `dataset_freshness` already exists.
- **Security/privacy:** Must not expose upstream URLs or credentials.
- **Tests:** API test for freshness payload shape; frontend test that a stale dataset renders a distinct state.
- **Acceptance criteria:** All eight §8.3 sources show age in the dossier; staleness beyond policy renders as Unavailable rather than a fresh-looking value.
- **Owner action:** Define the staleness policy per dataset.

---

# Slice LR-1 — Launch market and feature visibility

*Demoted below LR-2: cosmetic, no dependents.*

## LR-B-006 — Philadelphia flagship framing and pilot demotion

- **PRD requirement:** §0.1–0.2, §5.1, §24
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `MarketSwitcher` shows a `flagship` badge for Philadelphia and `pilot` for the others
- **Problem:** All four markets present as peers in the switcher; nothing in the UI communicates that Philadelphia is the commercial product and the others are pilots, beyond a coverage chip.
- **User impact:** A paying Philadelphia customer who switches to a pilot market and finds thin data will discount the whole product.
- **Current implementation:** `frontend/src/components/MarketSwitcher.vue`, `DataCoverageChip.vue:9` (`isPilot`), `markets/capabilities.py`, `market.launch_status`.
- **Proposed solution:** Make flagship-vs-pilot visually unambiguous in the switcher and on pilot surfaces. Do not remove pilot markets.
- **Dependencies:** none.
- **Likely files/modules:** `MarketSwitcher.vue`, `DataCoverageChip.vue`, `markets/capabilities.py`.
- **ADR:** Not required.
- **Migration:** No — `launch_status` exists.
- **Security/privacy:** None.
- **Tests:** Frontend tests asserting pilot markets carry the pilot treatment and `phl` does not.
- **Acceptance criteria:** A user can tell at a glance which market is the commercial product; no pilot market is removed or broken.
- **Owner action:** Confirm pilot markets stay visible to non-invited users, or should be restricted.

---

# Slice LR-3 — Philadelphia gold-set framework

*Started early: professional review is calendar-bound, not code-bound.*

## LR-B-007 — Gold-set structure and review workflow

- **PRD requirement:** LR-Q001, LR-Q002
- **Priority:** P1 · **Status:** **Done 2026-08-01** — `make gold-set-select` selects **118 parcels covering all 17 LR-Q001 categories**, deterministically and from source tables rather than our own flags; record format supports LR-Q003 severity; workflow documented. Expected facts and professional review are LR-B-008
- **Problem:** No Philadelphia gold set exists. The 25-parcel packets that exist are Harrisburg and Pittsburgh (`docs/wave0-hbg-25parcel-packet.md`, `docs/wave1-pgh-25parcel-packet.md`), both still pending reviewer sign-off.
- **User impact:** Without it, no defensible claim that Philadelphia output is correct — and §16 makes this a public-launch gate.
- **Current implementation:** Prior-wave packet format only.
- **Proposed solution:** Define the 100-parcel selection covering all LR-Q001 categories, the record format (expected vs actual, reviewer, source, severity), and the review workflow. Build the structure and selection in this slice; completion is owner + reviewer work.
- **Dependencies:** LR-B-001 (records should capture field states as reviewed).
- **Likely files/modules:** `docs/launch-readiness/gold-set/`, a selection query or script.
- **ADR:** Not required.
- **Migration:** No.
- **Security/privacy:** Gold-set records may contain owner names — treat as PII under CLAUDE.md §13; do not commit owner contact data.
- **Tests:** A check that the selection covers every LR-Q001 category.
- **Acceptance criteria:** 100 parcels selected with category coverage; record format supports LR-Q003 severity classification; workflow documented.
- **Owner action:** Engage an architect, zoning consultant, or expediter as reviewer.

## LR-B-008 — Gold-set review execution and error classification

- **PRD requirement:** LR-Q003, LR-Q004
- **Priority:** P1 · **Status:** **Blocked by owner action**
- **Problem:** Requires professional review of real parcels; cannot be produced by code.
- **User impact:** Gates the "commercially verified" claim for Philadelphia.
- **Current implementation:** None.
- **Proposed solution:** Execute the workflow from LR-B-007; classify every finding Critical/Material/Minor; resolve all Critical categories.
- **Dependencies:** LR-B-007.
- **Likely files/modules:** `docs/launch-readiness/gold-set/`.
- **ADR:** No. **Migration:** No.
- **Security/privacy:** As LR-B-007.
- **Tests:** Not applicable — Amendment 03 §16 states automated tests do not replace this review.
- **Acceptance criteria:** Every parcel has a review status; no unresolved Critical category; owner accepts the residual material-error profile.
- **Owner action:** Fund and schedule the review; accept the residual profile.

---

# Slice LR-4 — Decision-first Parcel Verdict

## LR-B-009 — Screening recommendation

- **PRD requirement:** LR-V001
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `verdict/decision.py` + ADR-0067; all six labels present in production data
- **Problem:** The dossier leads with `opportunity_score` and a `summary`; there is no pursue/investigate/pass label.
- **User impact:** JTBD-2 asks for a useful screening result in ~30 seconds. Today the user synthesizes it from several panels.
- **Current implementation:** `verdict/schemas.py:13-14`; `frontend/src/components/VerdictHero.vue`.
- **Proposed solution:** Deterministic label from explicit inputs, with a one-sentence reason. Critical missing data forces `Insufficient data`. Versioned and reproducible.
- **Dependencies:** LR-B-001, LR-B-003.
- **Likely files/modules:** `verdict/composition.py`, `verdict/schemas.py`, `VerdictHero.vue`.
- **ADR:** **Required** — new decision contract; verdict-version review (Amendment 03 §LR-V001).
- **Migration:** Likely, if persisted on `parcel_verdict`.
- **Security/privacy:** None.
- **Tests:** Deterministic label tests per input combination; a test that missing critical data yields `Insufficient data`; golden-file review across markets.
- **Acceptance criteria:** All six labels reachable; reason visible in one sentence; reproducible for a given verdict version.
- **Owner action:** Approve the decision contract and label wording.

## LR-B-010 — Likely development program

- **PRD requirement:** LR-V002
- **Priority:** P1 · **Status:** **Not started (criteria reviewed 2026-08-01)** — the summary is a terse compound line (`RM-1: buildable by-right (4 unit); est. ...`) that meets none of LR-V002's four criteria: no verified-vs-calculated distinction, no conditional language, no standards citation
- **Problem:** Program facts exist as separate numeric fields with no plain-language synthesis and no verified/calculated distinction.
- **User impact:** The developer's first question is "what can I build here" — currently answered by assembling four fields.
- **Current implementation:** `verdict/schemas.py:15-19`.
- **Proposed solution:** Plain-language program statement citing standards and source version, using conditional language wherever overlays, lot shape, access, parking, utilities, or title are not fully evaluated. Master-plan and special-district restrictions shown prominently.
- **Dependencies:** LR-B-001, LR-B-002.
- **Likely files/modules:** `verdict/composition.py`, `zoning/`, `VerdictHero.vue`.
- **ADR:** Required if the contract gains fields.
- **Migration:** Possible.
- **Security/privacy:** None.
- **Tests:** Wording tests for conditional cases; a test that an unevaluated overlay forces conditional phrasing.
- **Acceptance criteria:** Program summary distinguishes verified rules from calculated geometry and assumptions; cites standards version.
- **Owner action:** None.

## LR-B-011 — Financial headline with input origins

- **PRD requirement:** LR-V003
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `DealPanel.vue` with "Show assumptions and formula"; every assumption carries an origin
- **Problem:** Financial figures exist but do not identify whether each is a default, source-derived, calculated, or user-overridden value, and there is no direct path to the assumptions.
- **User impact:** §6.4 forbids black-box financial results. A developer cannot act on an MAO whose inputs are invisible.
- **Current implementation:** `verdict/schemas.py:20-29`; `deal/service.py:31` (`assumptions_source`).
- **Proposed solution:** Attach origin metadata to each headline figure; link to the assumption editor; ensure unknown values never render as zero.
- **Dependencies:** LR-B-001, LR-B-018.
- **Likely files/modules:** `deal/`, `verdict/composition.py`, `DealPanel.vue`, `VerdictHero.vue`.
- **ADR:** Required if the contract changes.
- **Migration:** Possible.
- **Security/privacy:** None.
- **Tests:** A test per figure asserting origin is present; a test that a missing input yields Unavailable, not `0`.
- **Acceptance criteria:** Every headline figure identifies its origin and is one interaction from its assumptions.
- **Owner action:** None.

## LR-B-012 — Top deal killers

- **PRD requirement:** LR-V004
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `lib/deal-killers.ts` + `rank_deal_killers`, deterministic and unit-tested
- **Problem:** `risk_flags[]` is an unranked list; nothing surfaces the three that would change the decision.
- **User impact:** JTBD-5 requires material risks be impossible to overlook.
- **Current implementation:** `verdict/schemas.py:31`; `risk/`.
- **Proposed solution:** Deterministic severity-and-decision-impact ordering; at most three in the hero; remainder in the detailed risk section.
- **Dependencies:** LR-B-001.
- **Likely files/modules:** `risk/`, `verdict/composition.py`, `VerdictHero.vue`.
- **ADR:** Not required if ordering is derived, not stored.
- **Migration:** No.
- **Security/privacy:** None.
- **Tests:** Ordering tests; a test that no more than three render in the hero and none are lost from the detail view.
- **Acceptance criteria:** Ordering is deterministic and reproducible; nothing is dropped.
- **Owner action:** None.

## LR-B-013 — Required next checks

- **PRD requirement:** LR-V005
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `ChecklistPanel.vue` + ADR-0068; gap-driven with `not_evaluated` surfaced
- **Problem:** The existing checklist is driven by four domain codes plus market capability categories — not by the specific gaps and flags found on this parcel.
- **User impact:** JTBD-5 asks that unknowns convert into a due-diligence list the developer can act on.
- **Current implementation:** `checklist/logic.py` (14 `ChecklistItem` constructions across codes `zoning`, `valuation`, `deal`, `abatement`), `checklist/service.py`, `api/parcels.py:382`, `frontend/src/components/ChecklistPanel.vue`.
- **Proposed solution:** Extend the existing checklist to derive items from Unavailable/Not-evaluated states and active risk flags. Reuse the module; do not rebuild.
- **Dependencies:** LR-B-001, LR-B-003.
- **Likely files/modules:** `checklist/logic.py`, `checklist/schemas.py`, `ChecklistPanel.vue`.
- **ADR:** Not required.
- **Migration:** No.
- **Security/privacy:** None.
- **Tests:** Tests that each Unavailable field produces its corresponding check; a test that the list never implies completion guarantees approval.
- **Acceptance criteria:** Checklist is gap-driven and deterministic; wording carries the §LR-V005 caveat.
- **Owner action:** None.

## LR-B-014 — Visible score dimensions and naming

- **PRD requirement:** §10.1, §10.2, §10.4
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `WhyScoreDrawer.vue` + `lib/verdict-explain.ts`; existing score preserved
- **Problem:** `opportunity_score` is the sole headline. Buildability, deal, and risk scores exist, but acquisition access / seller motivation is not a verdict dimension — it lives in a separate `distress` endpoint.
- **User impact:** A single composite hides which dimension drove the result, which §24 names an anti-pattern.
- **Current implementation:** `verdict/schemas.py:12,13,28,30`; `distress/` separate.
- **Proposed solution:** Surface the four dimensions separately. Keep `opportunity_score` for compatibility and sorting but demote it from sole headline. Consider renaming per §10.4.
- **Dependencies:** LR-B-009.
- **Likely files/modules:** `verdict/`, `distress/service.py`, `VerdictPanel.vue`, `WhyScoreDrawer.vue`.
- **ADR:** **Required** if renamed or if motivation joins the verdict contract. §10.3 forbids a *new* composite score without the listed evidence — this ticket must not introduce one.
- **Migration:** Possible.
- **Security/privacy:** None.
- **Tests:** Tests that all four dimensions render; a test that no new composite is introduced.
- **Acceptance criteria:** Four dimensions visible and separable; existing score preserved for sorting; no new composite.
- **Owner action:** Approve any rename.

---

# Slice LR-5 — Buildability checklist and wording

## LR-B-015 — Buildability check expansion

- **PRD requirement:** LR-B001
- **Priority:** P1 · **Status:** **Done 2026-08-01** — the five-value `ChecklistStatus` enum was already shipped; the twelve missing LR-B001 checks (permitted use, min lot area, min lot width, max height, floor area, yards, unit density, master plan, parking, utilities, deed restrictions, subdivision) are now built from `zoning_standard` and parcel dimensions via service interfaces. A real parcel returns 22 checks; anything without data reports `not_evaluated` with a reason rather than passing
- **Problem:** LR-B001 lists ~17 checks; the current checklist covers four domain codes plus capability categories. Yards, unit density, parking and loading, utilities, deed restrictions, subdivision, and master-plan requirement are not individually represented.
- **User impact:** A developer cannot see which specific rule failed or was never evaluated — the core of JTBD-3.
- **Current implementation:** `checklist/logic.py`, `checklist/schemas.py` (`ChecklistStatus = pass|warn|fail|info`).
- **Proposed solution:** Extend to the LR-B001 check list with the five required statuses (`Pass`, `Fail`, `Potential issue`, `Not evaluated`, `Not applicable`) — note this differs from the current four-value enum and is a contract change to `ChecklistStatus`.
- **Dependencies:** LR-B-001, LR-B-013.
- **Likely files/modules:** `checklist/`, `zoning/`, `ChecklistPanel.vue`.
- **ADR:** Recommended — the status enum is a public API contract.
- **Migration:** No.
- **Security/privacy:** None.
- **Tests:** A test per check; a test that unevaluated checks never report Pass.
- **Acceptance criteria:** All LR-B001 checks present with correct statuses; market-specific checks respected.
- **Owner action:** None.

## LR-B-016 — Buildability confidence rules

- **PRD requirement:** LR-B004
- **Priority:** P1 · **Status:** **Not started (criteria reviewed 2026-08-01)** — `_confidence()` reads only lot area and lot width; **five of LR-B004's seven inputs are not consulted** and the "high confidence cannot coexist with unresolved critical unknowns" invariant is unenforced
- **Problem:** `buildability_score` exists, but nothing prevents a high-confidence label coexisting with unresolved critical unknowns — which LR-B004 forbids.
- **User impact:** False confidence on a parcel with unevaluated access or overlays is precisely the failure that costs money.
- **Current implementation:** `verdict/schemas.py:12`; `deal/analysis.py` `Confidence`.
- **Proposed solution:** Derive confidence from source completeness, district certainty, geometry quality, lot-shape complexity, overlay coverage, standards version, and evaluated-vs-unevaluated ratio, with a hard rule blocking high confidence alongside critical unknowns.
- **Dependencies:** LR-B-001, LR-B-015.
- **Likely files/modules:** `zoning/`, `verdict/composition.py`.
- **ADR:** Required if confidence semantics change in the contract.
- **Migration:** Possible.
- **Security/privacy:** None.
- **Tests:** A test asserting high confidence is unreachable with any unresolved critical unknown.
- **Acceptance criteria:** The invariant holds across all markets.
- **Owner action:** Define which unknowns are "critical".

## LR-B-017 — Historical variance context guardrails

- **PRD requirement:** LR-B003
- **Priority:** P2 · **Status:** **Done (reconciled 2026-08-01)** — `VarianceOutlookLine.vue` + ADR-0050
- **Problem:** ZBA variance outlook exists over 9,687 appeals; whether it withholds percentages on thin evidence and states sample size, relief type, window, and geography is unverified.
- **User impact:** An approval percentage from insufficient matched evidence is worse than none.
- **Current implementation:** ADR-0050, `zba/`, `frontend/src/components/VarianceOutlookLine.vue`.
- **Proposed solution:** Verify against LR-B003; add sample-size disclosure, thin-evidence withholding, and the "Historical approval context" label.
- **Dependencies:** LR-B-001.
- **Likely files/modules:** `zba/`, `VarianceOutlookLine.vue`.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** None.
- **Tests:** A test that thin evidence withholds the percentage.
- **Acceptance criteria:** All five LR-B003 behaviours present.
- **Owner action:** Define the minimum sample threshold.

---

# Slice LR-8 — Product analytics and error monitoring

*Promoted ahead of LR-7: navigation and onboarding changes cannot be evaluated without instrumentation.*

## LR-B-018 — Product analytics and funnel instrumentation

- **PRD requirement:** LR-A001, LR-A002
- **Priority:** P0 · **Status:** **Blocked by owner action** (vendor approval)
- **Problem:** No analytics of any kind. Verified by exhaustive search across source and both dependency manifests.
- **User impact:** Indirect but decisive — a paid beta that cannot be measured cannot inform a launch decision, and §20 metrics are unobtainable.
- **Current implementation:** None.
- **Proposed solution:** Instrument the 16 LR-A001 events and the LR-A002 funnel behind a thin internal interface so the vendor is swappable.
- **Dependencies:** none technically; owner vendor choice.
- **Likely files/modules:** `frontend/src/main.ts`, `frontend/src/lib/`, `api/` middleware.
- **ADR:** **Required** — new dependency and a privacy decision.
- **Migration:** No.
- **Security/privacy:** **High.** §LR-A001 forbids sending owner PII, contact data, deed text, or sensitive search payloads. Redaction must be enforced at the interface, not left to call sites, and tested.
- **Tests:** Tests that redaction strips owner and contact fields; event-emission tests on the funnel path.
- **Acceptance criteria:** All 16 events emitted; funnel reconstructable; no PII leaves the system.
- **Owner action:** Approve vendor and dependency (CLAUDE.md forbids adding dependencies without discussion).

## LR-B-019 — Error monitoring and correlation identifiers

- **PRD requirement:** LR-A003
- **Priority:** P0 · **Status:** **Blocked by owner action** (vendor approval)
- **Problem:** No frontend or backend exception capture, and **no correlation identifier anywhere** — zero matches for `correlation_id|request_id|x-request-id|trace_id` in backend source.
- **User impact:** A user reporting a failure cannot be traced to a request; a frontend crash is invisible.
- **Current implementation:** `core/logging.py:12` (structlog JSON); `ops/alerts.py` (dataset failures, email-dependent).
- **Proposed solution:** Correlation ID middleware threading through structlog context, plus frontend and backend exception capture for the nine LR-A003 categories. Extend `ops/alerts.py` rather than duplicating it.
- **Dependencies:** LR-B-018 (shared vendor decision).
- **Likely files/modules:** `api/app.py` middleware, `core/logging.py`, `ops/alerts.py`, frontend boot.
- **ADR:** **Required** — dependency and privacy.
- **Migration:** No.
- **Security/privacy:** Errors must carry correlation IDs without leaking PII or secrets (§LR-A003).
- **Tests:** Middleware test that every response carries a correlation ID; a test that log payloads exclude secrets.
- **Acceptance criteria:** All nine categories captured; correlation ID present end to end.
- **Owner action:** Approve vendor.

## LR-B-020 — Launch metrics dashboard

- **PRD requirement:** LR-A004
- **Priority:** P1 · **Status:** **Not started (criteria reviewed 2026-08-01)** — the ops surface reports operational health only; **none of LR-A004's twelve activation/conversion/retention metrics is computed**
- **Problem:** Admin dashboards report operational health, not activation, conversion, or retention.
- **User impact:** Indirect — the owner cannot run §20 gate reviews.
- **Current implementation:** `api/ops.py`, `ops/stats.py`, `ops/digest.py`.
- **Proposed solution:** Internal dashboard or documented query set for the 12 LR-A004 metrics, reusing the ops surface.
- **Dependencies:** LR-B-018.
- **Likely files/modules:** `ops/`, `frontend/src/pages/OpsPage.vue`.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** Aggregate only; no per-user PII.
- **Tests:** Query correctness tests against fixtures.
- **Acceptance criteria:** All 12 metrics reportable.
- **Owner action:** None.

---

# Slice LR-6 — Professional underwriting

## LR-B-021 — Assumption inventory and calculation contract (LR-6A)

- **PRD requirement:** LR-U001, LR-U002, LR-U006
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — underwriting returns 12 assumptions with origins; MAO exposes formula, inputs, exclusions
- **Problem:** `DealAssumptions` carries **6** fields against ~40 required across six groups. Financing, time and carrying costs, itemised acquisition, construction, soft, and exit costs are all absent. MAO shows no formula, inputs, exclusions, or timestamp.
- **User impact:** A developer cannot reproduce their own underwriting, which is the launch promise. §6.4 forbids black-box financial output.
- **Current implementation:** `deal/analysis.py:15-20` (`construction_cost_per_sqft`, `soft_cost_pct`, `selling_cost_pct`, `target_margin`, `default_unit_sqft`, `max_unit_sqft`); `deal/service.py:26-47`; `api/parcels.py:467+` (5 override query params).
- **Proposed solution:** Expand the assumption model to the LR-U001 groups with origin metadata per LR-U002, and surface the MAO formula, inputs, exclusions, and timestamp per LR-U006. Keep the calculation pure and deterministic (CLAUDE.md §7).
- **Dependencies:** LR-B-001.
- **Likely files/modules:** `deal/analysis.py`, `deal/service.py`, `deal/schemas.py`, `api/parcels.py`.
- **ADR:** **Required** — significant contract expansion; ADR-0022/0045 govern the current methodology.
- **Migration:** Only if defaults move to the database.
- **Security/privacy:** None.
- **Tests:** Test-first per CLAUDE.md §12 (valuation is named core logic); a test that missing required inputs prevent a falsely precise MAO.
- **Acceptance criteria:** All LR-U001 groups representable; every assumption identifies its origin; MAO fully transparent.
- **Owner action:** Supply or approve Philadelphia default assumption values.

## LR-B-022 — User underwriting profiles (LR-6B)

- **PRD requirement:** LR-U005
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `/underwriting/profiles` CRUD, profile_id-addressable
- **Problem:** No persisted buy box or underwriting profile exists. `BuyBoxPanel.vue` binds ephemeral filter and area-search stores; there is no `buy_box` concept in the backend.
- **User impact:** The user re-enters criteria every session, and prior analyses cannot be reproduced.
- **Current implementation:** `frontend/src/components/BuyBoxPanel.vue:6-11`; zero backend matches for `buy_box`.
- **Proposed solution:** Persisted, versioned profile covering the LR-U005 fields, reusable by onboarding (LR-B-027) and saved searches.
- **Dependencies:** LR-B-021.
- **Likely files/modules:** new profile model in `accounts/` or a new module, `api/`, `BuyBoxPanel.vue`.
- **ADR:** **Required** — new persisted contract.
- **Migration:** **Required.**
- **Security/privacy:** Profiles reveal acquisition strategy — treat as user-confidential; exclude from analytics payloads.
- **Tests:** Persistence and versioning tests; a test that a prior analysis can be reproduced from a stored profile version.
- **Acceptance criteria:** Profiles saved, versioned, and reusable across sessions.
- **Owner action:** None.

## LR-B-023 — Base, downside, and upside scenarios (LR-6C)

- **PRD requirement:** LR-U003
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — three cases returned with a `case_version`
- **Problem:** `build_scenarios` varies **unit count** (`deal/scenarios.py:19-33` — `Scenario` carries `units`, `by_right`), not case. There is no Base/Downside/Upside axis.
- **User impact:** A developer cannot see downside exposure, which is the risk half of the underwriting decision.
- **Current implementation:** `deal/scenarios.py`.
- **Proposed solution:** Add the case axis as named, deterministic, saved, reproducible scenarios. Preserve the existing unit-count comparison — it is useful and distinct.
- **Dependencies:** LR-B-021, LR-B-022.
- **Likely files/modules:** `deal/scenarios.py`, `deal/schemas.py`, `ScenariosPanel.vue`.
- **ADR:** Required — contract change.
- **Migration:** Required if scenarios persist.
- **Security/privacy:** None.
- **Tests:** Determinism and reproducibility tests per case.
- **Acceptance criteria:** Three named cases, deterministic and reproducible; existing unit comparison retained.
- **Owner action:** Approve downside and upside default deltas.

## LR-B-024 — Sensitivity analysis (LR-6D)

- **PRD requirement:** LR-U004
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — 2-D table (exit x cost multipliers) with `available`/`unavailable_reason` gating
- **Problem:** No sensitivity analysis exists.
- **User impact:** The developer cannot see which variable dominates the outcome.
- **Current implementation:** None.
- **Proposed solution:** One two-dimensional table — exit value versus construction cost, or purchase price versus exit value. Additional pairs only after customer evidence (§LR-U004).
- **Dependencies:** LR-B-021, LR-B-023.
- **Likely files/modules:** `deal/`, new dossier panel.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** None.
- **Tests:** Grid correctness against hand-computed fixtures.
- **Acceptance criteria:** One useful 2-D table, gated per §14.2 free-plan limits.
- **Owner action:** None.

## LR-B-025 — Dossier underwriting experience (LR-6E)

- **PRD requirement:** LR-U001, LR-U006, §6.4
- **Priority:** P1 · **Status:** **Done (reconciled 2026-08-01)** — `UnderwritingPanel.vue` mounted on the dossier Deal tab
- **Problem:** Only 2 of the 5 override parameters are editable in the UI, and edits do not persist.
- **User impact:** The assumptions the customer cares about most are the ones they cannot change.
- **Current implementation:** `frontend/src/components/DealPanel.vue:155-164` (acquisition price, target margin); `ScenariosPanel.vue` read-only.
- **Proposed solution:** Full assumption editor with visible origins, formula disclosure, and persistence through the profile.
- **Dependencies:** LR-B-021, LR-B-022, LR-B-023.
- **Likely files/modules:** `DealPanel.vue`, `ScenariosPanel.vue`, new assumptions editor.
- **ADR:** Not required beyond LR-B-021. **Migration:** No.
- **Security/privacy:** None.
- **Tests:** Frontend tests for edit, persist, and reset-to-default per origin.
- **Acceptance criteria:** Every LR-U001 assumption inspectable and editable; origins visible; no black-box figure remains.
- **Owner action:** None.

---

# Slice LR-7 — Focused navigation and onboarding

## LR-B-026 — Launch navigation consolidation

- **PRD requirement:** §12.1, §12.4
- **Priority:** P1 · **Status:** **Done** — shipped as LR-7A (`9d23cd1`, ADR-0070); five primary destinations with the drifted five in a Research group, verified rendering by e2e flow 1
- **Problem:** 10 primary destinations against a target of 5. Explore, Feed, Sheriff sales, Top plays, Cash buyers, and Leads are six discovery variants competing for one intent.
- **User impact:** A new user has no obvious primary workflow, which directly undermines first-session activation.
- **Current implementation:** `frontend/src/components/AppSidebar.vue:30-43`; routes in `frontend/src/router/index.ts`.
- **Proposed solution:** Consolidate discovery under `Find Lots` as filters/tabs. **Keep all existing routes working via redirects** — §5 and CLAUDE.md §18 both forbid deleting stable features.
- **Dependencies:** LR-B-018 (measure the change), LR-B-006.
- **Likely files/modules:** `AppSidebar.vue`, `MobileTabBar.vue`, `router/index.ts`, affected pages.
- **ADR:** **Required** — supersedes or amends ADR-0029, and `docs/design/ia-and-layout.md` must be updated in the same change (CLAUDE.md §15).
- **Migration:** No.
- **Security/privacy:** None.
- **Tests:** Router tests for every legacy route redirecting correctly; navigation tests.
- **Acceptance criteria:** Five primary destinations; no route 404s; no feature removed.
- **Owner action:** Approve the IA change and the superseding ADR.

## LR-B-027 — Buy-box onboarding and immediate results

- **PRD requirement:** LR-O001, LR-O002, LR-O003, LR-O004, §4.1
- **Priority:** P1 · **Status:** **Done** — shipped as LR-7B (`a1d3949`); `BuyBoxOnboarding.vue` collects criteria and `GET /underwriting/matches` returns matches, verified by e2e flow 2
- **Problem:** Onboarding is a 4-slide feature tour (`OnboardingTour.vue:16-31` — Welcome, Explore the map, Read the Parcel Verdict, Track your deals) that collects **no** acquisition criteria. Only `onboarded_at` is persisted (`accounts/models.py:26`).
- **User impact:** A new user lands with no matched results and no configured buy box, so the §4.2 activation event is unreachable without founder explanation.
- **Current implementation:** `OnboardingTour.vue`, `api/auth.py:86` (`POST /auth/onboarded`).
- **Proposed solution:** Replace the tour with the five LR-O001 steps, persist to the profile from LR-B-022, and land the user on real matching parcels with guided activation.
- **Dependencies:** LR-B-022 (profile storage), LR-B-026 (destination), LR-B-018 (measurement).
- **Likely files/modules:** `OnboardingTour.vue`, `accounts/`, `api/auth.py`, home/explore pages.
- **ADR:** Not required if it reuses the LR-B-022 profile contract.
- **Migration:** Required if onboarding state extends beyond the profile.
- **Security/privacy:** Buy-box data is user-confidential; exclude from analytics payloads.
- **Tests:** Frontend flow tests for all five steps; a test that completion yields non-empty results or an honest empty state.
- **Acceptance criteria:** The §4.1 nine-step first session is completable without assistance.
- **Owner action:** Approve onboarding copy.

---

# Slice LR-9 — Commercial plumbing, support, and policy

## LR-B-028 — Legal and policy surfaces

- **PRD requirement:** LR-P003
- **Priority:** P0 · **Status:** **Blocked by owner action**
- **Problem:** No Terms of Service, Privacy Policy, refund policy, correction policy, or data-license disclosure exists. Disclaimer fragments appear in 9 components.
- **User impact:** Taking payment while publishing zoning and valuation conclusions without published terms is direct legal exposure, and §22 lists legal exposure as P0.
- **Current implementation:** Component-level fragments only; no route, no document.
- **Proposed solution:** Wire owner-approved copy into `/terms`, `/privacy`, and a data-license/attribution surface, plus consistent disclaimer placement. **Claude Code must not author final legal terms (§LR-P003).**
- **Dependencies:** none technical.
- **Likely files/modules:** new pages, `router/index.ts`, footer, `docs/data-licenses.md`.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** The Privacy Policy must accurately describe the analytics decision from LR-B-018 — sequence accordingly.
- **Tests:** Route tests; a test that the disclaimer renders on verdict surfaces.
- **Acceptance criteria:** All seven LR-P003 surfaces published and reachable.
- **Owner action:** **Provide approved copy.** This is the gating step.

## LR-B-029 — Support route and escalation

- **PRD requirement:** LR-P004
- **Priority:** P0 · **Status:** Not started
- **Problem:** No visible support route, response ownership, or escalation path.
- **User impact:** Paying users with no way to reach you churn silently.
- **Current implementation:** None found.
- **Proposed solution:** Visible support contact, billing-support path, severity escalation, and an incident communication template. Correction workflow is LR-B-004.
- **Dependencies:** LR-B-004 (parcel corrections), LR-B-032 (email delivery).
- **Likely files/modules:** frontend footer/account, `docs/runbook.md`.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** Support inbox may receive PII — define retention.
- **Tests:** Route presence tests.
- **Acceptance criteria:** All five LR-P004 elements exist.
- **Owner action:** Nominate the support address and response ownership.

## LR-B-030 — Billing verification in production-like conditions

- **PRD requirement:** LR-P001
- **Priority:** P0 · **Status:** **Blocked by owner action**
- **Problem:** The Stripe surface is implemented and unit-tested but has never been exercised end to end against Stripe.
- **User impact:** A broken upgrade at the moment of payment is the worst possible first impression, and §22 lists broken billing as P0.
- **Current implementation:** `api/billing.py:59-167`; `accounts/billing.py:19-22` (four subscription events); 13 Stripe vars in `.env.example`.
- **Proposed solution:** Verify all 11 LR-P001 behaviours against Stripe test mode, including webhook retry and replay, then document the results.
- **Dependencies:** owner Stripe credentials and products.
- **Likely files/modules:** `accounts/billing.py`, `api/billing.py`, `docs/runbook.md`.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** Credentials must never be committed (CLAUDE.md §6/§13).
- **Tests:** Webhook idempotency and replay tests; entitlement-transition tests per subscription event.
- **Acceptance criteria:** All 11 behaviours verified and recorded.
- **Owner action:** Create Stripe products and supply credentials. **Do not change pricing in this ticket** (§24 forbids combining pricing and entitlement changes).

## LR-B-031 — Entitlement consistency audit

- **PRD requirement:** §14.4
- **Priority:** P1 · **Status:** **Engineering complete 2026-08-01** — audit in `entitlement-audit-2026-08-01.md`; all six surfaces read from `tiers.py` and every numeric claim now has a binding test. Two Enterprise claims (`Team seats`, `API access`) have no implementation behind them and one Pro export entitlement is under-advertised: **three copy decisions are the owner's** before this can be called closed
- **Problem:** Entitlements are centralized in `accounts/tiers.py`, but consistency across pricing page, API authorization, frontend gating, checkout, portal, and upgrade prompts is unverified.
- **User impact:** A capability advertised on the pricing page but gated differently in the API is a refund conversation.
- **Current implementation:** `accounts/tiers.py:63-123`; `api/deps.py`; `PricingPlans.vue`; `UpgradePrompt.vue`.
- **Proposed solution:** Audit all six surfaces against the single source; add tests binding pricing copy to the entitlement module.
- **Dependencies:** none.
- **Likely files/modules:** `accounts/tiers.py`, `PricingPlans.vue`, `UpgradePrompt.vue`.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** None.
- **Tests:** A test asserting every advertised capability maps to an enforced predicate.
- **Acceptance criteria:** All six surfaces agree with `tiers.py`.
- **Owner action:** None.

## LR-B-032 — Production email enablement

- **PRD requirement:** LR-P002
- **Priority:** P0 · **Status:** **Blocked by owner action**
- **Problem:** The Mailgun path is built but SMTP is unconfigured, so account email, digests, and ops alerts are inert.
- **User impact:** Password reset and alerts silently do nothing — a P0 authentication-adjacent failure.
- **Current implementation:** `docs/email.md`; `notifications/`; `ops/alerts.py` (email-dependent).
- **Proposed solution:** Configure credentials, verify the six LR-P002 behaviours including bounce handling.
- **Dependencies:** owner DNS and credentials.
- **Likely files/modules:** `notifications/`, `core/config.py`, `.env.example`.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** Credentials via secret manager only.
- **Tests:** Existing send-path tests; a manual deliverability check.
- **Acceptance criteria:** All six behaviours verified.
- **Owner action:** **Supply DNS and credentials.**

---

# Slice LR-10 — Operations and critical E2E

## LR-B-033 — Backup, retention, and restore procedure

- **PRD requirement:** LR-P005
- **Priority:** P0 · **Status:** **Done 2026-08-01** — weekly cron + pre-migration backups, 30-day retention at script and bucket, documented RTO/RPO, migration rollback, bad-verdict recompute, and a **performed restore test** recorded in `gates.md` G6.
- **Problem:** No documented backup, retention, or restore procedure. `docs/runbook.md` has no match for backup, restore, or `pg_dump`; the only `sync-db.sh` is gitignored and local-only. *(Superseded: the runbook and `scripts/backup-db.sh` had in fact been written; the real gaps were that no schedule existed and no restore had ever been performed.)*
- **User impact:** Paying customers' pipelines, saved searches, and underwriting sit in one database with no tested recovery path.
- **Current implementation:** None documented.
- **Proposed solution:** Scheduled encrypted off-machine backups, retention policy, monthly restore test, documented RTO/RPO, migration rollback, and a bad-verdict-recompute response.
- **Dependencies:** none.
- **Likely files/modules:** `scripts/`, `docs/runbook.md`, deployment configuration.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** Backups contain owner PII — encryption and access control are mandatory (CLAUDE.md §13).
- **Tests:** A documented and executed restore test; not unit-testable.
- **Acceptance criteria:** All seven LR-P005 elements exist and one restore has actually been performed.
- **Owner action:** Approve backup destination and retention.

## LR-B-034 — Branch protection

- **PRD requirement:** LR-P006
- **Priority:** P0 · **Status:** **Blocked by external dependency**
- **Problem:** Branch protection cannot be enabled. Verified with an `admin: true` token: `PUT /repos/turabekh/lotscope/branches/main/protection` and `GET /repos/turabekh/lotscope/rulesets` both return 403 *"Upgrade to GitHub Pro or make this repository public"*. This is a billing constraint, not a settings oversight.
- **User impact:** Indirect but demonstrated — it has already allowed a `ruff format` drift onto `main` (PR #2) and an auto-merge with CI pending (PR #35).
- **Current implementation:** CI is complete and armed; nothing enforces it at merge time.
- **Proposed solution:** GitHub Pro, or a public repository. A local pre-push hook is the only free option and is weaker — bypassable with `--no-verify` and it guards pushes, while both incidents were merges.
- **Dependencies:** owner billing decision.
- **Likely files/modules:** repository settings; `docs/runbook.md` for the interim rule.
- **ADR:** Not required. **Migration:** No.
- **Security/privacy:** None.
- **Tests:** Verify a red PR cannot merge once enabled.
- **Acceptance criteria:** `main` protected with `lint-type-unit`, `integration`, and `web` required.
- **Owner action:** **GitHub Pro (~$4/month) or make the repository public.** Until then, `gh pr merge --auto` is not a gate on this repository — wait for `gh pr checks` to show all three green.

## LR-B-035 — Critical end-to-end tests

- **PRD requirement:** LR-P007
- **Priority:** P1 · **Status:** **Partially done** — Playwright approved 2026-08-01 (ADR-0071); 12 of the 14 flows automated and running in CI. Flows 10 and 11 remain blocked on LR-B-030 (Stripe) and are declared as explicit skips, not silent gaps.
- **Problem:** No E2E framework existed. Zero Playwright references; `make e2e` exited with "not implemented yet".
- **User impact:** A regression in register → onboard → search → dossier → save can reach production undetected.
- **Current implementation:** None. Backend 1,174 tests and frontend 138 cover units and integration only.
- **Proposed solution:** Automate the 14 LR-P007 flows including the mobile path.
- **Dependencies:** LR-B-026, LR-B-027 (flows must be stable first).
- **Likely files/modules:** new `frontend/e2e/`, `Makefile` (`e2e` target), `.github/workflows/ci.yml`.
- **ADR:** Recommended — adds a dependency and CI time.
- **Migration:** No.
- **Security/privacy:** E2E fixtures must not use production credentials.
- **Tests:** The deliverable is the tests.
- **Acceptance criteria:** All 14 flows automated and running in CI.
- **Owner action:** **Approve Playwright** (CLAUDE.md forbids adding dependencies without discussion).

---

# Slice LR-11 — Paid-beta instrumentation

## LR-B-036 — Beta feedback record and trust metrics

- **PRD requirement:** §17.3, §17.4, §20.3
- **Priority:** P1 · **Status:** **Blocked by owner action**
- **Problem:** No structure exists for capturing the §17.3 per-deal feedback record.
- **User impact:** Without it the beta produces anecdotes rather than the §17.4 evidence the launch gate requires.
- **Current implementation:** None.
- **Proposed solution:** Capture the 11 §17.3 fields per reviewed deal, plus §20.3 trust metrics (corrections per 100 verdict views, error counts, provenance coverage, stale-dataset incidents).
- **Dependencies:** LR-B-004, LR-B-018.
- **Likely files/modules:** `docs/launch-readiness/beta/`, possibly a lightweight model.
- **ADR:** Required only if persisted in the product.
- **Migration:** Possible.
- **Security/privacy:** Contains customer commercial information — access-restricted.
- **Tests:** As applicable if persisted.
- **Acceptance criteria:** Every reviewed deal has a complete record; §17.4 evidence is reportable.
- **Owner action:** Recruit the cohort.

---

# Deferred by PRD

## LR-B-037 — §5.2 deferred scope

- **PRD requirement:** §5.2
- **Priority:** P3 · **Status:** **Deferred by PRD**
- **Scope:** Additional markets, nationwide coverage, native mobile, public API, marketplace, owner-side growth campaigns, major tax-appeal expansion, general-purpose AI features, broad direct-mail automation, advanced white labeling, enterprise SSO, large-team administration, speculative scoring models, unrelated refactors.
- **Note:** Existing stable features in these areas — outreach (ADR-0046/0047), appeal packets (ADR-0042), AI summaries (ADR-0043/0044), skip-trace (ADR-0035/0060) — **remain in the codebase and must not be deleted** (§5.2, CLAUDE.md §18). They lose launch priority, not existence.
- **Owner action:** Promote individual items only on measured customer evidence.

---

## Counts

| Priority | Tickets |
|---|---:|
| P0 | 12 |
| P1 | 23 |
| P2 | 1 |
| P3 | 1 |
| **Total** | **37** |

| Status | Tickets |
|---|---:|
| Not started | 27 |
| Blocked by owner action | 8 |
| Blocked by external dependency | 1 |
| Deferred by PRD | 1 |

**ADR required or recommended:** 16 tickets. **Migration required or likely:** 9 tickets.

The 12 P0 tickets, which together gate G1 (controlled paid beta): LR-B-001, LR-B-002, LR-B-003, LR-B-004, LR-B-018, LR-B-019, LR-B-028, LR-B-029, LR-B-030, LR-B-032, LR-B-033, LR-B-034.
