# ADR-0058 — Materialized resolved zoning district on the parcel row

Status: proposed (2026-07-09)

## Context
Markets whose upstream extract carries no per-parcel zoning attribute leave `parcel.base_zoning_code` empty. Harrisburg is the whole-market case: the Dauphin GIS extract exposes no zoning code, so every `hbg` parcel has `base_zoning_code = ''` while its district is knowable spatially from `zoning_district` (ADR-0056). Philadelphia has ~1,100 attribute-missing orphans in the same shape.

The Harrisburg field-test batch (Slice 1, `fix/hbg-resolved-district`) unified the *dossier-side* surfaces on the verdict's resolved district, computed live in `parcels/service.get_parcel_detail` via `resolve_district()`. That choice was deliberately **reader-side only** — resolution was recomputed per request and never persisted, to keep the derived district out of the raw attribute column and preserve its provenance.

The residual gap: every surface that cannot call the live resolver still read the raw attribute and rendered "No zoning" / "—" for `hbg` — the nine list/card DTOs (leads, deals, watchlist, owner portfolio, saved-search matches, assemblage neighbors and Top Plays, spatial search, home feed), the Ask-the-Parcel retrieval pinning, and the `parcels_mvt` vector tile (hence the map click popup). List DTOs would need N per-row spatial lookups; the tile is a Postgres function where a per-tile spatial join would regress the map-performance work. Reader-side-only cannot reach these.

## Decision
Materialize the resolved district as a provenanced derived field on the parcel:

- Two nullable columns: `parcel.resolved_zoning_code` and `parcel.resolved_zoning_source` (currently always `'spatial'`), per the golden rule that every derived datum carries provenance.
- `zoning.service.refresh_resolved_districts(market)` runs the ADR-0056 spatial resolution as a set-based `UPDATE`, populating the columns **only** where `base_zoning_code` is empty/NULL. It is idempotent (writes only changed rows) and is invoked at the tail of the Harrisburg zoning ingestion (after both parcels and districts are loaded), plus a one-time backfill in the migration.
- Every display reader coalesces: `coalesce(nullif(base_zoning_code, ''), resolved_zoning_code)`, keeping the `base_zoning_code` output alias so DTO mappers are unchanged. The `parcels_mvt` function emits the same coalesced value, so the map popup resolves with no frontend change. Ask-the-Parcel pins district documents on the resolved code.
- Filter and matching logic (zoning-code search, assemblage same-zoning) continues to read the raw attribute; changing filter semantics is out of scope and noted as a follow-up.

This reverses the reader-side-only stance of field-test Slice 1 for the *derived value's storage*, while keeping its consistency rule (one district story per parcel) intact.

## Consequences
- `VERDICT_VERSION` is unaffected — the verdict already resolved the district; this materializes the same value for other readers. No recompute.
- Philadelphia parcels with a present attribute are byte-identical (the coalesce is a no-op; golden parcels asserted unchanged). The ~1,100 attribute-missing `phl` orphans now show their spatially-resolved district in list and tile views too — consistent with the dossier, which already resolved them live. This is a consistency gain, not a regression, and is reported honestly rather than hidden.
- The resolved district can go stale if district polygons change without a zoning re-ingest; the refresh re-runs on every Harrisburg zoning job, which is the cadence at which districts change.

## Follow-up — filter parity (2026-07-09)
The user-facing zoning-code *filter* predicates now coalesce on the same expression, so attribute-missing parcels are filterable by their resolved district, not just displayable. A shared `core.sql.resolved_zoning_code_sql(alias, resolved_alias)` produces the exact display coalesce string and is reused by both sides. Predicates updated: saved-search matching `zoning_codes`, spatial area-search `zoning_codes` and `zoning_use_classes` prefix, and assemblage Top Plays `zoning` prefix (the assemblage count query gains the `parcel` join it needs to reach `resolved_zoning_code`). phl parcels with a present attribute stay byte-identical; phl orphans become filterable, matching their display — the same consistency gain as above. `VERDICT_VERSION` is again unaffected; these are read-path filters, not verdict inputs.

Still deferred (verdict-adjacent, not filters): the assemblage `same_zoning` adjacency flag, the ZBA variance-outlook district match (`zba/service.py`), and the valuation comps use-class segmentation (`valuation/service.py` + `avm.land_use_class`). These feed the Parcel Verdict, so switching them to the resolved code needs a recompute and belongs in a verdict slice, not this read-path change.
