# 33. Vacancy-confidence cross-check

Date: 2026-07-03

## Status

Proposed

Gates PRD-amendment-01 feature **A11**. Extends the Vacant Property Indicators ingest and `parcel.vacancy_confidence`.

## Context

`is_vacant` is set from the City's Vacant Property Indicators (VPI) dataset (`ingestion/loaders/vacancy.py` upserts `is_vacant = True` for VPI parcels). VPI has known **false positives** — "that lot actually has a house on it" is the single most embarrassing demo failure. The `parcel.vacancy_confidence` column (`Numeric(5,4)`) already exists but is not populated with any corroboration signal. We hold data that can corroborate or contradict VPI: L&I vacancy-code violations and demolition events (corroborate), and recent building permits or an improvement value that dwarfs land value (contradict).

## Decision

**Compute `vacancy_confidence` as a corroboration score over signals we already ingest; keep the `is_vacant` display unchanged but qualify low-confidence cases in the UI. No verdict version bump.**

- **Confidence is derived from corroboration**, starting from a VPI baseline and adjusted:
  - **Raise** on L&I vacancy-code violations and demolition events on the parcel.
  - **Lower** on recent building permits, or `improvement_value` ≫ `land_value` (a substantial structure is assessed) — the classic "house on the lot" contradiction.
  The exact baseline, increments, and thresholds are documented in this ADR's implementation and unit-tested as a **pure scoring function** (mirroring the distress-index weight table in ADR-0015 — deterministic, fixtured, no network). Proposed starting point: VPI-present baseline ≈ 0.6; +corroboration toward 1.0; −contradiction toward 0.0; clamp `[0, 1]`.
- **Population:** computed in the ingest/merge path (or a small nightly recompute) once the contributing datasets are loaded, so it sees both VPI and L&I/permit/value sides. Written to `parcel.vacancy_confidence`; provenance is the set of contributing signals.
- **Display unchanged, honesty added:** `is_vacant` still renders as today (no flip-flopping the boolean on a soft signal). When `vacancy_confidence` is below a threshold, the "Vacant" chip tooltip gains a **"low confidence"** qualifier so the boolean isn't presented as certainty.
- **No `VERDICT_VERSION` bump.** `vacancy_confidence` does not feed any scored verdict field in v1 — it is a display/trust qualifier — so no recompute sweep. (Contrast ADR-0028: that flag was scored and required a bump.) If confidence is later wired into `opportunity_score` weighting, that is a deliberate verdict-contract change with its own bump — deferred here.

## Consequences

- The worst demo failure (a built parcel shown as a confident vacant lot) is defused: the contradicting signals pull confidence down and the UI stops asserting certainty, without suppressing genuine vacant lots.
- Confidence is only as good as the corroborating data's coverage; parcels with no L&I/permit history sit at the neutral VPI baseline, which is honest (we have nothing to add). This is intentional — absence of corroboration is not treated as contradiction.
- Keeping `is_vacant` boolean stable avoids churn in every downstream consumer (leads, filters, comps' `vacant_only`, saved-search criteria); only the tooltip and the stored confidence change.
- The scoring weights are a documented, tunable table like ADR-0015's; retuning them is a scoring-function change, not a schema or contract change.
- **Deferred:** folding confidence into lead ranking / `opportunity_score`; a confidence threshold that would actually hide a lot from vacant-only surfaces (v1 only annotates, never hides).
