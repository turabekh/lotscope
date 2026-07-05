# 51. Market entity and canonical parcel key

Date: 2026-07-05

## Status

Accepted

Implements PRD Amendment-02 workstream **B1**. (The PRD names this "ADR-0029"; that number was already taken by "App shell and market scope" — the amendment's 0029–0034 numbering is stale, so Phase P authors 0051–0053.)

## Context

There is no market concept in the data model. `parcel.parcel_number` (`String(20)`) is the primary key — semantically a Philadelphia OPA 9-digit account — and **20 tables** carry it: 14 as a `String(20)` FK with `ON DELETE CASCADE` (`sale`, `tax_status`, `sheriff_sale`, `li_event`, `parcel_verdict`, `parcel_distress`, `parcel_assemblage`, `parcel_event`, `saved_parcel`, `saved_search_match`, `deal`, `deed_document`, `deed_restriction`, `appeal_packet`), and 6 as a non-FK column (the `staging.opa/tax/rtt/sheriff_sale/li_event` tables and `zba_appeal`). `sheriff_sale` and `li_event` each have two definitions — a staging row (no FK) and a core row (FK). `ingestion/reconciliation.py::normalize_account` hard-codes the 9-digit shape (strips non-digits, rejects >9, `zfill(9)`) and is the canonical-key generator. A partial primitive already exists: `core/markets.py` defines `Market(StrEnum)` with a single member `philadelphia` + `DEFAULT_MARKET`, and `/search` accepts a cosmetic (unfiltered) `market` query param. The frontend is further along — ADR-0029 shipped `/:market/...` routing, a market store, and a router guard, all using the string **`philadelphia`**.

Allegheny's 16-char block-lot IDs, Baltimore's ward-section-block-lot, Milwaukee's 10-digit TAXKEY, and Cook's zero-padded 14-digit PINs collide with the 9-digit assumption only by luck; a second market needs an explicit market dimension and a key scheme that cannot collide.

## Decision

**Add a `market` table and re-key parcels on a single-column canonical key `{code}:{local_key}` (e.g. `phl:012345678`), keeping the single-column PK so every FK, cascade, upsert helper, and the keyset-pagination chunker survive untouched.**

- **Market code is the short form (`phl`, `hbg`, `pgh`, `bal`, `det`, `mke`, `cle`)** — decided — so canonical keys stay terse across all markets (`pgh:0028F00194000000`, not `pittsburgh:…`). The shipped frontend URL segment `/philadelphia/` is preserved as a **`url_slug`** on the market row (`phl` ⇄ `philadelphia`); the frontend continues to route on the slug and a small bridge maps slug→code when calling the API. `core/markets.py`'s enum is reconciled to the backend-owned market registry (the DB table becomes the source of truth; the enum, if kept, holds codes). The canonical-key prefix is therefore `phl:`.
- **`market` table** (fields from PRD §B1): `code` (pk), `name`, `state`, `url_slug`, `local_srid`, `map_center`, `map_bounds`, `default_zoom`, `timezone`, `recorder_url_template`, `deal_assumption_overrides` (jsonb), `coverage_note`, `launch_status` (`live`/`data_only`/`pilot`). Seed the `phl` row from the values found in Slice 0 (SRID 2272, `America/New_York`, center `[-75.1652, 39.9526]`, default_zoom 13, `recorder_url_template` from `philadox_document_url_template`, `launch_status='live'`).
- **`parcel`** gains `market_code` (FK → `market.code`, indexed, default `'phl'`) and `local_key` (the bare upstream key). `parcel_number` becomes the prefixed canonical key. `String(20)` widens to `String(40)` on `parcel` and **every** FK/staging column in the inventory; the Pydantic cap `pipeline/schemas.py::parcel_number max_length=20` widens in lockstep. Philly-specific `pwd_parcel_id`/`brt_number` stay as columns until Wave 1 (fold into a `source_keys` jsonb later).
- **Migration** (transactional, `feat/expansion-b1-market-key`): create `market` + seed `phl`; widen columns; rewrite `parcel_number → 'phl:' || parcel_number` across all 20 tables in an FK-safe order (or with constraints deferred); backfill `market_code='phl'` and `local_key`; embed verification (pre/post per-table row counts, prefixed-shape assertion, spot-check joins) that raises on mismatch; symmetric `downgrade()` strips the prefix.
- **Compatibility resolver** at the API boundary: a single normalization (path-converter/dependency) treats an incoming parcel id without `:` as `phl:<id>`. Old bare-key URLs, bookmarks, and previously generated PDFs resolve **forever**. The same normalization applies to parcel ids arriving via saved-search criteria, watchlist, and pipeline payloads.
- **Key composition lives in exactly one place** — the reconciliation boundary (B4's `KeyNormalizer`); loaders never hand-prefix.
- **Colon hygiene** (from the B1 inventory): Redis keys `report:{pn}:{ver}` / `ask:` / `summary:` remain valid opaque keys (no code splits on `:` — grep confirmed zero `.split(':')`); PDF filenames sanitize `:`→`-` in the filename only (`lotscope-dossier-phl-012345678.pdf`); MVT functions emit the prefixed key as a property and frontend filter literals must use the same prefixed form.

## Consequences

- **This is the irreversible, highest-risk slice** — a full re-key of the PK graph. It ships alone, behind the migration ritual (prod backup confirmed, migrate-on-deploy wired, rollback = restore + `git revert`).
- **Zero user-visible change**: verdicts are byte-identical modulo `computed_at` (no `VERDICT_VERSION` bump — we are at v8, and Phase P bumps nothing), and old URLs keep resolving via the resolver.
- **Composite PK `(market_code, parcel_number)` was rejected**: it ripples a two-column FK through 20 tables, every raw-SQL join, and the MVT functions — maximal churn for zero capability the prefixed single-column key doesn't already provide.
- The MVT `parcels_mvt`/`vacant_lots_mvt` functions and the frontend map filters must be regenerated/updated in lockstep (they carry `parcel_number`); handled in this slice.
- `normalize_account`'s rewrite is deferred to B4 (Slice 4) as the first `KeyNormalizer`; Slice 1 applies the prefix at the reconciliation boundary directly and B4 formalizes the protocol.
