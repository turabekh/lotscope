# ADR-0085 — Philadelphia public ownership derived from the OPA owner name

**Status:** proposed, **explicitly interim** · **Date:** 2026-08-24 · **Related:** ADR-0084, ADR-0028

## Context

`is_city_owned` does real work. `score_distress` returns `score=0, tier="none"` immediately for a city-owned parcel (`distress/scoring.py:61`); `savedsearch/matching.py:38`, `distress/service.py:158,175` and `watchlist/service.py:52` each exclude them; `risk/scoring.py:361` adds a `public_ownership` flag reading "acquisition is through the public disposition process, not a private sale"; `assemblage/logic.py` treats them as acquisition candidates and as a "clear path".

It is set by loaders for `pgh` (8.7% of parcels), `hbg` (4.6%) and `wlm` (0.12%). For `phl` it is set for **1 parcel of 588,606**, so every one of those behaviours is inert in the flagship market.

Measured 2026-08-24: **9,175 publicly-owned Philadelphia parcels sit in lead range** (`score >= 30`, the default in `api/leads.py:24`). That number rose from 7,539 the same day, because ADR-0084's vacancy correction flagged 1,683 City and Land Bank parcels as vacant and each gained the +10 vacant distress factor. **A correct fix made this defect measurably worse**, which is what moved it to the front of the queue.

**The authoritative source does not exist upstream.** Searched and recorded in `docs/data-sources.md`: six candidate Carto relations absent and the catalog un-enumerable; of three ArcGIS candidates, `PublicOwnership_Public` is an empty May-2019 snapshot and `MDOLandBank` and `LandDispositionStatus` carry no parcel key. `pgh` and `wlm` each bind to a parcel-keyed authoritative layer. Philadelphia publishes no equivalent in either place.

## Decision

Derive `is_city_owned` for `phl` from the OPA owner name, as an explicitly interim measure, until a parcel-keyed source is found.

`is_public_owner` matches three prefixes (`CITY OF PHILA`, `PHILADELPHIA HOUSING`, `PHDC`) and two fragments (`LAND BANK`, `REDEVELOPMENT AUTHORITY`), after excluding any owner containing `LLC`.

**The prefix/fragment split is not cosmetic.** `PHILADELPHIA HOUSING` must anchor, or `HLP PHILADELPHIA HOUSING` — a private holder — matches. `LAND BANK` must not anchor, or `PHILADELPHIA LAND BANK` is the only form caught and the upstream misspelling `PHIADELPHIA LAND BANK` is missed. The `LLC` exclusion is what separates `PHILADELPHIA HOUSING AUTHORITY` from `PHILADELPHIA HOUSING GROUP LLC`, which the anchor alone cannot.

Measured against production: the naive pattern set matched 13,434 parcels; the rule above matches **13,426**, excluding exactly the three private owners found by inspection — `WEST PHILADELPHIA HOUSING GROUP LLC` (6), `PHILADELPHIA HOUSING GROUP LLC` (1), `HLP PHILADELPHIA HOUSING` (1). Upstream misspellings (`CITY OF PHILADEELPHIA`, `CITY OF PHILADEPLPHIA`, `CITY OF PHILADELPIA`, `PHIADELPHIA LAND BANK`) are retained as public, which they are.

**The derivation writes both `true` and `false`, and is scoped to `phl` in both the query and the UPDATE.** Ownership, unlike vacancy, has one truth — the owner of record — so a parcel whose owner is no longer public should lose the flag. The market scope is what makes writing `false` safe: `pgh`, `hbg` and `wlm` bind to authoritative sources this derivation must never touch, and there is a test asserting it does not.

A NULL flag is left NULL rather than written to `false`. Every consumer reads it through `coalesce(is_city_owned, false)`, so the two are equivalent, and writing `false` across ~575,000 rows would be churn with no semantic effect.

## Consequences

**Roughly 9,175 parcels leave the lead lists**, along with their saved-search matches, watchlist eligibility and export rows. That is the correction. It is a large visible movement in who the product surfaces, and it should be run deliberately rather than as a side effect of a nightly.

**`risk_score` moves**, because the `public_ownership` flag becomes reachable. This is v11 methodology receiving correct input, not a methodology change, so it takes **no `VERDICT_VERSION` bump** — the same posture as PR #168 and ADR-0084. It does require a **targeted verdict recompute of the affected parcels**, since lazy recompute fires only on version mismatch and these would otherwise stay stamped `v11` while disagreeing with the engine. Derived AI artifacts for those parcels must be purged in the same step, per the cache rule in `CLAUDE.md` §12.

**A heuristic now stands where a fact belongs, and it is visible.** It runs as its own dataset, `opa_derived_public_ownership`, so its row count is on the ops board rather than folded into another loader's.

**The error direction is deliberately conservative.** A false positive withholds a genuinely private parcel from lead lists — a missed opportunity. A false negative leaves a public parcel in them — today's behaviour. Given the harm being fixed is the product directing outreach at the City, erring toward withholding is the right way to be wrong.

**This must be revisited if an authoritative source is adopted.** OPA ownership is known to be stale on some parcels — handoff 0047 §5 records `3862 ASPEN ST` still naming a 2025 seller. A Land Bank parcel whose OPA record still shows the previous private owner would be written `false` by this derivation, overwriting an authoritative flag. The moment a real source exists, this derivation must become additive or be retired, exactly as ADR-0084's vacancy derivation is additive for the same class of reason.

## Alternatives rejected

**Wait for the authoritative source.** It does not exist in either place checked, has no owner and no date, and 9,175 parcels are in lead lists now.

**Match on tax exemption instead of owner name.** `exempt_land` / `exempt_building` identify all exempt owners — churches, universities, hospitals — not public ones. Far more false positives, and they would be silently withheld from lead lists.

**Address-match `MDOLandBank`.** It is a genuine city dataset, but keyless; address reconciliation against 588,606 parcels is its own project with its own error surface, and CLAUDE.md §17 already names key reconciliation as a first-class hazard.
