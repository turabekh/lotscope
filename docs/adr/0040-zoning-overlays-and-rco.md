# 40. Zoning overlays & RCO surfacing

Date: 2026-07-03

## Status

Accepted

Gates PRD-amendment-01 feature **A8** (Phase 5) — existing PRD §5.3 scope, never built. Replicates the historic-district overlay pattern (ADR-0028) for two new geometry layers and bumps the verdict to **v6**. Sibling of ADR-0041 (A7, same phase).

## Context

The biggest credibility hole for the developer persona is a "buildable by-right" verdict that silently misses a **zoning overlay** (NCO, /CTR, pedestrian/− controls) or the **RCO** (Registered Community Organization) whose sign-off a variance needs. A developer catches that omission in one phone call, and trust is gone. Both datasets are published by the City on the same ArcGIS transport we already use (OpenDataPhilly: `Zoning_RCO`, and the zoning-overlay layer alongside base districts), and the resolution + surfacing machinery already exists — this is the **historic-district feature (ADR-0028) applied to two more layers**, not new architecture.

We deliberately **do not model overlay dimensional overrides** in v1 (the amendment defers that to its own ADR). A8 is *surface-and-cite*: detect the overlay/RCO a parcel falls in, name it, and cite the Title 14 §14-500-series to check. That closes the credibility gap without pretending to compute modified standards we haven't encoded.

## Decision

**Replicate the historic-district vertical for `zoning_overlay` and `rco`: geometry table → ArcGIS loader → `ST_Intersects` resolution → info-grade risk flag → verdict (v6) + checklist, surface-and-cite only.**

### Data & ingestion

Two geometry tables mirroring `HistoricDistrict` (id, external_id unique, name, `geom_2272`, `geom_4326` with GiST indexes, standard mixins):
- `zoning_overlay(… code, name …)` — overlay district code + name.
- `rco(… name, primary_email/type optional …)` — RCO boundary + name.

Two ArcGIS loaders following the `loaders/zoning.py` template (`ArcGisClient.paginate`, GeoJSON → `geom_4326` → `ST_Transform` 2272, `upsert` on `external_id`), registered in `INGEST_JOBS` so they run under the existing 4am `ingest_all` sweep. Exact layer URLs are confirmed and pinned in `data-sources.md` at the loader slice (per our data-source convention).

### Resolution & surfacing

Parcel→overlay/RCO resolution uses **`ST_Intersects(layer.geom_2272, parcel.geom_2272)`** on the full parcel geometry (gated on `geom_2272 IS NOT NULL`) — the exact predicate historic/flood use. `ST_Intersects` (not centroid `ST_Contains`) is the deliberate, credibility-safe choice: A8 exists to *stop missing* overlays, so a parcel that touches an overlay boundary should surface it (the flag is informational and says "check §14-500"; over-surfacing costs a citation to read, under-surfacing costs trust).

Two new info-grade risk flags, produced in `risk/scoring.py` beside `_historic_flag` and assembled in `risk/service.py` (resolution SQL + signal builders + `_CHECKED_SOURCES` entries), severity **low** like `historic_district`:
- **`overlay_district`** — "Parcel is in overlay **X** — check Title 14 §14-500 series for modified standards," listing overlay name(s).
- **`rco`** — "RCO: **<name>** — community meeting required for variances."

Both flow into the verdict's `risk_flags` with **no `composition.py` change** (flags ride the existing `risk_flags` list) and into the checklist by adding `overlay_district` and `rco` to the existing `overlays` category `frozenset` in `checklist/logic.py`. The overlay citation lives in the **risk-flag detail**, not the pure buildability engine — keeping `buildability.py` a pure function of encoded standards (we haven't encoded overlay overrides, so putting an unmodeled overlay into buildability `reasons` would over-promise). This is a small, deliberate deviation from the amendment's "buildability reasons" wording, with the same user-visible outcome (dossier + checklist show the overlay + citation).

### Verdict version

`VERDICT_VERSION` → **`"v6"`** in `verdict/composition.py`. `get_or_compute_current_verdict` lazily recomputes any stale (`!= v6`) verdict on read; a full eager backfill runs via `make recompute-verdicts` on deploy (same playbook as v5/historic).

### Rollout (slices, each tested + committed)

1. This ADR.
2. **Data** — `ZoningOverlay` + `Rco` models (registered in `models.py`), two migrations off head (geospatial-table template), two ArcGIS loaders + `INGEST_JOBS` entries + `data-sources.md` rows. Loader tests mirror `test_historic_loader.py`.
3. **Verdict integration** — overlay/RCO signals + `_overlay_flag`/`_rco_flag` in `risk/`, resolution SQL, checklist `overlays` additions, `VERDICT_VERSION = v6`, recompute. Tests mirror historic risk/checklist tests. Frontend auto-renders (dossier reads `risk_flags` + checklist).

## Consequences

- **The credibility hole closes.** A by-right verdict now names the overlay and the RCO and cites where to verify, on the dossier and in the checklist, with zero new UI wiring.
- **v6 forces a recompute.** Every verdict is stale until recomputed; lazy-on-read + a deploy sweep close it, exactly as v5 did. No new verdict *field* — flags ride `risk_flags` — so the contract shape is unchanged.
- **Surface-and-cite, honestly bounded.** We add no dimensional modeling; the flags say "check §14-500," and `buildability.py` stays pure. Modeling overlay overrides is the named follow-up ADR.
- **`ST_Intersects` can over-surface** a parcel grazing an overlay edge; acceptable for an info flag whose job is to never miss. A precision pass (area-overlap threshold) is a possible refinement, noted.
- **Cost is two more layers on a proven rail** — no new transport, no new cron (rides `ingest_all`), one verdict-version bump. RCO/overlay standalone endpoints are optional and deferred (the dossier reads them from `risk_flags`).
