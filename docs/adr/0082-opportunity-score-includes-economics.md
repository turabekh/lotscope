# ADR-0082 — The opportunity score cannot contradict the recommendation (verdict v10)

**Status:** Accepted · **Date:** 2026-08-16 · **Rides the v9 → v10 bump opened by ADR-0081**

**Open at acceptance.**

1. **`est_margin` inherits the land-value band.** Acquisition cost defaults to the modelled land value, so margin — and therefore the economics factor — carries that uncertainty. ADR-0081 narrowed the band; it did not remove it. The factor is deliberately coarse (a four-point curve, not a precise function) so that it is robust to that.
2. **`insufficient_data` lots are still surfaced.** 2,004 Philadelphia vacant lots have unavailable critical buildability fields. They are treated as just-viable rather than excluded, which is a judgement, not a measurement.
3. **Philadelphia only was measured.** The change is market-agnostic in code; the impact figures below are `phl`.

## Context

`opportunity_score` was `0.6 × buildability + 0.4 × (100 − risk)`. It contained no economics of any kind.

The same verdict carries a `recommendation` from `decide()` (ADR-0067), which *does* weigh economics — `economics_unattractive` when the build is infeasible or the margin falls below `VIABLE_MARGIN`. So the verdict held two conclusions drawn from different evidence, and they disagreed. Measured on production, over 36,774 Philadelphia vacant lots:

| recommendation | lots | scoring ≥ 70 | avg score |
|---|---|---|---|
| high_entitlement_risk | 22,558 | 0 | 52.9 |
| **economics_unattractive** | **10,867** | **9,619** | **84.2** |
| insufficient_data | 2,004 | 1,353 | 71.2 |
| worth_investigating | 669 | 511 | 80.3 |
| strong_candidate | 664 | 664 | 89.4 |

**10,867 lots were told "the deal does not carry itself" and scored 84.2 on average — above the 80.3 of the lots the product recommends investigating.** 88.5% of them scored 70 or better.

This is not a cosmetic inconsistency, because the score is the sort key. `savedsearch/service.py`, `savedsearch/matching.py` and `search/spatial.py` all order by `opportunity_score DESC`. Saved-search alert emails and area search results therefore led with parcels the product's own recommendation says to pass on.

For a screening tool this is the defect that matters most. A developer's entire reason to use it is to have the list ordered for them. An order that puts 9,619 money-losing lots above the 1,333 genuinely actionable ones does not save them work; it hands back the same haystack with a misleading label.

## Decision

**Economics scales the existing blend rather than joining it as a fourth term.**

```
opportunity = (0.6 × buildability + 0.4 × (100 − risk)) × economics_factor
```

`economics_factor` runs from **0.4** to **1.0**, anchored on the constants `decide()` already uses, so the score and the recommendation cannot drift apart:

| margin | factor |
|---|---|
| infeasible, or ≤ 0% | 0.40 |
| `VIABLE_MARGIN` (10%) | 0.70 |
| ≥ `STRONG_MARGIN` (20%) | 1.00 |
| **unknown** | **0.70** — treated as just-viable |

### Why scaling, not a fourth weighted term

The additive form was measured first: `0.45 × buildability + 0.25 × (100 − risk) + 0.30 × economics`. It fixed the economics problem and broke something that was working — `high_entitlement_risk` lots scoring ≥ 70 went from **0 to 1,614**, because lowering the buildability weight diluted a penalty that was correctly severe. Scaling leaves the buildability/risk balance exactly as it was and corrects only the missing dimension.

### Why unknown economics is 0.70 and not 1.0

Treating unknown as 1.0 asserts "as attractive as a proven 20% margin", which is a default standing in for evidence — precisely what LR-B-001 and the field-state taxonomy forbid. Treating it as 0 asserts unprofitability, which is equally unfounded. 0.70 is the `VIABLE_MARGIN` point: *marginal until established*. It ranks below anything with proven economics and above anything with proven bad economics, which is the correct ordering and the only claim the evidence supports.

## Consequences

Measured against production data, the same 36,774 lots:

| recommendation | scoring ≥ 70 before | after |
|---|---|---|
| strong_candidate | 664 | **664** |
| worth_investigating | 511 | 459 |
| insufficient_data | 1,353 | 0 |
| **economics_unattractive** | **9,619** | **9** |
| high_entitlement_risk | 0 | **0** |

**`strong_candidate` is untouched** — 664 lots, average 89.4 before and after. The change removes noise from the top of the list without disturbing the signal.

**The top of the list shrinks by roughly 78%**, from ~11,148 lots scoring ≥ 70 to ~1,132. That is the point. The 1,333 lots carrying `strong_candidate` or `worth_investigating` are what a developer should see first, and now do.

**`insufficient_data` lots leave the top band entirely** (1,353 → 0). Their base scores cluster just above 70, so the 0.7 factor moves all of them below it at once. This is a threshold artefact rather than a ranking change — their position *relative* to other classes is unchanged and correct. The 70 cutoff is an analysis convenience, not a product constant.

**Every Philadelphia opportunity score moves**, so this is a methodology change. It rides the v9 → v10 bump already opened by ADR-0081 rather than opening a second one, per the batching invariant in `docs/verdict-bump-queue.md`.

**Alert content changes when the recompute runs.** Saved-search alerts read stored rows; until the batch runs they will keep sending the old ordering. This is the strongest argument for running the v10 recompute sooner rather than later — every day it is deferred is a day of alert emails leading with parcels the product recommends passing on.
