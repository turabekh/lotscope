# Harrisburg (hbg) data sources — field mapping

Wave-0 pilot. Scope: **City of Harrisburg only** (`DC_Parcels.MUNICIPALI = 'CITY OF HARRISBURG'`, ~19,827 parcels of Dauphin County's ~117.6k). All upstream data is Dauphin County "as-is." Field names verified live against the ArcGIS FeatureServers on 2026-07-05.

## Transports (correction to PRD Appendix A)

The PRD assumed assessment data is extract-only ("no query API for assessments, hence `ExtractClient`"). **This is not what Dauphin publishes.** The county's ArcGIS Hub org (`services2.arcgis.com/EEtiX55QzkHKYQKY`) exposes the assessment tables and parcel geometry as **live-queryable ArcGIS FeatureServers**. So:

- **Spine, tax, characteristics, geometry, streets, municipal, land-use, county-zoning → `ArcGisClient`** (already exists; keyset-paginate by `property_id` / OBJECTID). No `ExtractClient` needed for these.
- **`ExtractClient` / PDF-parse pipeline burns in on the Tax Claim Bureau sale lists** (Slice 3), which are published as **PDF**, not machine-readable — that is the genuine periodic-extract surface for this wave.

## Parcel key

- Canonical: `hbg:<property_id>`, e.g. `hbg:04-038-028`.
- `property_id` format: `MM-BBB-PPP` (assessment district – block – parcel), hyphenated, observed uniform across Harrisburg city. The leading segment is the **assessment district**, not a clean city filter — Harrisburg spans several district prefixes (01, 04, …); **filter city membership by `MUNICIPALI`, never by prefix.**
- `HbgKeyNormalizer` (B4 protocol): trim, upper, preserve hyphens; canonical `hbg:MM-BBB-PPP`. **Verify in Slice 1** whether condo/unit parcels carry a 4th segment or suffix (none seen in the city sample) and lock the golden-file tests to real extract samples.

## Datasets

| Dataset | Service (FeatureServer/0) | Transport | Key | Notes |
|---|---|---|---|---|
| Parcel geometry | `DC_Parcels` | ArcGisClient | `PID` | **SR 102729 / EPSG:2272** — geom_local transform is a no-op (assert SRID). Polygon. Carries denormalized owner/value/address too. `MUNICIPALI`, `PARENT_PAR` (subdivision), `UPI`, `CAMA_PID`. |
| Tax roll (assessment) | `Tax_Roll_Table` (`DC_TaxRoll.csv`) | ArcGisClient (table) | `property_id` | `land`, `building` (assessed), `py_used_code` (land use), owner (`last_name`/`first_name`/`org_indi_flag`), address parts, `city`/`state_code`/`zip_code` = **owner mailing address, not parcel location**. `acres`, `area`. |
| Parcel characteristics | `DC_ParcelCharacteristic` | ArcGisClient (table) | `property_id` | `py_use_code`, `py_tax_code`, **`document_number` (deed reference — the only sale linkage)**, `exeland`/`exebuild` (exempt), `taxland`/`taxbuild` (taxable assessed), `prefland`. |
| Parcel dimensions | `DC_ParcelDimensions` | ArcGisClient (table) | `MAP` | `DIMENSION`, `SIDE` — lot frontage/depth. |
| Land-use codes | `DC_TAX_LANDUSE_CODES` | ArcGisClient (lookup) | `LANDUSE` | `R##` residence, `C##` commercial, `L##` **land/vacant** (L01 bldg lot <1ac … L14 unbuildable lot), `U##` utility, `E##` exempt, `P##` recreational. Feeds `land_use_class` (hbg mapping) + derived vacancy. |
| District/tax codes | `DC_TAX_CODES` | ArcGisClient (lookup) | — | assessment district → municipality. |
| Municipal boundaries | `Municipal_Boundari` | ArcGisClient | `NAME` | `NAME='HARRISBURG'` (FID 27). City-membership fallback (spatial) if `MUNICIPALI` proves dirty. |
| Street centerlines | `DC_Streets` (+ `DC_StreetClass`, `DC_StreetAlias`) | ArcGisClient | — | Landlocked flag. |
| County zoning (generalized) | `TCRP_CountyZoning_Dauphin` | ArcGisClient | `MAP_ACRONY` | **TCRPC generalized regional layer, per municipality — NOT the city's official district geometry.** Usable as a first pass; **must be validated against Harrisburg's official zoning map in the 25-parcel packet** (Slice 4). Locate the city's authoritative districts layer if this diverges. |
| Flood | **City hub `Flood_Parcels`** (`services5.arcgis.com/9n3LUAMi3B692MBL`) via `load_hbg_flood` | ArcGisClient | `floodzone` | **Loaded 2026-07-10.** Parcel polygons pre-tagged `floodzone` (`100 Year` = SFHA, `500 Year` = 0.2%-annual). Kept the non-`N/A` polygons as hbg `FloodZone` rows (`external_id = hbg:flood:{oid}`); the existing spatial-`ST_Intersects` risk join flags parcels — no risk/verdict code change. Chosen over the FEMA NFHL layer (originally planned) because this city layer is already parcel-accurate and reachable. ~3,200 flood polygons. Capability `flood` stays `pending_load` until run on prod + hbg verdict recompute. |

## Sales / valuation — honest degradation (critical)

**Dauphin's open data carries no sale price or sale date.** The only recorder linkage is `document_number` (deed reference) in `DC_ParcelCharacteristic`. Sale prices live at the Dauphin Recorder of Deeds (index/deep-link only; no bulk price feed located). **Consequence: the comps/AVM engine has effectively no priced comps for Harrisburg → value estimates run low-confidence or absent, by construction, from day one.** This is correct behavior, not a defect. The parity gate's comp threshold is met via *honest degradation verified*, and the Slice-6 report records actual comp coverage (expected ≈ 0 priced comps).

## Zoning ordinance (corpus source, Slice 4 — corpus-gated)

- Official text: **City of Harrisburg Codified Ordinances, Title 7 (Planning & Zoning), on eCode360** (General Code), current through 2025-12-29; zoning adopted 2014-07-08 by Ord. 5-2014. `https://ecode360.com/HA1391`.
- **Corpus-gate action (Slice 4):** verify eCode360 / General Code terms permit compliant automated text acquisition. If not, **STOP and hand acquisition to the owner** — no zoning logic from summaries or memory (golden rule §9). District geometry source TBD (TCRP generalized vs. a city layer) — resolve in Slice 4.

## Distress — Dauphin Tax Claim Bureau (RETSL; Slice 3)

First non-MCTLA mapping (ADR-0034 semantics). Lists are **PDF** (`dauphincounty.gov/.../tax-claim/...`):
- **Upset sale** (annual, ~Aug/Sep) → `in_forced_sale_pipeline`, label "Tax upset sale (RETSL)", sheriff-sale weight.
- **Judicial sale** (e.g., 2026-06-29) → forced-sale, label "Tax judicial sale (RETSL)", later stage.
- **Repository** (ongoing, $2,000 min bid) → public-inventory status, **distress 0**, acquirability channel.
Freshness labeled **"as of <list date>"** — never imply a cadence the county doesn't publish.

## Absent feeds → checklist "no data source for this market"

- **No open code-enforcement / violations feed** → the whole "L&I & demolition" checklist category renders *no data source for this market* (not a pass). Distress `violations` component contributes **0** (no weight renormalization; ceiling honestly lower).
- **Overlays / RCO** — Philadelphia concepts; absent for hbg.
- **Historic districts, wards/neighborhoods** — not in the county Hub catalog; historic flag likely absent, named-area search degrades with reason (radius/polygon search carries discovery). Locate city sources in Slice 5 or degrade.

## Public-owned identification

No public-ownership dataset. Derive from owner strings (`org_indi_flag='O'` + name match): City of Harrisburg, County of Dauphin, Harrisburg Redevelopment Authority, plus Tax Claim repository parcels. Strategy finalized in the ADR.

## Recorder posture

Dauphin Recorder of Deeds — `document_number` is the deed reference; `recorder_url_template` provides an index deep-link. No bulk price data.

## Market-literal sweep — Slice-6 checklist (from repo grep)

A Harrisburg snapshot that says "Philadelphia" is the classic Wave-0 bug. Every item below must render the market's city name from data (or be relabeled/hidden), never a literal:

- **AI prompts** — `ai/prompts.py:8,24,63` ("...assistant/analyst for **Philadelphia** real estate") — snapshot + Ask-the-Parcel system prompts.
- **PDF dossier / appeal packet** — `reports/dossier.py:127` and `reports/appeal_packet.py:83` ("LOTSCOPE PHL ..."); `reports/service.py:18` ("**Philadelphia** city data ... © LotScope PHL").
- **Email** — `outreach/service.py:27` ("from public **City of Philadelphia** records").
- **Frontend copy** — `MapView.vue` ("Back to **Philadelphia**", `PHILADELPHIA` const → already market-driven via `/markets` in Phase P B10); `HistoricPanel.vue:19`, `OwnerPortfolioPanel.vue:60`, `VerdictPanel.vue:29` ("Philadelphia historic districts"); `LandingPage.vue` (hero copy — marketing, likely leave for pilot); `index.html` `<title>`, `AuthPage`/`AppSidebar` "LotScope **PHL**" brand (brand stays per Wave-0 out-of-scope).
- **Note:** brand "LotScope PHL" naming is explicitly out of scope for the pilot; fix only the *data/city-name* literals, not the brand.

## Philly-specific surfaces needing per-market availability (Slice 6)

- **Sheriff-sales page** (`api/sheriff_sales.py`, `pages/SheriffSalesPage.vue`, sidebar nav + `/:market/sheriff-sales` route) — MCTLA-named; relabel/hide for hbg (RETSL naming).
- **ZBA variance outlook** (`zba/` module + panel; ADR-0050) — Philadelphia-only; hide for hbg.
- **Zoning overlays / RCO panels** — Philadelphia concepts; absent for hbg.
- **Checklist "L&I & demolition" category** (`checklist/logic.py`) — must show *no data source for this market*.
- Driven by a **market-capabilities config**, not scattered `if market == …` conditionals.

## Lot area — source & the DC_Parcels acres variance (field-test 2026-07-06)

Harrisburg `parcel.lot_area_sqft` is **polygon-derived** (`ST_Area(geom_local)`), recorded as `lot_area_source = 'geometry'`. Philadelphia uses OPA's deeded `total_area` (`lot_area_source = 'extract'`).

We evaluated preferring the extract's stated area for hbg and **rejected it**: the only area field in the GIS extract, `DC_Parcels.acres`, is rounded to **2 decimals** — for small urban lots this is coarser than the polygon by up to ~50% (sampled 14 small lots; 11 differed >5% from the polygon; worst case PID 02-017-016: acres 0.01→436 sqft vs polygon 852 sqft). Preferring it would degrade lot area on exactly the infill parcels the product targets.

**Field-test parcel 02-021-052 variance (recorded, not chased):** polygon `ST_Area` = **2,484 sqft** (retained); `DC_Parcels.acres` 0.05 → **2,178 sqft** (rounded, less precise); the county's third-party figure of **2,295 sqft** comes from the Dauphin **CAMA/assessment** system, which the GIS extract does not expose. If a precise CAMA deeded-area export becomes available, prefer it then (and set `lot_area_source` accordingly).

## Common level ratio (assessment → market value)

Dauphin County is a base-year assessment county: the assessed value is a fraction of market value, unlike Philadelphia's ~100% ratio. Assessment-comparison features (the "vs. assessment" gap and the over-assessment / tax-appeal signal) therefore compute against the **ratio-implied market value = assessed ÷ CLR**, labeled as such; Philadelphia's math runs at ratio 1.0 and is byte-identical.

- **Dauphin County 2024 Common Level Ratio: 0.4042** (40.42%), effective **July 1 2025 – June 30 2026**.
- Source: PA Bulletin Vol. 55, No. 27 (2024 Common Level Ratios); STEB / PA DCED Tax Equalization Division. Note: STEB states the CLR is for assessment-appeal use, not to create value.
- `market.assessment_ratio`: phl = 1.0000, hbg = 0.4042. Refresh annually when STEB publishes the new CLR (effective each July 1).

## Tax-claim / delinquency feed — built, deliberately unregistered

The Dauphin tax-claim loader (`ingestion/loaders/hbg_taxclaim.py`, `load_hbg_tax_claim`) is built and unit-tested but is **not** in the JOBS registry (`ingestion/jobs.py`), so it does not run on the daily `ingest_market('hbg')`. This is intentional, not an oversight: Dauphin publishes delinquency through its **seasonal** upset/judicial sale lists (the upset list publishes ~August for the September sale), and the fetch is prod-origin (the build environment cannot reach dauphincounty.gov). Registering it now would schedule a job against a source that has nothing to return.

**When the ~August 2026 upset list publishes:** register `ingest_hbg_tax_claim` in `_HBG_JOBS` (environment-aware, prod-origin), point it at the published list, and the checklist `liens_taxes` state flips from `pending_load` toward `live` for the parcels it covers. Until then the truthful `pending_load` state (ADR: field-test Slice 2 / `markets/capabilities.py`) is correct. The **repository** list (county-held, purchasable year-round) is already wired and refreshing monthly — that is a distinct feed from delinquency.
