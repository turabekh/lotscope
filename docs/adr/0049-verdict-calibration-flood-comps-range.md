# 49. Verdict calibration: SFHA-only flood flags, package-deed comp validity, percentile value range

Date: 2026-07-05

## Status

Accepted

## Context

A field test of parcel `056219700` (558-60 N Lawrence St), cross-checked against OPA records and an external review, exposed three calibration defects that each degrade a stored verdict field:

1. **Flood Zone X flagged as risk.** The risk engine flagged *any* flood-zone intersection, and Zone X — FEMA's minimal-hazard designation covering much of the city — carried a medium flag worth 20 points. The AI snapshot then narrated it as "the primary risk flag." Zone X is not a hazard; the 20 points are phantom and apply to a large share of parcels.

2. **Comp inflation from multi-parcel package deeds.** Philadelphia RTT attaches the full deed price to every parcel on a package deed, so a 3-lot $600k sale reads as three $600k land comps. The subject's land estimate (~$569/sqft on a 940 sqft lot) was inflated by this.

3. **Raw min/max value range.** The reported range was the full spread of surviving comp rates ($162,692–$658,000, ~4×) shown at "60%" confidence, letting a single outlier set the ceiling.

Per the ADR-0028 lesson — three `VERDICT_VERSION` bumps in one session thrashed the ~550k recompute repeatedly — changes that alter stored verdict output must batch into **one** version bump with **one** citywide recompute, never one bump per fix.

## Decision

Ship all three calibration changes together and bump `VERDICT_VERSION` **once** (v7 → v8):

- **Flood flags are SFHA-only.** In the risk engine (not the loader — ingested data stays complete), a zone whose normalized designation starts with `A` or `V` (A, AE, AH, AO, AR, A99, V, VE) flags `high` and the detail names only the SFHA zones; 0.2%-annual / shaded-X / legacy `B` flags `info` at zero weight; unshaded X, legacy C, open water, and minimal-hazard descriptors do not flag. Descriptive minimal phrases take precedence over the prefix test so "AREA OF MINIMAL FLOOD HAZARD" is not read as SFHA.

- **Package-deed sales are excluded from comps.** The shared comp finder excludes any sale whose `document_id` appears on more than one parcel (null `document_id` kept as indeterminable). Because the finder is shared, this cleans both the land AVM comps and the deal engine's improved-sale ARV comps in one place. Provenance records `package_deeds_excluded`.

- **Value range is the 10th–90th percentile when depth allows.** With at least five usable comp rates, `low`/`high` are the p10/p90 of the `$/sqft` rates times subject area; with fewer, min/max is kept. The point estimate stays the median; confidence/CV logic is unchanged.

## Consequences

- **A citywide recompute is required and is run out-of-band** (`make recompute-verdicts`), not in the change session. On-demand refresh (`get_or_compute_current_verdict`) upgrades any viewed parcel to v8 immediately, so the UI is correct per-parcel before the sweep completes.
- **Risk scores drop ~20 points for unshaded-X parcels citywide** and value ranges narrow. These are corrections, not regressions.
- **Batch consumers see mixed versions until the sweep finishes.** The distress/leads score filters and saved-search `min_opportunity_score` read whatever version each parcel currently carries; a parcel viewed (and lazily recomputed) mid-sweep may rank differently from a not-yet-swept neighbor. This is transient and resolves when the sweep completes.
- **One bump, not three** — honoring ADR-0028, the recompute runs once for all three changes.
- **Out of scope, noted for follow-up:** entitled-site comp detection beyond package-deed exclusion (revisit with permit-join heuristics), and folding any new signal into the verdict contract (defer to the next batched bump).
