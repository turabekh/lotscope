# 45. Deal-model ARV scaled to finished area (root fix for infeasible-build blowups)

Date: 2026-07-04

## Status

Proposed

Follows the infeasible-build **guardrail** shipped in `fix(deal): guardrail infeasible builds` (verdict **v7**). The guardrail stops nonsensical numbers from reaching users; this ADR proposes the root fix that makes the deal magnitudes *correct*, not merely *floored*. Touches the `deal` engine and the `valuation`/`ingestion` boundary, and will bump the verdict version again — hence an ADR.

## Context

The deal model builds its P&L from two sides that **do not share a size basis** (`deal/analysis.py`):

- **Cost side scales with the built envelope:** `GFA = min(footprint × floors, units × max_unit_sqft)`, then `construction = construction_cost_per_sqft × GFA`.
- **Value side is a flat neighborhood comp:** `ARV = median(finished_comp_prices) × units` — it ignores *how big* the modeled building is.

When the modeled envelope is large but neighborhood finished values are low, the two sides diverge and profit goes massively negative. Concretely, parcel `234001200` (1420 Deal St): a single by-right unit is modeled as a 3,000 sqft build (`max_unit_sqft` cap) costing `175 × 3000 = $525,000`, but "sold" at the flat comp median of **$97,500** (the price of the area's typical, smaller finished homes) → profit −$535,041, margin −549%, MAO −$532,575.

Measured across the dev DB at v6: **28,224 of 38,163 verdicts (74%) had a negative MAO**, 40% worse than −$100k, worst **−$163,808,370** (an 11-acre RM-1 apartment complex modeled as 998 rowhouse-priced by-right units on a 358k-sqft envelope). The guardrail (v7) floors these to $0 and labels them "not feasible" — honest, but it throws away signal: a lot that is *barely* infeasible and one that is *wildly* infeasible now look identical, and genuinely-feasible deals in low-value areas may still be distorted because ARV never reflects the built size.

**The real defect:** ARV must scale with the finished square footage the cost model assumes you build. It currently does not, because our comp sales carry **no finished/building area** — `sale` has only `lot_area_sqft`, and `parcel` has only `lot_area_sqft` + `exempt_building`. So we cannot compute a price-per-finished-sqft today.

## Decision

**Price ARV per finished square foot, derived from comps that carry building area, so cost and value share one size basis; and re-scope the two envelope assumptions that inflate the build.**

1. **Ingest finished area.** Add OPA `total_livable_area` (available in `opa_properties_public`) to the parcel record and to the comp projection, so each finished comp has both a sale price and a livable area. (Reconcile via the existing OPA↔PWD↔RTT keys; validate defensively per §7 — livable area is often 0/NULL and must be filtered, not trusted.)
2. **Compute `price_per_finished_sqft`** from comps with a usable `sale_price` and `total_livable_area` (median of `price / area`, with the same comp hygiene as ADR-0032 and the same confidence/CV scoring as `_finished_value_confidence`). Fall back to the current flat-per-unit ARV only when finished area is unavailable for the comp set — and mark that fallback in `reasons` + lower the confidence.
3. **ARV = `price_per_finished_sqft × sellable_GFA`**, where `sellable_GFA` is the same GFA the construction cost is computed on (net of an efficiency factor if we choose to model common area). Both sides of the P&L now move together; a bigger modeled building costs more *and* is worth more, and infeasibility reflects a genuine cost-vs-value gap rather than a unit mismatch.
4. **Fix the two inflated envelope assumptions surfaced by the audit:** `deal_max_unit_sqft = 3000` over-sizes a single Philadelphia rowhouse (typical 1,000–1,600 sqft) — revisit per use class; and the by-right **unit-count / envelope estimate on large multi-family parcels** (the 998-unit case) needs a sanity bound so a legacy apartment complex isn't modeled as a fresh 998-unit ground-up build. Deal analysis should also be **skipped or flagged on clearly non-vacant, already-improved parcels**, where a ground-up pro-forma is meaningless.
5. **Bump `VERDICT_VERSION` v7 → v8** and re-sweep; the `infeasible` flag stays (now driven by a correct cost-vs-value comparison), but negative-MAO magnitudes should largely disappear on their own.

## Consequences

- **Deal magnitudes become defensible.** ARV, profit, margin, and MAO stop being artifacts of an envelope/comp mismatch; the AI report and dossier can safely quote them again (the report/summary infeasibility guard from the guardrail remains as a belt-and-suspenders floor).
- **New data dependency.** This is the first deal-critical use of OPA `total_livable_area`; it must be ingested, reconciled, and freshness-tracked like any other dataset, and it is frequently missing/zero → the flat-per-unit fallback (2) must remain and be clearly attributed so we never silently present a low-confidence ARV as high-confidence.
- **Test-first, per §12.** New unit tests: price-per-finished-sqft from comps, ARV scales with GFA, fallback path when area is absent, `max_unit_sqft` re-scoping, the non-vacant/large-multifamily guard. Spatial/ingestion tests for the livable-area join via testcontainers.
- **Scope boundary.** This ADR is the *valuation correctness* fix. It does **not** attempt a full development pro-forma (financing, absorption, phasing) — that remains out of scope. If comp finished-area coverage proves too thin in target neighborhoods, an interim step is a per-use-class $/sqft table rather than blocking on comp-derived rates.
- **Superseded guardrail behavior:** once v8 lands, the MAO floor and the "not feasible" labeling are expected to fire far less often and only on genuinely infeasible economics; the guardrail code is retained, not reverted.
