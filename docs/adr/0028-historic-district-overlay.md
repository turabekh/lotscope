# 28. Historic-district overlay signal

Date: 2026-06-30

## Status

Accepted

## Context

PRD §5.3 (overlay & RCO impacts) and §5.5 (due diligence) call for surfacing historic-review constraints: a parcel inside a Philadelphia Register historic district needs Historical Commission review for exterior alterations, demolition, and new construction — real time/cost friction for a developer. The City publishes **`historicdistricts_local`** on Carto (17 local districts, polygon `the_geom`, with `name` and `designated` date) — the same Carto SQL API already used for OPA/PWD/RTT.

The natural home for this signal is the risk engine (like the flood overlay): intersect the parcel with the district polygons and emit a flag. But adding a risk flag changes verdict output and forces a `VERDICT_VERSION` bump + a full ~550k recompute. The verdict version had already been bumped three times in the same session (v2→v3→v4, with the v4 recompute still in flight), so another bump would thrash the recompute again.

## Decision

**Ship historic-district detection as a standalone per-parcel overlay signal now; defer folding it into the verdict risk flag / DD checklist until the next verdict-contract change.**

- New `historic_district` table (Carto loader registered as the `historic` ingest job; geometry in 2272 + 4326 with GiST indexes; idempotent upsert on `objectid`).
- `historic` module: `get_parcel_historic` does `ST_Intersects(parcel.geom_2272, historic_district.geom_2272)` and returns whether the parcel is in a district, the district name, the designation date, and an informational review note.
- `GET /parcels/{id}/historic` + a dossier panel surface it. No verdict change, no version bump — the in-flight recompute is undisturbed.

This mirrors the standalone-signal pattern already used for over-assessment (ADR-0026 era) and subdivision: a per-parcel signal with its own endpoint and panel, composed from existing engines/data, not routed through the verdict's `risk_score`.

## Consequences

- **The signal is visible immediately** (panel + endpoint) without a recompute, respecting the running v4 sweep. ~8k parcels fall inside a historic district.
- **It does not yet influence `opportunity_score` or appear in the DD checklist.** Promoting it to a `risk` flag (`historic_district`, with a new "Historic & overlays" checklist category) is a clean follow-up to **batch with the next verdict-contract change**, so verdict-affecting additions are recomputed together rather than one bump at a time. Recorded here so the follow-up isn't lost.
- Informational and cited (`historicdistricts_local`), per §13 — it states that Historical Commission review is required, not that a project is barred.
- The `historic_district` layer is reusable for map overlays and future overlay logic; it owns no domain truth.

## Follow-up (2026-06-30): folded into the verdict

The deferred promotion is now done, batched as the single verdict-contract change for `VERDICT_VERSION` v4→v5 (the v4 recompute had completed, so no thrash). The risk engine emits a `historic_district` flag (severity `low` — Historical Commission review is process friction, not a development bar; same tier as the landlocked flag) sourced from `historicdistricts_local`, queried via `ST_Intersects` against `historic_district.geom_2272` like the flood overlay. A new "Historic & overlays" DD-checklist category surfaces it (low → `info`). The standalone `GET /parcels/{id}/historic` endpoint and panel stay — they carry richer detail (designation date, full review note) than the verdict flag. All ~8k in-district parcels now reflect the flag after the v5 recompute.
