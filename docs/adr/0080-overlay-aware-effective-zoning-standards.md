# ADR-0080 — Overlay-aware effective zoning standards (verdict v9)

**Status:** Accepted · **Date:** 2026-08-11 · **Supersedes nothing; bumps `VERDICT_VERSION` v8 → v9**

## Context

`docs/audit/zoning-standard-vs-title14.md` compared every seeded dimensional value in `TITLE_14_STANDARDS` against the parsed Title 14 tables in `code_provision.table_data`. 71 of 72 determinate values across 32 districts matched exactly. Four defects came out of it, and one of them cannot be fixed by changing a number.

**RSA-5's minimum lot area is geography-dependent.** Table 14-701-1 (p.951) prints **960**; six §14-500 overlay sections restore **1,440** inside their boundaries. `zoning_standard` holds one scalar per district, so whichever value it carries is wrong somewhere:

- Seeded at 1,440 (the shipped state): every RSA-5 lot in [960, 1,440) outside the six is wrongly told it fails the minimum — **58,540 parcels**, false negatives.
- Corrected to a bare 960: the **54,376 parcels** inside the six are wrongly told they clear a minimum their overlay raises — false positives, the worse failure mode, because "you can build" is advice someone acts on.

A prior attempt (`98cadfa`, reverted in `4122af1`) shipped the bare scalar on the rationale that the false positives were "confined to three overlays". Six sections carry the 1,440 minimum and the two largest — `/EDO` 13,530 parcels and `/SIX` 12,042 — were never counted. The trade is roughly one-for-one, which is not a fix.

**A scalar column cannot express a conditional standard.** That is the decision this ADR exists to make.

## Decision

### 1. Effective standards resolve at one seam

A new seeded table, `overlay_standard`, records per-overlay field modifications keyed on `code_section` — the column `zoning_overlay` already carries, so the join is a column equality rather than a name match.

`_get_standard` (`zoning/service.py`) gains an optional `parcel_number`. When supplied, it joins the parcel's overlays to `overlay_standard` and returns an **effective** standard: base values with applicable overlay modifications applied, plus an additive `overlay_modifications` list carrying the base value, the effective value, the overlay code, and the operative subsection cite.

This is the whole change surface. `_get_standard` has exactly two callers — `get_parcel_standard` and `assess_parcel` — and every consumer of zoning standards reaches the table through one of them: buildability, verdict composition, deal, AI, reports, checklist, subdivision, and assemblage unit estimates. Because the new field is additive, none of them breaks; they read the same attribute names and get the correct number.

### 2. Conflicts are surfaced, not resolved by invention

Of the 54,376 affected parcels, 54,344 sit under exactly one of the six and 32 under two — and all six set the identical value, so no parcel has a conflicting standard today. The code states no precedence rule between overlays. Applying "most restrictive wins" would be inventing law.

Resolution is deterministic (ordered by field then citation); a second modification that *agrees* applies once; one that *disagrees* is discarded and logged as `overlay_standard_conflict`. If Philadelphia ever writes conflicting overlays, we find out from a log line rather than from a wrong verdict.

### 3. The small-lot suppression is narrowed, because it was wrong

`analyze_subdivision` suppressed small-lot division entirely whenever a parcel touched *any* overlay — all 193 of them — with a "verify the §14-500 series" caveat.

Each of the six overlays **preserves the small-lot exception verbatim**: the same 1,600 sq ft trigger, the same 800 sq ft floor, the same provisos (verified at `14-520(4)(a)(.1)/(.2)/(.3)` against base `14-701(2)(b)[2]`). They raise the base minimum; they do not remove the exception. The blanket suppression therefore withheld a correct answer.

Suppression now keys on **unmodelled** overlays only (`get_unmodelled_overlays`): where we have recorded what an overlay does, we apply it; where we have not, we stay conservative and say so. The caveat's wording changed from asserting that an overlay "may modify or prohibit" division to stating that its terms are not modelled — which is the true claim.

### 4. Three transcription corrections ship in the same release

| correction | value | evidence |
|---|---|---|
| RSA-5 base minimum lot area | 1,440 → **960** | Table 14-701-1, `14-701(2)(b)[11]#table1`, p.951; verified at the printed page independently of the parser |
| RM-1 small-lot provision (absent) | trigger **1,920**, floor **960**, 75% adjacency, 1,000 sq ft | `14-701(2)(c)[1]` verbatim |
| Industrial FAR (absent, 5 districts) | **500%** for IRMX, ICMX, I-1, I-2, I-3 | Table 14-701-4, `14-701(4)(a)[5](.b)#table1`, p.954 |

**Atomicity is the safety property.** The RSA-5 base flip to 960 and the six `overlay_standard` rows ship in one commit. A deploy carrying 960 without the overlay layer is precisely the 54,376-parcel false-positive window this ADR exists to close.

## Consequences

