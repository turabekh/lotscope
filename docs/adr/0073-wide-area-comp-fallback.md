# ADR-0073 — A wide-area comp fallback, priced as a rough guide

Status: accepted (2026-08-01)

Extends **ADR-0049** (valuation calibration) and works with **ADR-0072** (screening must not outrun its evidence). Nothing in either is reversed.

## Context

ADR-0072 stopped the product calling a parcel a strong candidate when its margin was priced from the assessed value rather than a modelled land value. That was correct, and it downgraded 4,421 Philadelphia parcels. It also left them saying nothing useful about price.

The obvious question is whether those parcels genuinely have no comparable land sales, or whether the search window is simply too tight. Measured on a random sample of 400 of the 4,421 actually downgraded parcels:

| | of 400 |
|---|---:|
| Zero comps under current rules | **398** |
| Recovered by radius 1,500 → 3,000 ft | 220 |
| Recovered by lookback 3 → 5 years | 58 |
| Recovered by dropping use-class segmentation | 217 |
| Recovered by radius **and** lookback together | 259 |
| Recovered by radius + lookback + cross-use | **338** |
| Recovered by allowing sales of improved land | 398 |

Two results decided the design.

**Allowing improved-land sales recovers everything and is invalid.** A sale of land with a structure on it prices the structure. Using those as land comps would produce a confident-looking number that measures the wrong thing — the same class of error ADR-0072 exists to prevent, and worse, because it would look well-supported.

**Restricting the cross-use relaxation to residential↔commercial costs nothing.** Allowing all four use classes to mix recovers 338; allowing only residential↔commercial recovers the same 338. Industrial and special land contributes no recoveries, so it stays segregated rather than being permitted for free. In Philadelphia, CMX strips sit inside RSA blocks and land trades comparably; industrial land does not.

The remaining ~15% have no vacant-land sale within 3,000 ft in five years. They are honestly unpriceable and stay that way.

## Decision

**A widened search runs only as a fallback, never as the default.** The existing query — 1,500 ft, 3 years, strict use class — runs first and is unchanged. Only when it returns *nothing* does a second query run at 3,000 ft, 5 years, with residential and commercial treated as interchangeable.

This ordering is the point. Widening globally would pull more distant comps into the 94% of parcels that already have good local ones, because comps are taken nearest-first up to a limit — diluting estimates that are currently sound. A fallback cannot regress them, by construction.

**A wide-area estimate is always `low` confidence**, regardless of comp count or dispersion. Five tightly-clustered sales half a mile away are not evidence about this block, and the existing confidence formula — which reads only count and coefficient of variation — would otherwise call them `high`. Distance is not in that formula, so the cap is applied outside it.

**A wide-area estimate does not earn `strong_candidate`.** It produces a real land value, a real margin, and a distinct screening reason naming the wider search. The recommendation stays `worth_investigating`. Showing the figure while withholding the confidence claim is exactly the line ADR-0072 drew.

**The fallback applies only to markets where its window has been measured.** A per-market registry (`valuation/fallback.py`) holds the radius and lookback, and Philadelphia is the only entry. An unregistered market gets no fallback and behaves exactly as before.

This follows the discipline ADR-0057 established for distress profiles: per-market calibration is registered, not inherited. It matters here because the nightly `recompute_vacant_verdicts` cron runs with no market filter, so an ungated change would reach every market the night it deployed. Proportionally the pilots are far more exposed than Philadelphia - 18.5% of Philadelphia verdicts carry no valuation, against 91.9% for Pittsburgh and 100% for Harrisburg - and 3,000 ft spans a large share of a city the size of Harrisburg, where "wide-area" could amount to a citywide average. None of that has been measured, so none of it ships.

**Provenance records the tier that actually ran**, not the tier requested: `comp_tier`, the effective `radius_ft` and `years`, and the accepted use classes flow into `valuation.sources` and from there into the verdict's provenance. No migration is needed — `parcel_verdict` already stores the merged sources.

## Consequences

**Roughly 3,758 of the 4,421 parcels gain a land value** they did not have, all marked low confidence, none of them promoted to strong candidate. The user gains a number to reason about where previously there was nothing.

**A third screening reason now exists** for a strong margin that cannot be trusted: assessed-value basis, wide-area basis, and the ordinary case. They are deliberately distinct strings — a reader can tell *why* the confidence is withheld, which is the whole purpose.

**`decision_version` stays `d1`.** The recommendation vocabulary and every threshold are unchanged. A new branch was added ahead of the assessed-value branch; it can only move a parcel from `strong_candidate` to `worth_investigating`, never the reverse.

**Existing verdicts need recomputing to pick this up**, on the same targeted basis as ADR-0072: only rows whose valuation was previously empty can change.

**This still does not create comps that do not exist.** ~15% of the starved set remain unpriceable, and the honest answer for them is unchanged.
