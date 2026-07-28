# ADR-0069 — Underwriting assumption contract

Status: proposed (2026-07-28)

Required by `docs/PRD-amendment-03-launch-readiness.md` §LR-U001–U006 (Slice LR-6, sub-slice **LR-6A** only). Backlog ticket LR-B-021. Amends the deal methodology in ADR-0022 and ADR-0045. Depends on ADR-0065.

Scope note: the execution document requires LR-6 to run as separately approved sub-slices. This ADR covers **6A — assumption inventory and calculation contract** only. Profiles (6B), scenarios (6C), sensitivity (6D), and the dossier editor (6E) each follow separately.

## Inventory: what exists today

`DealAssumptions` (`deal/analysis.py:15-20`) carries **six** values:

| Assumption | Platform default | Source |
|---|---:|---|
| `construction_cost_per_sqft` | 175.0 | `core/config.py:90` |
| `soft_cost_pct` | 0.15 | `core/config.py:91` |
| `selling_cost_pct` | 0.07 | `core/config.py:92` |
| `target_margin` | 0.20 | `core/config.py:93` |
| `default_unit_sqft` | 1200.0 | `core/config.py:94` |
| `max_unit_sqft` | 3000.0 | `core/config.py:95` |

Five are overridable as **query parameters** on `GET /parcels/{n}/deal`; two of those five reach the UI (`DealPanel.vue`). Nothing persists. `market.deal_assumption_overrides` supplies per-market values and `assumptions_source()` reports `platform_default` or `calibrated`.

The model is deterministic, tested, and produces MAO, profit, margin, ROI, a confidence signal, and `reasons[]`. It is a sound foundation and is not being replaced.

## What §LR-U001 requires that does not exist

Six groups. Marking what the current six cover:

| Group | Required | Present |
|---|---|---|
| Development program | units, product type, gross area, saleable area, floors, parking, basement, demolition | partial — unit sizing only |
| Acquisition | price, transfer taxes, title/closing, brokerage, legal, survey, environmental | price only, and not persisted |
| Construction | hard cost/sqft, site work, demolition, utilities, excavation, landscaping, contingency | hard cost/sqft only |
| Soft costs | architecture, engineering, permits, entitlement, legal, insurance, overhead | one blended percentage |
| Financing and time | equity, interest, points, construction/entitlement/sales duration, carrying costs | **none** |
| Exit | finished value, commission, transfer taxes, concessions, closeout reserve | one blended percentage |

**Financing and time are entirely absent.** For an infill developer carrying a construction loan through an entitlement period, that is not a rounding difference — it is often the gap between a deal that works and one that does not. This is the single largest gap in the slice.

## Decision

### 1. Itemised groups, with blended percentages retained as defaults

The assumption model expands to the six §LR-U001 groups. The existing blended percentages (`soft_cost_pct`, `selling_cost_pct`) remain as the **default expression** of their groups, so a user who does not itemise gets today's behaviour and today's numbers.

Itemisation is opt-in per group. A user who supplies line items gets the sum; a user who does not gets the blended default. This keeps the current results reproducible rather than silently repricing every stored deal on the day the contract widens.

### 2. Origin is carried per assumption, reusing ADR-0065

Each assumption reports its origin using the `DefaultOrigin` values already defined in `core/provenance.py`: `platform_default`, `market_default`, `derived` (parcel-derived), `user_override`. §LR-U002's five origins map onto these plus the profile origin introduced in 6B.

No second provenance vocabulary. `assumptions_source()` becomes a per-field property rather than one string for the whole calculation.

### 3. Unknown required inputs prevent a figure, never default to zero

§LR-U006 and the LR-6 restrictions are explicit, and §8.4 already forbids it generally. If a required input is unavailable, the dependent figure is `unavailable` with a stated reason — it does not become `0` and the MAO does not acquire false precision.

This is why 6A precedes the editor: the calculation must refuse to produce a number before the UI offers to change one.

### 4. Money and percentages are distinct and precise

Money is stored and computed to the cent; percentages are stored as fractions in `[0, 1]`. Mixing them, or carrying money as float through a chain of multiplications, is how underwriting output drifts from what a user reproduces in a spreadsheet — which for this product is a trust failure, not a rounding one.

### 5. The formula is part of the contract

§LR-U006 requires MAO to show its formula, inputs, target return, scenario, exclusions, and calculation time. The exclusions list is explicit and enumerated — what the model does **not** account for is as much a part of the answer as what it does.

### 6. No user-specific assumption enters parcel truth

Assumptions belong to a user's analysis, never to the parcel. `parcel_verdict` continues to store the platform/market-default calculation so that verdicts remain comparable across users; per-user results are computed on request. Two users underwriting the same parcel differently must not change what either sees of the parcel itself, which is the LR-6 definition of done.

## Consequences

- `DealAssumptions` widens substantially. Its consumers are contained — `deal/` and the verdict composition — so the blast radius is small, but the API contract for `/deal` and `/scenarios` changes.
- Verdict-stored deal figures continue to use platform/market defaults. **`VERDICT_VERSION` is unaffected** provided default values do not change, and this ADR changes none of them.
- Deferred to later sub-slices: persistence (6B), scenario axes (6C), sensitivity (6D), and the editor (6E). 6A defines the contract and the calculation; it does not add storage.
- **Risk:** the itemised defaults for categories that do not exist today — financing rates, durations, carrying costs — are commercial assumptions I should not invent. They are proposed as named constants with explicit provenance and flagged for owner review, in the same spirit as the ADR-0067 thresholds.

## Open question for the owner

**Philadelphia default values** for the new categories: interest rate, points, construction and entitlement durations, transfer-tax rates, and typical brokerage. These are market facts I can research but should not assert. Until supplied, the new categories default to *unavailable* rather than to a guessed number — which under §3 means dependent figures decline to compute rather than quietly using a placeholder.
