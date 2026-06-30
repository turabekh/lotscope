# 27. Street-centerline ingest and street-access (landlocked) flag

Date: 2026-06-30

## Status

Accepted

## Context

PRD §5.5 lists **Access / easements** (Differentiator) under Risk & Due Diligence: easements, rights-of-way, and landlocked detection. A landlocked parcel — one with no frontage on a public street — cannot be developed by-right and is a material deal-killer, yet none of the data already ingested (OPA, PWD parcels, RTT, L&I, tax, vacancy, zoning, flood, neighborhoods) describes the street network. Recorded easements require deed/plat OCR (separate track, ADR-0026). The tractable, autonomous slice is **landlocked detection from the street network plus PWD parcel geometry**, which needs one new data source.

The City publishes **Street Centerline** on ArcGIS Hub (`Street_Centerline` FeatureServer, ~41k LineString segments) — the same access pattern as the neighborhoods loader.

A centerline runs down the middle of the right-of-way, not along the parcel frontage, so "abuts a street" cannot be tested by touch. It must be approximated by distance: a parcel fronts a street when a centerline lies within roughly half a right-of-way width of the parcel boundary.

## Decision

**Ingest street centerlines as a reference geometry layer and derive a conservative, low-severity `no_street_access` risk flag from a distance test; do not attempt easement extraction here.**

- New `street_centerline` table (`streets` module), populated by an ArcGIS loader registered as the `streets` ingest job — mirrors the neighborhoods loader (idempotent upsert keyed on `seg_id`, geometry stored in both 2272 and 4326 with GiST indexes, freshness recorded).
- Access is computed **on demand inside the risk engine** (like the flood check), not precomputed onto the parcel: a parcel with geometry is flagged when **no** centerline lies within `STREET_ACCESS_MAX_FT` of it, via `ST_DWithin(parcel.geom_2272, street.geom_2272, max)` against the GiST index. No new parcel column or batch job.
- The flag is **`no_street_access`, severity `low`**, sourced to `street_centerline`, and worded as a signal to verify ("no street frontage detected within N ft — possible landlocked lot; confirm access/easements"), not a determination. It composes into the Parcel Verdict's risk like every other flag and surfaces as a new **Access** category in the due-diligence checklist.

## Consequences

- **Precision over recall, by design.** `STREET_ACCESS_MAX_FT` is set generously so that parcels fronting wide rights-of-way (e.g. Roosevelt Blvd) are not falsely flagged; the cost is that a genuinely landlocked interior lot whose nearest street is just inside the threshold will not be flagged. This matches the §13 "no false precision" stance: a low-severity, verify-this signal, not a hard landlocked verdict. The threshold is a named constant to tune as we validate against known cases.
- **Adding the flag changes verdict output**, so `VERDICT_VERSION` bumps (v3 → v4) and persisted verdicts recompute (on demand per view, batch via `make recompute-verdicts`).
- **Recorded easements and rights-of-way are still not covered** — that remains a deed/plat OCR problem (ADR-0026). This ADR covers landlocked/no-frontage detection only.
- The `streets` layer is reusable beyond this flag (frontage measurement, address-range geocoding, future map context); it is reference geometry and owns no domain truth.
- The distance heuristic is a v1; refinements (per-segment right-of-way width, frontage along the parcel's street-facing edge only, corner-lot handling) are follow-ups.
