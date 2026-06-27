# 3. Data model baseline and verdict contract

Date: 2026-06-27

## Status

Accepted

## Context

Build-order step 2 (`CLAUDE.md` §11) lands the relational baseline: `parcel`, `zoning_district`, `zoning_standard`, `sale`, `tax_status`, `li_event`, and `parcel_verdict`, with PostGIS geometry and the first Alembic migration. Several choices here are lasting (the geometry strategy, provenance, and especially the verdict representation), and one contradicts the PRD, so they are recorded here.

## Decision

**Module ownership.** Each table lives in its owning module's `models.py`: `parcel` → `parcels`, `zoning_district`/`zoning_standard` → `zoning`, `sale` → `valuation`, `tax_status`/`li_event` → `risk`, `parcel_verdict` → `verdict`. A thin `lotscope.models` aggregator imports them so Alembic sees one metadata; modules still collaborate only through services, never by importing each other's models.

**`parcel` is the spine.** Primary key is the OPA `parcel_number` (text). `pwd_parcel_id` and `brt_number` are nullable, indexed columns so OPA↔PWD↔RTT reconciliation (step 3) has a home without forcing a synthetic key now.

**Geometry / SRID.** Every spatial table carries both `geom_2272` (EPSG:2272, feet — analysis source of truth) and `geom_4326` (tiles), each with its own GiST index. Storing both avoids re-projecting on every tile read at the cost of maintaining two columns on write; ingestion derives 4326 from 2272.

**Cross-module references.** Child tables (`sale`, `tax_status`, `li_event`, `parcel_verdict`) carry a `parcel_number` foreign key to `parcel` with `ON DELETE CASCADE`, declared by table name only — no cross-module ORM `relationship()` navigations, preserving module boundaries. Joins are explicit in services.

**Provenance & freshness.** Ingested tables use an `IngestionMixin` (`source`, `last_synced_at`); derived rows use a `ProvenanceMixin` (`sources` JSONB list, `computed_at`). All tables carry `created_at`/`updated_at`. This satisfies the "provenance + computed-at on every derived datum" rule (§0.6).

**`zoning_standard` is reference data.** Dimensional Title 14 standards are keyed by `(code, code_version)` (unique) and never hardcoded in logic — the code is amendable, so versioned rows are looked up at resolution time.

**`parcel_verdict` is a regular table — deviation from the PRD.** PRD §8 describes a computed `parcel_verdict` *materialized view*. We implement it as a **table** written by the verdict engine. Rationale: a materialized view cannot carry per-field provenance, supports only all-or-nothing refresh, and cannot be recomputed on-demand for a single parcel — all of which §0.6 and §11.7 require. The verdict module owns this contract; further changes are ADR-level.

**Migrations.** The Alembic `env.py` runs async, renders geometry via GeoAlchemy2's `alembic_helpers`, and filters reflection to tables in our own metadata so the PostGIS image's bundled Tiger-geocoder tables are never touched. The baseline migration was generated against a real PostGIS instance and verified to upgrade and downgrade cleanly.

## Consequences

- The schema is a baseline, not final; columns will be added as engines are built. Additive changes are ordinary migrations.
- Storing dual-SRID geometry doubles geometry storage and write cost but keeps both analysis and tiles fast; acceptable for ~580k parcels.
- The verdict-as-table choice diverges from the PRD wording; the PRD should be updated to match, or this ADR superseded if a materialized view is ever chosen.
- Integration tests run against real PostGIS via testcontainers (schema, GiST indexes, geometry round-trip, FK cascade), marked `integration` so unit runs stay network-free.
