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

## Recorded documents

DOR records system for deed / plat images — the OCR + RAG layer for restriction and easement extraction.

## Third-party (optional)

- **Regrid** — standardized ownership + mailing for skip-trace; portability beyond Philadelphia (fallback for base parcels).
- Skip-trace provider, imagery provider — provider-agnostic interfaces.

## Geometry & keys

- Analysis geometry: **EPSG:2272** (feet). Tile geometry: **EPSG:4326**.
- **Parcel-key reconciliation** (OPA ↔ PWD ↔ RTT) is a first-class, tested concern — the join keys are not aligned upstream.
