# ADR-0084 — Philadelphia vacancy derived from OPA land use, additively

**Status:** proposed · **Date:** 2026-08-24 · **Supersedes:** nothing · **Related:** ADR-0028 (batched recomputes), ADR-0057 (distress profiles)

## Context

`is_vacant` is the flag the vacant-land product is built on. It gates vacant-only search (`search/spatial.py:51`), the `vacant` distress factor (`distress/scoring.py:103`, weight 10), the vacant-only verdict recompute scope (`verdict/jobs.py:34`), and vacant assemblage neighbours (`assemblage/logic.py:100`).

For `hbg` and `pgh` it is derived from the assessor's land-use string via `derive_vacancy`. For `phl` it has only ever come from the city's Vacant Property Indicators layer, and nothing derives it — `VACANT_LAND_USES_BY_MARKET` registered `hbg` and `pgh` only.

Measured on production, 2026-08-24: **14,020 of 42,583** phl parcels whose OPA `land_use` starts `VACANT` carry no flag — 32.9%. The suffixed values are worse: `VACANT LAND - RESIDENTIAL` 1,731 of 2,242 (77%), `VACANT LAND - NON-RESIDENTIAL` 172 of 212 (81%). Handoff 0047 §5 recorded one of these (`2138 N FAIRHILL ST`) as a single miss; it is one instance of the class.

The two sources disagree in both directions. **9,150 phl parcels are flagged vacant that OPA does not call vacant land** — VPI is a per-parcel vacancy model, not a land-use lookup, and it sees things OPA's category does not.

## Decision

Register `phl` in `VACANT_LAND_USES_BY_MARKET` with the three OPA vacant land-use values, and derive vacancy for Philadelphia **additively**: `derive_phl_vacancy` sets `is_vacant = true` only where it is not already true, and **never writes `false`**.

This is the one place the Philadelphia implementation deliberately departs from `hbg`/`pgh`. Those markets have no VPI equivalent, so derivation is their sole source and writing `false` is correct. Philadelphia has an authoritative model that disagrees with OPA on 9,150 parcels; copying the other markets' pattern would un-flag every one of them. **VPI stays authoritative; OPA land use is additive evidence only.**

`derive_vacancy`'s existing improvement-value guard is retained unchanged: a parcel with `improvement_value >= $1,000` is not flagged however OPA categorises it. On production that correctly withholds the flag from **268** of the 14,020, leaving **13,752** that would flip.

The derivation runs as its own dataset, `opa_derived_vacancy`, registered after `vacancy` in the phl loader table so VPI lands first. It records its own freshness row, so its coverage is visible on the ops board rather than being folded into the VPI count.

## Consequences

**Not a verdict-methodology change, and it takes no `VERDICT_VERSION` bump.** `is_vacant` does not feed `risk_score` or `opportunity_score`; it reaches the verdict engine only as batch *scope*. The scoring rule "vacant → +10 distress" is unchanged and already live in `philly-distress-v2`. What changes is which parcels satisfy a rule that already exists — a data correction under this repo's standing distinction, and the same posture PR #168 took for the multi-party grantor fix.

**It does require a distress recompute.** `assess_parcel_distress` scores live on read, so the parcel detail surface is correct the moment the loader runs, but the stored `parcel_distress` table is what leads, saved-search matching, feed and spatial search filter on. Until the distress sweep runs, the newly-flagged parcels are correct on their own page and absent from every list. Philadelphia distress is ~4 minutes, so this is cheap.

**Lead lists will grow.** ~13,752 parcels gain +10 distress; some cross the default lead threshold of 30. That is the intended correction, but it is a visible change in who gets surfaced, and it should not land in the same window as an external user's first session without someone deciding it should.

**Confidence is recorded but then superseded.** `derive_vacancy` returns 0.5 (multi-signal) for these, since OPA always publishes an improvement value so the single-signal path never fires for phl. `recompute_vacancy_confidence` subsequently overwrites `vacancy_confidence` for every `is_vacant IS TRUE` parcel from the richer L&I signal set, so the derived value is a floor, not a final answer.

**A known asymmetry is accepted.** A parcel VPI calls vacant and OPA calls built stays vacant; a parcel OPA calls vacant land and VPI does not know about becomes vacant. Both sources can only add. Nothing in this decision can ever clear a stale flag, and no mechanism currently does. That is the same posture as before this change, on a larger set — worth naming so the next reader does not assume otherwise.

## Alternatives rejected

**Copy the `hbg`/`pgh` pattern verbatim.** Writes `false` from the land-use vocabulary and silently un-flags the 9,150 VPI-only parcels. This is the trap the additive rule exists to avoid.

**Weight OPA-derived vacancy below VPI in distress scoring.** Defensible, and it would honour the confidence distinction properly, but it *is* a methodology change to the distress profile and would need a profile version and its own packet. Deferred rather than dismissed.

**Leave it and pursue a better vacancy source.** Does not answer the question — VPI is already the better source, and it simply does not cover these parcels.
