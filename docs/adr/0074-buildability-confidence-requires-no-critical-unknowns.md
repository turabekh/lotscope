# ADR-0074 — High buildability confidence requires no unresolved critical unknowns

Status: accepted (2026-08-03)

Implements the LR-B004 invariant tracked as **LR-B-016**. Sits alongside **ADR-0072** (screening must not outrun its evidence), which applied the same principle to the valuation half of the verdict.

## Context

`_confidence()` in `zoning/buildability.py` read exactly two inputs — is the lot area known, is the lot width known — and returned `high` when both were present. Nothing in any code path inspected an unresolved unknown before assigning that label, so LR-B004's requirement that a high confidence label cannot coexist with unresolved critical unknowns was unenforced by construction rather than merely untested.

Measured against the Philadelphia parcel table, **545,388 of 550,945 parcels — 99.0% — satisfied that two-input test.** `high` was not occasionally wrong; it was the default state of the city and therefore carried no information. A parcel whose district was asserted by a single unconfirmed source, or whose footprint was a lot-coverage guess, or whose district records no by-right height, presented exactly like a fully resolved one.

The pilot markets were already protected: Pittsburgh, Wilmington, and Harrisburg all carry `provisional` standards, which force `low`. The exposure was Philadelphia alone.

### Which unknowns are critical

Two candidate rules were measured before choosing.

**Zoning overlays were considered and deliberately excluded from this decision.** 96.4% of sampled Philadelphia parcels intersect at least one overlay, but 90% of that is `/NIS Narcotics Injection Sites Overlay District`, which restricts a use that has no bearing on the development envelope of a vacant lot. Blocking `high` on overlay membership would demote nearly the whole city and replace an uninformative `high` with an equally uninformative `medium`. Some overlays genuinely do constrain the envelope — `/AHC` and `/HHC` impose height limits, `/CTR` imposes Center City controls, `/WWO` and steep-slope areas impose environmental limits — but separating those from the use-specific and administrative ones requires Title 14 §14-500, which is not in the document corpus. Classifying 43 overlay codes from parametric memory would violate §9 of `CLAUDE.md`. Overlays are therefore deferred to a later slice that ingests the chapter first.

**District resolution method was replaced by district corroboration.** The initial proposal treated `opa_attribute` as the weaker method. Measured on 3,000 sampled parcels holding both a geometry and an OPA zoning code, the spatial lookup and the OPA attribute agreed on 2,998, disagreed on 2, and never failed to match — so neither method is weak in itself. What is actually informative is whether a second source confirms the first. That is free to compute, because both values are already loaded by the existing query.

## Decision

Confidence is derived in two stages, in a pure module `zoning/confidence.py`:

1. A base tier from lot dimensions, unchanged from previous behaviour — both known is `high`, one known is `medium`, neither is `low`.
2. A set of **critical unknowns**, any one of which blocks `high`:

| unknown | meaning |
|---|---|
| `dimensions_incomplete` | lot area or width is missing |
| `district_uncorroborated` | no second source confirms the district |
| `conformance_unresolved` | conformance with district minimums could not be determined |
| `footprint_not_setback_derived` | the buildable footprint is a lot-coverage estimate, not a setback calculation |
| `height_standard_missing` | the district records no by-right height |
| `permitted_uses_missing` | the district records no by-right uses |
| `standards_provisional` | market standards are provisional pending local review |

`standards_provisional` forces `low`, preserving the pre-existing pilot-market rule. Every other unknown caps confidence at `medium`. Unknowns never promote a result and never demote below the dimensional base tier, so the `medium`/`low` boundary is untouched by this change — the decision is deliberately confined to the invariant LR-B004 states.

Each unknown carries a user-facing reason string that is appended to the buildability reasons, so a parcel that is not `high` says why.

## Consequences

Measured through the real code path on 1,200 spread-sampled Philadelphia parcels: **95.6% `high`, 3.5% `medium`, 0.9% `low`** — 4.4% demoted, against 4.2% projected from the parcel table directly. The dominant cause is `height_standard_missing` (3.2%), which reflects that 20 of the 39 Philadelphia districts record no by-right height in the current standards table.

The invariant now holds by construction and is enforced by a parametrised test asserting that every declared critical unknown blocks `high`, so a new unknown cannot be added without inheriting the guarantee.

**`high` still describes 95.6% of Philadelphia, and this ADR does not claim otherwise.** For a rowhouse city with a good parcel layer that is substantially honest — the dimensional and standards data really are complete for most lots. The label's discriminating power will improve when overlays are classified and when the missing height standards are filled, both of which are follow-on work. What this decision buys is that the 4.4% which should never have read `high` no longer do, and that the mechanism for demoting them is a single reviewed list rather than an implicit consequence of which two columns happened to be consulted.

**No migration, no recompute, and no verdict-contract change.** LR-B-016 was recorded as verdict-affecting work needing a batch recompute. It is not: `parcel_verdict` has no buildability-confidence column, and the buildability entries in the stored `field_trust` blob carry `confidence: null`. Buildability confidence is computed on read by `assess_parcel` and reaches users through the buildability endpoint and the LR-B001 checklist. The new labels therefore take effect on deploy, and `VERDICT_VERSION` stays at `v8`.

That absence is itself a gap worth naming: the confidence a user is shown for the by-right read is not recorded with the verdict, so there is no stored provenance for it and no way to audit after the fact what confidence a parcel displayed on a given date. Persisting it belongs with the overlay slice, not here, because doing it now would mean a migration and a full recompute for a value this decision does not change for 95.6% of parcels.

## Addendum (2026-08-03) — surfacing

When this ADR was accepted, nothing in the codebase read `BuildabilityResult.confidence`: it was computed, returned on the schema, and consumed by nobody, so the invariant was correct but invisible. The label is now carried on the parcel checklist response — which is already computed per request from zoning and already reaches the dossier — and rendered on the Buildability card as a chip, with the unresolved inputs listed inline beneath the by-right qualifier rather than hidden in a tooltip.

The checklist rather than the verdict carries it deliberately. The verdict is a stored row with no confidence column; adding a read-time field there would mean either a migration and a recompute, or a spatial district query on every verdict read. The checklist is already request-time and already zoning-derived, so it costs one additional district resolution on a path that performs several queries regardless.

Both halves are asserted where a user would see them: a component test requires the chip and the reason list to be visible outside any tooltip, and an end-to-end test opens a real dossier in a browser and reads the label off the rendered page.
