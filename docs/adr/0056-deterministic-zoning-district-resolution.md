# ADR-0056 — Deterministic zoning-district resolution (majority-area tie-break)

Status: proposed (2026-07-06)

## Context
`zoning/service.py` resolves a parcel's base zoning district spatially by testing whether the parcel centroid is contained in a `zoning_district` polygon, taking the first match:

```sql
SELECT zd.code FROM parcel p
JOIN zoning_district zd ON zd.market_code = p.market_code
  AND ST_Contains(zd.geom_local, ST_Centroid(p.geom_local))
WHERE p.parcel_number = :parcel_number LIMIT 1
```

The `zoning_district` layers are not strictly planar-partitioned: some markets carry polygons that overlap in area. A parcel centroid can therefore satisfy `ST_Contains` for more than one district, and `LIMIT 1` with no `ORDER BY` returns an arbitrary row. The resolved district — and every downstream zoning answer (by-right units, height, setbacks, "standards not loaded", buildability score) — is nondeterministic for those parcels.

Measured multi-containment (centroid inside ≥2 districts):

| Market | Parcels | Notes |
|---|---|---|
| pgh | 15,769 (~11%) | 7,597 involve overlay-type P/H co-mapped with base; 8,172 pure base-district overlap (e.g. `R1D-H + R1D-M`, `R2-L + RM-M`) |
| phl | 5,168 | pre-existing, latent since launch |
| hbg | 0 | layer is planar |

Surfaced during Wave-1 Slice 5c (the Pittsburgh 25-parcel zoning verification packet): sampled parcels resolved to a different district than the polygon they were drawn from, run to run. A packet certifying "our district matches the city map" is meaningless while resolution is unstable.

Two distinct upstream causes are folded into this symptom: (a) overlay-type districts (Hillside `H`, Parks `P`, and specialized `RIV-*`/`UI`/`UPR-*`) co-mapped into the base layer, and (b) genuine base-district polygon overlaps and boundary slivers. This ADR addresses only the *resolution determinism*. Overlay **stacking** (an overlay adding constraints on top of the underlying base district) and reclassifying overlay-type codes out of `zoning_district` are separate, larger concerns tracked as follow-ups.

## Decision
Keep centroid containment as the membership test, but make the tie-break deterministic by **majority overlap area**: among the districts whose polygon contains the parcel centroid, resolve to the one whose polygon overlaps the parcel the most.

```sql
SELECT zd.code FROM parcel p
JOIN zoning_district zd ON zd.market_code = p.market_code
  AND ST_Contains(zd.geom_local, ST_Centroid(p.geom_local))
WHERE p.parcel_number = :parcel_number
ORDER BY ST_Area(ST_Intersection(ST_MakeValid(zd.geom_local), ST_MakeValid(p.geom_local))) DESC, zd.code ASC
LIMIT 1
```

`ST_MakeValid` wraps both operands because `ST_Intersection` raises `TopologyException` on self-intersecting input, and the Pittsburgh layers carry invalid polygons. The old centroid-only query never computed an intersection, so it tolerated invalid geometry silently; introducing area ranking into the hot path makes validity a correctness precondition. Guarding at the query keeps `assess_parcel` from regressing an invalid-geometry parcel from "returns a district" to "raises".

- The `WHERE` clause is unchanged, so every parcel whose centroid is in exactly one district resolves **byte-identically** to before. Only the ambiguous set changes, and only from arbitrary to deterministic.
- `zd.code ASC` is a final stable tie-break for the degenerate case of equal overlap area (e.g. duplicated geometry), so the result is total-ordered and reproducible.
- `district_method` stays `"spatial"`; the semantics ("the district the parcel sits in") are preserved, now resolved by dominant area rather than row order.

The alternative — full-parcel majority-area with `ST_Intersects` replacing centroid containment — was rejected for this slice: it changes resolution for *every* boundary-straddling parcel, not just the ambiguous ones, widening the regression surface for no correctness gain on the parcels that were already unambiguous.

## Consequences
- **pgh:** 15,769 parcels move from nondeterministic to a stable, majority-area district; parcels mostly in an authored base district with a corner clipping an overlay-type polygon (P/H) now resolve to the base district and get real standards instead of a coin-flip "standards not loaded".
- **phl:** 5,168 previously-nondeterministic parcels become stable. Stored v8 verdicts were computed against whatever the old query happened to return; on-view buildability may now differ from a stored verdict for some of these until the next recompute. No forced recompute in this slice — flagged for the next scheduled batch.
- **hbg:** zero multi-containment parcels; resolution is unchanged. Two-market regression (phl + hbg goldens) runs on this shared-code change.
- **Performance:** `ST_Intersection` is evaluated only across the (usually one) rows already passing centroid containment, not the whole layer, so per-parcel on-view cost is negligible. Batch verdict recompute (Slice 7) pays it once per parcel; acceptable at single-city scale.
- Overlay stacking and overlay-vs-base reclassification remain open, tracked separately; this ADR does not encode overlay constraints.
