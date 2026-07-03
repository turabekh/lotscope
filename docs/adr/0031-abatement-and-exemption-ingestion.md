# 31. Abatement & exemption ingestion

Date: 2026-07-03

## Status

Accepted

Gates PRD-amendment-01 feature **A9**. Extends ADR-0004 (ingestion) and ADR-0022 (deal methodology).

## Context

OPA's `opa_properties_public` carries exemption fields — `exempt_land`, `exempt_building` — that the OPA loader currently drops (`ingestion/loaders/opa.py` maps only `market_value`, `taxable_land`, `taxable_building`, geometry, and descriptors). A non-zero `exempt_building` is the signature of an active tax abatement (Philadelphia's 10-year new-construction/improvement abatement exempts the improvement value from taxation). Abatement status materially changes a developer's carrying-cost math and is a first-question diligence item, so its absence is a credibility gap (PRD §5.4).

This is a pure additive-data change: the fields exist upstream, join on the parcel key we already reconcile, and require no new source or new transport.

## Decision

**Ingest the OPA exemption fields onto `parcel`, surface them, and treat a detected abatement as an informational signal — no verdict version bump.**

- **Model:** add `exempt_land` and `exempt_building` (both `Numeric(14,2)`, nullable) to `parcel`. Alembic migration in this slice; backfilled by the next OPA load (idempotent upsert, ADR-0004).
- **Loader:** add `exempt_land`, `exempt_building` to the OPA fetch field list and the record→parcel mapping, alongside the existing `taxable_*` fields. Parse defensively (nullable, "never trust upstream" §7).
- **Detection is derived, not stored as truth:** an abatement is considered active when `exempt_building` (or `exempt_land`) is present and `> 0`. This lives as a small pure helper, not a persisted boolean, so the rule can evolve without a migration.
- **Surfacing:**
  - `PropertyFacts` (frontend) shows assessed vs exempt breakdown when an exemption is present.
  - The deal engine (`deal/analysis.py`) adds an informational `reasons` note when an active abatement is detected (it does not alter the deal score math in v1 — surface-and-note, mirroring how other informational reasons read).
  - The DD checklist gains a `liens_taxes`-category item noting the abatement and that the buyer should confirm remaining abatement term with OPA.
- **No `VERDICT_VERSION` bump.** Nothing here changes `opportunity_score`, `risk_score`, or any scored verdict field, so no recompute sweep is required (contrast ADR-0028's historic flag, which was scored and forced a bump). This follows the standalone-informational-signal pattern.

## Consequences

- Developers see abatement status where they look first (property facts + diligence checklist) without a 550k recompute.
- The exemption columns are reusable later: if we ever model the abatement's effect on carrying cost in the deal engine (a scored change), that becomes a deliberate verdict-contract change with its own bump — explicitly deferred here.
- Values are OPA-sourced and cited "as-is" (§13); the checklist item states the buyer must verify the remaining term, not that an abatement is guaranteed to transfer.
- Edge case respected: `exempt_building > 0` can also arise from non-abatement exemptions (homestead, non-profit). v1 labels it "exemption/possible abatement — verify," not a definitive abatement claim, to avoid over-asserting on ambiguous upstream data.

## Follow-up (2026-07-03): shipped surfaces + deferred deal reason

Shipped as `a1d4e7c2b830` (migration) + loader/schema/UI: `exempt_land`/`exempt_building` on `parcel`, mapped from OPA (`exempt_land`, `exempt_building`), flowing to `ParcelDetail` via `from_attributes`; a pure `has_active_exemption(exempt_land, exempt_building)` helper (`parcels/abatement.py`); a **PropertyFacts** "Tax exemption" row; and an **info** checklist item in the *Liens & taxes* category (threaded into `build_checklist(verdict, has_abatement=...)` from the checklist service, which reads the parcel through `parcels.service` — no verdict flag, no version bump).

**Deferred:** the deal-engine `reasons` note. The deal `reasons` are produced by the pure `analyze_deal` from `DealInputs`; adding an informational abatement string there means threading a flag through `DealInputs`/`build_deal`/two service entry points — disproportionate plumbing across the deal contract for a non-scored note that PropertyFacts and the diligence checklist already surface prominently. Recorded here so the follow-up isn't lost; it can ride the next deal-schema change cheaply.
