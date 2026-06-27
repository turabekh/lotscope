# 5. Postgres trigram/full-text search instead of Elasticsearch

Date: 2026-06-27

## Status

Accepted (supersedes the Elasticsearch choice in `CLAUDE.md` §2 for this phase)

## Context

`CLAUDE.md` §2 named Elasticsearch as the search store, and build-order step 4 calls for address/owner/parcel search. The actual requirement is modest: typo-tolerant address search, owner-name search, and parcel-number lookup over **~580k parcels in a single city**. Elasticsearch is a separate JVM service (~512MB+ RAM), carries real operational burden, and requires a **second copy of the parcel data** kept in sync with Postgres — a moving part and a class of consistency bugs we do not need at this scale early on.

## Decision

Use **PostgreSQL** for search, which we already run as the primary datastore:

- **`pg_trgm`** (trigram) GIN indexes on `parcel.address` and `parcel.owner` for fuzzy, typo-tolerant, substring matching ranked by `similarity()`.
- Parcel-number lookup by exact (normalized) match and prefix.
- Results are ranked (exact parcel match first, then trigram similarity) and paginated.

The `search` module exposes its query through a service interface, so the backend can be swapped to Elasticsearch or a dedicated search engine later (e.g. for multi-city scale or advanced relevance) without changing callers. Elasticsearch is removed from `docker-compose`, the `ELASTICSEARCH_URL` setting is dropped, and `CLAUDE.md`/README are updated in this change.

## Consequences

- One datastore, no index-sync pipeline, transactional consistency between search and parcel data, and one fewer service to operate.
- Sub-100ms search at this scale with trigram GIN indexes; the extension and indexes ship as a migration.
- Relevance ranking and typeahead are less sophisticated than Elasticsearch out of the box. If multi-city expansion or marquee search features demand it, revisit and supersede this ADR; the service interface keeps that swap contained.
- This is a deliberate deviation from the originally specified stack, recorded here and reflected in `CLAUDE.md` §2.
