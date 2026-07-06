# ADR-0055 — Wave 1: Pittsburgh kickoff

Status: proposed (2026-07-06)

## Context
Third market, first at scale (~150k parcels). Allegheny County data via the WPRDC CKAN datastore (reachable from build — recon `docs/wave1-recon.md`). `launch_status='pilot'` at wave end; graduation is a later effort. `VERDICT_VERSION` stays v8 through Slice 7.

## Decision
- **Scope & filter:** Pittsburgh city only; `MUNIDESC ILIKE '%PITTSBURGH%'` (32 wards). County fringe excluded (`coverage` field exists if revisited).
- **SRID:** analysis `geom_local` = EPSG:2272 (PA South — same plane as phl/hbg, zero CRS work, third time); tiles 4326. Assert 2272 no-op in Slice 2.
- **Key & normalizer:** `PARID`/`PIN`, 16-char alphanumeric block-lot. `PghKeyNormalizer` → `pgh:<PARID>`; golden files from real samples (padding/suffix quirks captured in Slice 1).
- **Transports:** CKAN `CkanDatastoreClient` (primary, keyset-chunked like the Carto client) for assessment/sales/liens/violations/condemned/city-owned/foreclosures; ArcGIS/GIS where geometry needs it (boundaries WKB, zoning districts, neighborhoods, historic). Per-dataset `source_config` rows with resource_ids from the recon.
- **Sales validity:** load Property Sale Transactions filtered to `SALEDESC='VALID SALE'` at the loader; provenance `"sales_validation_filtered": true`. Supersedes the phl document-id package heuristic for pgh.
- **Lien key:** composite `docket_number + year + description` (docket numbers are non-unique per the publisher's warning).
- **Distress & surface naming:** Treasurer's Sale + sheriff sale + foreclosures + liens + city delinquency → forced-sale weight; stages named in flag details. Forced-sale surface label: **pgh "Treasurer's sale"** (phl "Sheriff sales" / hbg "Tax sales") via capabilities.
- **Assessment ratio:** `pgh` `assessment_ratio` = **0.5014** (Allegheny 2024 CLR, base year 2012); implied market = assessed ÷ CLR (field-test mechanism).
- **Capabilities:** owner surfaces (Leads owner-dimension, owner-portfolio panel) **off for pgh** (Ordinance 3478-07 + no owner names in the feed); `zba_variance` hidden; forced-sale surface under the pgh name.
- **Recorder deep-link:** Allegheny real-estate portal template in the market row.
- **Deal assumptions:** `pgh` placeholders (construction $/sqft TBD), `assumptions_source='market_default'` until a local review calibrates.
- **License ledger:** WPRDC licenses are per-dataset — each recorded in `docs/data-licenses.md` as loaded.

## Consequences
- Strongest expected comp coverage of any market (assessor-validated VALID SALE set).
- Owner-based leads unavailable for pgh until the 3478-07 legal read (and would need an owner-name source the feed lacks).
- Zoning authoring (Slice 5) is the critical path — Municode acquisition + attachment inventory, corpus-gated; STOP if compliant tooling is impossible.
- Three-market regression (phl + hbg golden parcels) on every shared-code slice.
