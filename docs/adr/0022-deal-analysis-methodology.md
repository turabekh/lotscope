# 22. Deal analysis methodology

Date: 2026-06-28

## Status

Accepted

## Context

PRD §5.4 — beyond the land AVM, the core developer persona needs the deal math: the value of the *finished* product (ARV), a feasibility/profit calculation, a "max allowable offer" (MAO), and a flag for lots that look underpriced against that math. The existing `valuation` engine answers "what is the land worth"; this answers "is it a good buy, and at what price."

## Decision

**A new `deal` domain engine — pure core plus a thin service adapter — that composes the existing `valuation` and `zoning` engines through their service interfaces.**

- **Boundary.** `deal` depends inward on `valuation.service` (land AVM + comps) and `zoning.service` (by-right units, buildable area, estimated floors); it owns no domain truth of its own and reaches no module's internals. `valuation` stays focused on the AVM.
- **ARV from real improved comps.** The finished-unit value is the median recorded sale of nearby *improved* residential parcels (the same RTT comp finder with `vacant_only=False`). ARV = per-unit value × by-right units. This keeps the estimate grounded in real recorded sales rather than a parametric guess, consistent with the project's "real comps" thesis.
- **Feasibility identity.** `profit = ARV − (acquisition + construction + soft + selling)`, where construction = `construction_cost_per_sqft × GFA`, GFA = `buildable_area_sqft × estimated_floors` (fallback `units × default_unit_sqft`), soft = `soft_cost_pct × construction`, selling = `selling_cost_pct × ARV`, and acquisition is the caller's price or, absent one, the AVM land value (assessed market value as a last resort). `margin = profit / ARV`; `roi = profit / (acquisition + construction + soft)`.
- **MAO back-solves acquisition for the target margin:** `MAO = ARV × (1 − target_margin) − construction − soft − selling`. Feeding MAO back in as the acquisition price yields exactly the target margin — this is the invariant the engine is tested against. A lot is flagged underpriced when its acquisition price sits at or below MAO.
- **Assumptions are configuration, not magic numbers.** Defaults live in `Settings` (Philadelphia rowhouse-infill: `$175/sqft`, soft `15%`, selling `7%`, target margin `20%`, fallback unit `1,200 sqft`) and every one is overridable per request, so a user can model their own scenario. The engine is pure and deterministic over `(DealInputs, DealAssumptions)`.
- **Provenance & honesty.** The result carries the comps and AVM it was built from as `sources`, a `computed_at`, the assumptions used, itemized `reasons`, and a confidence derived from ARV comp depth and dispersion. Missing inputs (no by-right units, no finished comps) degrade gracefully to `null` outputs with an explanatory reason rather than a fabricated number.
- **Endpoint.** `GET /parcels/{parcel_number}/deal` (auth), with optional query overrides for acquisition price and each cost assumption.

## Consequences

- **Informational, not advice.** The output is a model with explicit assumptions and confidence — framed like every other LotScope estimate (§13), never as a guaranteed pro-forma.
- **Standalone first.** This slice ships the engine, endpoint, and a parcel-panel deal panel. Folding `deal_score` / MAO into the `parcel_verdict` contract (migration + batch recompute) is a deliberate follow-up so this commit stays atomic; the verdict contract is unchanged here.
- **ARV is rowhouse-shaped.** Treating each by-right unit as one nearby improved sale fits Philadelphia infill (rowhouse/duplex/triplex) well; it is a weaker proxy for large multifamily or commercial, where a future revision can move to a finished-floor-area $/sqft basis once building gross floor area is ingested.
- **Deferred:** build-to-rent / hold modeling, full scenario comparison (multiple structures side by side), and exporting the pro-forma as a report (§5.4, §5.10).
