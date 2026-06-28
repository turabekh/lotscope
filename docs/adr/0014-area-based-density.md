# 14. Area-based dwelling-unit density

Date: 2026-06-28

## Status

Accepted

## Context

By-right unit count was a flat per-district cap (`zoning_standard.max_units`). That is wrong for Philadelphia's multi-family districts, where Title 14 sets density as **minimum lot area per dwelling unit** — so the unit count scales with lot size. Without this, the assemblage radar (ADR-0013) could not answer its headline question: "assemble these lots → how many more units by-right?"

## Decision

**Add `zoning_standard.lot_area_per_unit_sqft` and compute by-right units from lot area where Title 14 defines density by area.**

- `by_right_unit_count(standard, lot_area)` = `max(1, floor(lot_area / lot_area_per_unit_sqft))` when the district permits multi-family and has a per-unit area; otherwise it falls back to `max_units`. Pure and unit-tested; used by both single-lot buildability and the assemblage combined-lot estimate.
- **Seeded only where the grounded Title 14 corpus (`data/title14/sections.jsonl`) states a by-right per-unit area** — not from memory (golden rule §9):
  - **RM-1**: 480 sq ft/unit.
  - **CMX-2**: 480 sq ft/unit.
  - **CMX-2.5**: 360 sq ft/unit.
- **Assemblage** exposes `by_right_units_current` and `by_right_units_combined` (current lot vs. lot + same-zoning candidates), via a `zoning.service` interface function, so the panel can show "1 → N units."

## Consequences

- **Density-governed (FAR) districts are intentionally excluded.** RM-2/3/4, RMX-1/2/3, and CMX-3/4/5 set capacity via a floor-area ratio, where unit count depends on building and unit-size design choices, not a lot-area-per-unit constant. For those, assembling raises buildable floor area but we do **not** assert a unit count; the radar shows combined land and tells the user to confirm. Modeling FAR-to-units is a separate follow-up.
- **RM-1's first tier is approximated.** Title 14 RM-1 is denser for the first 1,440 sq ft (360 sq ft/unit) then 480 sq ft/unit above. We use the marginal **480** rate, which is what governs as a lot grows — the right rate for the assemblage delta — and is slightly conservative for small standalone lots. Documented as approximate; the UI says "confirm with the zoning code."
- This changes single-lot by-right units for RM-1/CMX-2/CMX-2.5 verdicts (previously null/flat) to area-scaled counts. Verdicts refresh on recompute.
- All outputs remain informational; the unit estimate is not a zoning determination.