**Verdicts move.** Outside the six overlays, 58,540 RSA-5 parcels flip from non-conforming to conforming and 68,280 gain subdivision capacity. Inside them, **nothing moves** — the effective minimum resolves to 1,440, identical to what v8 stored, so the comparison is between equal values. That zero is a property of the design, not an assertion about it.

No correction in v9 makes any parcel *less* buildable. The release cannot introduce the false-positive class the audit warned about, given atomicity.

**A full phl recompute is required.** `VERDICT_VERSION` moves to v9; stored verdicts hold v8 values until recomputed. Scope to `market_code='phl'` — pgh, wlm, and hbg are untouched by every correction here.

**Recompute cost rises, and the benchmark decided how much.** Overlay resolution adds a per-parcel overlay lookup that v8 did not do. Measured (40-parcel `compute_verdict` samples, local): the live `ST_Intersects` cost **27.1 ms/parcel, 29% of `compute_verdict`**, taking a full phl recompute from 10.38 h to 15.30 h. Both GiST indexes already existed, so this was never a missing-index problem — it is the exact-intersection test against 193 polygons, paid 550,945 times.

Membership is therefore **materialized** into `parcel_overlay`, refreshed by the overlay ingest job (1,487,536 rows in 57 s, one spatial pass). The hot path becomes a b-tree lookup: **27.1 ms → 1.5 ms**, `assess_parcel` 30.6 ms → 2.15 ms, recompute 15.30 h → **11.70 h**. v9's own overhead is +1.13 h over the v8 baseline. The live join is retained as `parcel_overlay_divergence`, so the query being replaced verifies its replacement.

**This mattered more than a batch-job cost, because `get_or_compute_current_verdict` recomputes lazily on version mismatch** (`verdict/service.py:145`). Between deploy and recompute, every parcel view holding a v8 row pays a full `compute_verdict` on the request path — 95 ms unmitigated, 70 ms materialized. Rollout ordering is in `docs/runbook.md`.

**RM-1 is modelled at its base provision only.** §14-502(4)(c)(.2) (**/CTR** Center City) sets a different trigger (1,600), a different floor (800), and a hard two-lot cap that `SmallLotProvision` has no field to express. Modelling it needs a schema change and is out of scope. §14-533(3)(e)[1] (**/MIN**) modifies RM-1's *lot area per dwelling unit* — a different field, also out of scope.

**The suppression narrowing is correct but delivers little today, and that is worth stating.** Measured on a 3,000-parcel sample of RSA-5 lots at or above the 1,600 sq ft trigger: **not one** has only modelled overlays. `/NIS` (Narcotics Injection Sites) touches 2,825 of 3,000, and 1,817 touch overlays carrying the literal code `[N/A]` — sign controls, use permissions, FAR maps and similar, none of which bear on lot area or subdivision. So the caveat still fires almost everywhere, and small-lot division stays suppressed for parcels whose only obstacle is a siting overlay that says nothing about lot size.

Narrowing from "any overlay" to "any unmodelled overlay" is strictly more correct and is the right shape. The change that would actually unlock small-lot analysis is **classifying the 193 overlays by whether they touch dimensional standards at all**, so a narcotics-siting overlay stops suppressing a subdivision answer. That needs all 193 read against the code and is its own slice — recorded here as the direct follow-up rather than half-done inside v9.

**The overlay layer inherits its own data risks.** `zoning_overlay.last_synced_at` is NULL on all 193 rows, so the layer the effective standard depends on carries no freshness signal. Membership uses `ST_Intersects`, so a parcel touching an overlay boundary counts as inside — restrictive, therefore safe, but a recorded choice rather than an accident.

## Non-goals

Explicitly out of scope, to keep the change auditable:

- General overlay dimensional support beyond `min_lot_area_sqft`. The table shape generalises; the seeded content deliberately does not.
- Use-permission overlays.
- /CTR's RM-1 small-lot variant and /MIN's lot-area-per-unit modification.
- Markets other than `phl`.
- The 25 conditional cells the audit classified (intermediate-vs-corner occupancy, "if used" yards, use-conditional rear yards) — not errors, and candidates for disclosure rather than value changes.
- RMX-3's front/rear setbacks, which the audit could not resolve against Title 14 and which need the Quick Guide page.

## Corrections to the evidence base

The audit's §4 and §6 state *"19,435 of them clear the 1,920 trigger"* for RM-1. **19,435 is the ≥1,600 count; the ≥1,920 figure is 10,946** — two columns of one query transposed in the prose. The audit's conclusion is unaffected (the provision is missing; the fix is additive) but the figure is wrong by 1.8×. Recorded here rather than restated.

## Alternatives rejected

**Bare scalar at 960 with a documented caveat.** Trades 58,540 false negatives for 54,376 false positives at close to one-for-one, in the worse direction. Rejected on the measurement.

**Leave 1,440 and disclose.** Keeps 58,540 parcels wrong in the district the code itself calls the most common in the city, when the correct answer is knowable.

**A confidence qualifier on the field.** Expresses uncertainty we do not have — the standard is not uncertain, it is conditional, and the condition is in the data already.
