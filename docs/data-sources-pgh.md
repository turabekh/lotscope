# Pittsburgh (Allegheny County via WPRDC) — data sources & field mappings

CKAN datastore `data.wprdc.org` (reachable from build). City filter `MUNIDESC ILIKE '%PITTSBURGH%'` (32 wards). Canonical key `pgh:<PARID>` (16-char). Analysis geometry EPSG:2272; tiles 4326.

## Spine — Property Assessments (`65855e14-…`, `CkanDatastoreClient`, keyset by PARID)
| Parcel field | Assessment column | Note |
|---|---|---|
| parcel_number | `PARID` | `pgh:<PARID>` via PghKeyNormalizer |
| address / zip | `PROPERTYADDRESS` / `PROPERTYZIP` | |
| land_use | `USEDESC` | |
| market_value / land_value / improvement_value | `COUNTYTOTAL` / `COUNTYLAND` / `COUNTYBUILDING` | base-year 2012 assessed; CLR 0.5014 → implied market via the assessment engine |
| lot_area_sqft | `LOTAREA` | **stated (precise)** — `lot_area_source='extract'`; polygon fallback. Opposite of hbg (there the stated field was coarse and the polygon won). |
| base_zoning_code | — | NULL (no zoning attribute; resolved spatially) |

143,215 parcels loaded (~64s).

## Geometry — Parcel Boundaries (`3f50d47a-…`, CKAN)
WKB is bytea-hex in **EPSG:4326** (Pittsburgh lon/lat) — fetched via `encode("dataspatial_wkb",'hex')` in the SQL keyset (the plain SQL API mangles the binary to a memoryview). `geom_4326` native; `geom_local = ST_Transform(…,2272)`. Filtered to Pittsburgh `MUNICODE` set (derived from the assessment). 143,257 geometries loaded (~92s), ~98.9% of parcels (unmatched PINs honestly without geometry).

## Reconciliation
PARID (assessment) = PIN (boundaries), 16-char block-lot. Unresolved reported, never dropped.

## Licenses
WPRDC licenses are per-dataset — confirm each package's `license_id` at load and record in `docs/data-licenses.md`.
