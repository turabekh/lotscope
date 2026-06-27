# Philadelphia Data Sources

Catalog of the upstream datasets LotScope ingests, their access patterns, and the gotchas that ingestion must respect. This is a living document — endpoints, schemas, and field names are verified during the ingestion slice (build order step 3) and updated here.

> All city data is provided **"as is" / hold-harmless**. Parse and validate defensively; surface source and freshness on every derived datum.

## Tabular — Carto SQL API

Base endpoint: `https://phl.carto.com/api/v2/sql`

| Dataset | Table | Purpose | Notes |
|---|---|---|---|
| OPA assessments | `opa_properties_public` | Owner, mailing address, assessed market/land/building values, land use | Keyed on OPA `parcel_number`. The assessment + ownership spine. |
| Recorded transfers | `rtt_summary` | Real recorded sales / deeds / mortgages / sheriff deeds with prices | The **comps** source; back to 1999. Realty Transfer Tax dataset. |
| Parcels (PWD) | `pwd_parcels` | Authoritative parcel polygons | Join key to OPA is **not** aligned — reconcile explicitly. |
| Tax delinquency | (revenue dataset) | Liens, amounts, years owed, sheriff-sale exposure | Distress signal. |
| L&I | (violations / permits / demolitions) | Violations, permits, demolitions, unsafe / imminently-dangerous flags | Daily freshness target. |

**Carto gotchas (must respect):**
- Carto **times out on full-table dumps** → chunk by parcel-number ranges; never paginate a full table in one query.
- SQL is **case-sensitive** → use `ILIKE` for text matching.
- Always parametrize / construct SQL safely; never string-interpolate untrusted input.

**Field mappings (verify against the live API).** The OPA loader maps
`opa_properties_public` columns — `parcel_number`, `location`, `zip_code`,
`owner_1`, `mailing_address_1`, `category_code_description`, `zoning`,
`market_value`, `taxable_land`, `taxable_building`, `total_area`, `frontage`,
`depth` — onto the `parcel` table. These names are plausible but must be
confirmed against the current schema; the transform is defensive and tolerates
missing or renamed fields. Update this table as each loader's mapping is verified.

The PWD loader reads `pwd_parcels` (`cartodb_id`, `brt_number`, `parcel_id`,
and `the_geom` as GeoJSON), reconciles `brt_number` to the canonical parcel
key, and writes geometry into `parcel`: `geom_4326` via `ST_GeomFromGeoJSON`
and `geom_2272` via `ST_Transform` in our own PostGIS (so the projection does
not depend on Carto). Chunking keys on `cartodb_id`, the Carto system primary
key, which is monotonic and present on every Carto table.

## GIS — ArcGIS Hub

Base: `https://data-phl.opendata.arcgis.com`

| Layer | Purpose |
|---|---|
| Vacant Property Indicators | The city's per-parcel vacancy model — the **core vacant-lot inventory**. |
| Zoning Base Districts | Title 14 base districts (RSA / RM / CMX, …) and overlays. |
| Building footprints | Structure presence on a parcel. |
| Land use | Categorical land use. |
| FEMA flood | Flood zones. |
| Historic districts | Overlay / review impacts. |
| Council districts, neighborhoods / RCOs | Boundaries, notification requirements. |

## Publicly-owned / Land Bank

City-owned property and Land Bank / PHDC inventory — flags publicly-owned lots and disposition status. Current authoritative source to be located and pinned during ingestion.

## Title 14 zoning standards (reference data)

The `zoning_standard` table is populated by an idempotent seed
(`lotscope.zoning.seed`, run via `make seed`), not an API. The shipped values
are **provisional** (`code_version = title14-provisional-2024`): the district
taxonomy and well-established figures (e.g. RSA-5 = 1,440 sq ft / 16 ft / 38 ft)
are encoded, and fields not yet confirmed are left NULL so the engine degrades
honestly rather than asserting false precision. **Verify every value against
the official Title 14 text before production use** and re-run the seed to update.

## Recorded documents

DOR records system for deed / plat images — the OCR + RAG layer for restriction and easement extraction.

## Third-party (optional)

- **Regrid** — standardized ownership + mailing for skip-trace; portability beyond Philadelphia (fallback for base parcels).
- Skip-trace provider, imagery provider — provider-agnostic interfaces.

## Geometry & keys

- Analysis geometry: **EPSG:2272** (feet). Tile geometry: **EPSG:4326**.
- **Parcel-key reconciliation** (OPA ↔ PWD ↔ RTT) is a first-class, tested concern — the join keys are not aligned upstream.
