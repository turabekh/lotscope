# 48. Multi-jurisdiction tenancy (Harrisburg and beyond)

Date: 2026-07-04

## Status

Proposed

Foundational decision for expansion beyond Philadelphia (a Harrisburg / Dauphin County pilot is the trigger). This is the one change that touches the whole data model and every query, so it is decided before any second-market code is written. It does **not** cover Harrisburg data acquisition or which features ship in the pilot — those follow in a pilot-scope doc once this contract is set.

## Context

The **shell** was built for this: ADR-0029 made "market" a first-class URL scope (`/:market/...`) with a market store and switcher, and `data-sources.md` already names **Regrid** as the "portability beyond Philadelphia" fallback. But **everything behind the shell is single-tenant Philadelphia**, in three ways that each block a second market:

1. **No jurisdiction dimension.** No table carries a market/county column. Worse, `parcel`'s **primary key is the OPA `parcel_number`** — a Philadelphia ID scheme. Harrisburg parcels use Dauphin County's scheme; two markets' IDs can collide and cannot share one keyspace. Every FK (`parcel_verdict`, `parcel_distress`, `tax_status`, `li_event`, `sale`, `saved_parcel`, `sheriff_sale`, …) points at that PK.
2. **Ingestion is Philly-hardwired.** Every loader targets Philadelphia sources (Carto `opa_properties_public` / `rtt_summary` / `pwd_parcels`, ArcGIS Hub zoning/vacancy/overlays, Philly Sheriff CivilView, Philly Land Bank). Nothing is source-pluggable.
3. **Zoning is Title 14 end-to-end.** The `zoning_standard` table, the buildability engine, and the AI grounding corpus all assume Philadelphia's code. Harrisburg has its own ordinance with different districts — this is the single most expensive thing to port, and the pilot will defer it.

The strategic reality (worth stating so the design doesn't over-invest): **Philadelphia's open-data depth is the moat and is not cheaply replicable.** Most PA jurisdictions are far thinner. So the tenancy model must let a market run on a *reduced* feature set (base parcels + ownership + comps + distress, no buildability verdict) without the schema pretending every market is Philadelphia-complete.

## Decision

**Add an explicit `market` dimension to the core data model as a short string code (`'philadelphia'`, `'harrisburg'`), re-key parcels on `(market, source_parcel_id)`, scope every query and ingestion run by market, and make ingestion + zoning market-pluggable behind interfaces — one shared schema, row-level market scoping (not schema-per-tenant, not a DB-per-market).**

- **Keying.** Introduce a **surrogate parcel key** `parcel.id` (uuid/bigint) as the new PK; keep the jurisdiction-native id as `parcel.source_parcel_id` with a **unique `(market, source_parcel_id)`**. All child tables carry `market` and FK to `parcel.id` (or to `(market, source_parcel_id)` — chosen in the migration). `parcel_number` stays as a Philadelphia-specific column, no longer load-bearing. This is the irreversible part and the bulk of the migration.
- **Scoping is mandatory, not optional.** `market` is a required filter on every parcel-derived query, tile source, search, and precompute job. A single shared Postgres schema with a `market` column (indexed, and composite-indexed with geometry and hot filters) — chosen over schema-per-market or DB-per-market because it keeps one migration path, one connection pool, cross-market admin/analytics, and matches the existing single-DB PostGIS + Martin setup; the isolation we need is row-level and query-enforced, not physical.
- **Market registry, backend-owned.** A `market` config (code, label, EPSG analysis SRID, feature flags, source adapter set) lives in the backend and is exposed to the frontend, replacing the hard-coded `MARKETS = ['philadelphia']`. Philadelphia analysis SRID is **EPSG:2272**; Harrisburg/Dauphin is a **different state-plane zone (EPSG:2271, PA North)** — so the "2272 for analysis" assumption becomes per-market, and geometry columns stay dual-SRID (analysis + 4326) with the analysis SRID read from the market.
- **Feature flags per market.** Each market declares which engines are live (`buildability`, `verdict`, `distress`, `comps`, `sheriff`, `outreach`, …). The verdict/dossier degrade gracefully: a market without buildability shows parcel + ownership + comps + distress and a "buildability not yet modeled for {market}" state rather than a fabricated verdict. This is what lets Harrisburg launch thin.
- **Ingestion becomes market-pluggable.** A `MarketSource` adapter set per market behind the existing loader interfaces (mirrors the `SkipTraceProvider` / `EmailProvider` pattern): Philadelphia keeps its Carto/ArcGIS loaders; Harrisburg gets **Regrid** (base parcels + ownership + mailing) + Dauphin County assessment + Recorder-of-Deeds sales adapters. Ingestion runs, freshness, and the raw→staging→merge path all key on `market`.
- **Zoning becomes market-scoped.** `zoning_standard` (and the AI grounding corpus) gain a `market` dimension; buildability resolves the market's code. Harrisburg's ordinance is modeled as its own slice **later** — the pilot ships with buildability off for Harrisburg.
- **Auth/accounts stay global**; a user can view any market. Billing/limits stay per-user, not per-market (revisit only if per-market pricing is ever wanted).

## Consequences

- **One big migration, done once.** Re-keying `parcel` and back-filling `market='philadelphia'` across every child table is the heavy lift and the point of no return — it must be a single, well-tested Alembic migration with a full re-verify of the verdict/distress/search paths. Every query in every module gains a `market` filter; missing one silently leaks cross-market data, so this needs a systematic sweep (and ideally a session-level market guard in the query layer).
- **The frontend is mostly ready.** The `/:market/` scope, store, and switcher already exist; the work is swapping the static registry for the backend one, threading `market` into API calls, and honoring feature flags in the UI (hide/greu-out engines a market doesn't have).
- **Enables a thin Harrisburg pilot** (the point): Regrid base + county comps + portable distress + outreach, with buildability/verdict deferred — enough for the agent A/B test without the ordinance-modeling cost. If it validates, Harrisburg buildability + zoning corpus become their own ADR + slices.
- **Cost/scale:** one shared DB with a `market` column is the cheapest path and fine at two-city scale; if a future market demands isolation (a large tenant, a data-license boundary), schema-per-market can be revisited per-market without redoing this contract.
- **Test-first, per §12:** every scoped query proven to exclude other markets (seed two markets, assert isolation); the migration re-keys without dropping rows; feature-flag degradation renders a partial market correctly; a `MarketSource` is mockable (a `Null`/fixture adapter for tests). No live Regrid/county calls in tests.
- **Explicitly out of scope here:** Harrisburg data-source specifics and licensing (Regrid contract), Harrisburg zoning modeling, per-market billing, and the pilot feature list — all follow once this keying/scoping contract is accepted.
