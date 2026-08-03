# ADR-0075 — Zoning standards distinguish "unregulated" from "not captured"

Status: accepted (2026-08-03)

Corrects an assumption in **ADR-0074** and fixes the root cause behind the checklist defect repaired the same day.

## Context

`zoning_standard` stored every dimensional field as a nullable number, so `NULL` carried two incompatible meanings: *the district imposes no such standard*, and *we have not captured the value*. Everything downstream read it as the second.

That conflation reached users. A CMX-4 parcel's checklist reported "Minimum lot area — not evaluated", implying missing information, when the district in fact sets no minimum lot area at all. ADR-0074 then treated a null height as `height_standard_missing`, a critical unknown blocking `high` confidence — and it was the single largest driver, 3.2 of the 4.4 percentage points demoted.

The provenance made this hard to see. Both `zoning_standard` and the "Title 14 corpus" derive from one document — the [Philadelphia Zoning Code Base Districts Quick Guide, February 2026](https://www.phila.gov/media/20260213170558/ZONING-QUICK-GUIDE_feb-2026.pdf) — which the seed already cites. `docs/data-sources.md` described the nulls as "fields not yet confirmed", which is true for some districts and wrong for others.

Reading the guide's dimensional tables directly settles which is which:

| district group | guide shows | meaning |
|---|---|---|
| CMX-3 / CMX-4 / CMX-5 | no lot-minimum rows, **no height row**; FAR 500%–1200% | height and lot minimums genuinely unregulated; bulk governed by floor-area ratio and the §14-702 bonuses |
| CMX-2 / CMX-2.5 / IRMX / ICMX | no lot-minimum rows; heights stated (38/55/60/60 ft) | lot minimums unregulated |
| RMX-1 / RMX-2 / RMX-3 | `Min. Lot Width  N/A  N/A  N/A` | explicitly none |
| CA-1 / CA-2 | lot area and height stated; no lot-width row | width unregulated; district uses minimum street frontage instead |
| I-1 / I-2 / I-3 | "60 ft. where abutting a Residential or SP-PO district; **otherwise no limit**" | regulated, but conditional on neighbours — not one number |
| RM-2 / RM-3 / RM-4 | row reads "Max. Height / FAR", values 70% / 150% / 350% of lot area | height expressed as a ratio, not a fixed figure |
| CMX-1 | "Occupied Area, Building Dimensions, and Height are based on the requirements of adjacent residential zoning districts" | inherited from neighbours; varies by location |

Two of those are not "no standard" and not "unknown" either. They are **regulated but irreducible to a single value**, and calling them missing data would be as wrong as calling them unregulated.

## Decision

`zoning_standard` gains a `field_dispositions` JSONB column mapping a field name to `{disposition, note?}`, where disposition is `unregulated` or `conditional`. A field with a value needs no entry; a field with neither a value nor an entry keeps today's meaning — not captured.

This yields three distinct user-facing outcomes per check:

- **unregulated** → `not_applicable`, *"CMX-4 sets no minimum lot area."* A real answer, not an absence. An optional note says what governs instead, so *"CMX-4 sets no maximum height"* is never read as unlimited: it continues *"— building size is governed by the floor-area ratio and the bonus provisions instead."*
- **conditional** → `not_evaluated`, stating the actual rule: *"In I-1 this standard is 60 ft. where the lot abuts a Residential or SP-PO district; otherwise no height limit, so it cannot be reduced to a single figure and is not modelled."*
- **neither** → unchanged: *"The … standard on file records no maximum height, so this check was not evaluated."*

ADR-0074's `height_standard_missing` critical unknown now fires only when the height is genuinely uncaptured or conditional. An unregulated height is not an unknown — there is nothing to know.

Dispositions are recorded **only for districts read directly from the guide**. Everything else keeps the conservative default. Writing a false "no standard applies" would be worse than the vagueness it replaces, so absence of evidence stays absence of evidence.

## Consequences

On the reported CMX-4 parcel, three rows change from "not evaluated" to answered, and its buildability confidence rises from `medium` to `high` — correctly, since the only blocking unknown was a height the district does not set.

Across 1,200 spread-sampled Philadelphia parcels, measured through the real code path: `high` **95.6% → 96.4%**, and `height_standard_missing` **38 → 26 parcels (3.2% → 2.2%)**. The residue is districts whose height is conditional (RM-2/3/4, I-1/2/3) or genuinely uncaptured (the SP-\* family), which is the honest result rather than a number driven to zero.

This needs a migration and a re-seed (`make seed`) but **no recompute** — buildability is computed on read, per ADR-0074, so `VERDICT_VERSION` stays `v8`.

**The deeper lesson is about provenance, not zoning.** A summary document was treated as if it were the code, and its omissions were read as our gaps. The same mistake is latent wherever a null is loaded from a secondary source: `min_parking_spaces` is null for every district because the Quick Guide carries no parking table at all — those live in Chapter 14-800, which nothing in this repository has ever read. Parking is therefore honestly "not captured", and unlike height it must not be given a disposition until the chapter is ingested.
