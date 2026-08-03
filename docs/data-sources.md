# Philadelphia Data Sources

Catalog of the upstream datasets LotScope ingests, their access patterns, and the gotchas that ingestion must respect. This is a living document — endpoints, schemas, and field names are verified during the ingestion slice (build order step 3) and updated here.

> All city data is provided **"as is" / hold-harmless**. Parse and validate defensively; surface source and freshness on every derived datum.

## Tabular — Carto SQL API

Base endpoint: `https://phl.carto.com/api/v2/sql`

| Dataset | Table | Purpose | Notes |
|---|---|---|---|
| OPA assessments | `opa_properties_public` | Owner, mailing address, assessed market/land/building values, land use | Keyed on OPA `parcel_number`. The assessment + ownership spine. |
| Recorded transfers | `rtt_summary` | Real recorded sales / deeds / mortgages / sheriff deeds with prices | The **comps** source; back to 1999. Realty Transfer Tax dataset. **Package-deed gotcha:** a multi-parcel deed attaches the full deed price to *every* parcel on it, so a 3-lot $600k sale reads as three $600k comps. The comp finder excludes any sale whose `document_id` appears on more than one parcel (ADR-0049). |
| Parcels (PWD) | `pwd_parcels` | Authoritative parcel polygons | Join key to OPA is **not** aligned — reconcile explicitly. |
| Tax delinquency | (revenue dataset) | Liens, amounts, years owed, sheriff-sale exposure | Distress signal. |
| L&I | (violations / permits / demolitions) | Violations, permits, demolitions, unsafe / imminently-dangerous flags | Daily freshness target. |
| Historic districts | `historicdistricts_local` | Local Register historic-district boundaries → Historical Commission review overlay (ADR-0028) | 17 polygons; fields `objectid`, `name`, `designated`, `the_geom`. |

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
| FEMA flood | Flood zones. Only **SFHA** designations (zone starts `A`/`V`) are a risk flag; 0.2%-annual / shaded-X is informational; unshaded X and minimal-hazard zones do not flag (ADR-0049). |
| Historic districts | Overlay / review impacts. |
| Council districts, neighborhoods / RCOs | Boundaries, notification requirements. |
| Street Centerline | Street network (~41k LineString segments); basis for the landlocked / no-street-access flag (ADR-0027). `Street_Centerline` FeatureServer; key `seg_id`, name `stname`. |
| Zoning Overlays | Title 14 overlay districts (~193 polygons) → `overlay_district` verdict flag (ADR-0040). `Zoning_Overlays` FeatureServer; key `objectid`, `overlay_symbol` (code), `overlay_name`, `code_section`. Resolution via `ST_Intersects`. |
| Zoning RCO | Registered Community Organization boundaries (~233 polygons) → `rco` verdict flag / variance-meeting requirement (ADR-0040). `Zoning_RCO` FeatureServer; key `objectid`, `organization_name`, `org_type`. **Contact PII fields (primary_name/email/phone) are deliberately NOT ingested** (§13). |

## Sheriff sales (A4 · ADR-0038)

Philadelphia Sheriff's Office real-estate sale lists (tax + mortgage foreclosure) — the dated auction calendar. Upstream is **CivilView** (`https://salesweb.civilview.com/Sales/SalesSearch?countyId=60`): server-rendered HTML list + per-property detail pages, CSV-exportable. Each row carries **Book & Writ (case number)**, **OPA #**, address, plaintiff, sale type, status, sale date, opening bid. The consumer-facing `phillysheriff.com/services/list-of-properties/` is a bot-protected Bid4Assets/CivilView embed — not an acquisition target.

Acquisition is decoupled from the record contract (`SheriffSaleRecord`) behind a `SheriffSource` interface. Two adapters, selected by `SHERIFF_SALE_SOURCE`:

- **CSV/file adapter** (`CsvSheriffSource`, `SHERIFF_SALE_CSV_PATH`) — the default and the operational fallback if the scrape breaks.
- **CivilView HTML adapter** (`CivilViewSheriffSource`, `SHERIFF_SALE_SOURCE=civilview`) — fetches the `countyId` list (`SHERIFF_SALE_COUNTY_ID`, phl = 60) then each per-property detail page, primed by a session cookie the list response sets (detail pages 302 to home without it). Parsing is a pure, fixture-tested function over saved HTML (**selectolax**); the list supplies Book & Writ / OPA # / address / plaintiff, the detail page adds sale type / current status / sale date / minimum (opening) bid. Polite pacing via `SHERIFF_SALE_CIVILVIEW_REQUEST_DELAY_SECONDS`; `SHERIFF_SALE_CIVILVIEW_DETAIL_LIMIT` caps detail fetches for smoke runs. CivilView serves no `robots.txt` (404); scraping stays low-volume and honors ToS.

Loader is staged (raw→staging→merge, ADR-0036): a new case emits a dated `sheriff_sale` event. Turning the live scraper on in production is an env flip — see the sheriff-sale section of [runbook.md](runbook.md).

**Reconciliation:** OPA # → `normalize_account` → `parcel_number`; rows with no resolvable OPA are retained in `raw` but skipped from core/events (address-match is a follow-up). CSV columns expected by `CsvSheriffSource`: `case_number, opa_number, address, sale_type, status, sale_date, opening_bid, plaintiff`.

## Publicly-owned / Land Bank

City-owned property and Land Bank / PHDC inventory — flags publicly-owned lots and disposition status. Current authoritative source to be located and pinned during ingestion.

## Title 14 zoning standards (reference data)

The `zoning_standard` table is populated by an idempotent seed
(`lotscope.zoning.seed`, run via `make seed`), not an API. The Philadelphia
values come from the [Base Districts Quick Guide, February 2026](https://www.phila.gov/media/20260213170558/ZONING-QUICK-GUIDE_feb-2026.pdf)
(`code_version = title14-quickguide-2026-02`) — a summary published by the
Planning Commission, **not the code text**. Other markets ship provisional
values pending local review.

A NULL dimensional field means one of two things, and they are not
interchangeable — see **ADR-0075**. Where the guide shows a district genuinely
sets no such standard (CMX-3/4/5 have no height row; RMX lot width reads
`N/A`), that is recorded in `field_dispositions` as `unregulated` and the
product answers the check rather than reporting it unevaluated. Where a
standard exists but cannot be reduced to one figure (I-1/2/3 height is
conditional on abutting districts; RM-2/3/4 height is expressed as an FAR;
CMX-1 inherits its dimensions from adjacent districts), the disposition is
`conditional` and the rule itself is shown. A NULL with **no** disposition
means the value has simply not been captured, and stays that way until read
from a primary source.

Dispositions are recorded only for districts read directly from the guide;
asserting "no standard applies" without that evidence would be worse than the
vagueness it replaces. **Verify every value against the official Title 14 text
before production use** and re-run the seed to update. Note the guide carries
no parking table — `min_parking_spaces` is null for every district because
Chapter 14-800 has never been ingested.

## Title 14 RAG corpus

The "Ask the Parcel" feature grounds answers in `document` rows under
`source = "title14"`, loaded by `lotscope.ai.corpus` (`make ingest-title14`)
from a JSONL of `{section, title, text}` records — chunked, embedded with
Voyage, and replaced on each run. A provisional sample ships at
`backend/data/title14/sections.sample.jsonl`; the real Title 14 section text is
a data task you supply at `backend/data/title14/sections.jsonl`. See that
directory's README for the format. Requires `VOYAGE_API_KEY`.

## Recorded documents

DOR records system for deed / plat images — the OCR + RAG layer for restriction and easement extraction.

## Third-party (optional)

- **Regrid** — standardized ownership + mailing for skip-trace; portability beyond Philadelphia (fallback for base parcels).
- Skip-trace provider, imagery provider — provider-agnostic interfaces.

## Geometry & keys

- Analysis geometry: **EPSG:2272** (feet). Tile geometry: **EPSG:4326**.
- **Parcel-key reconciliation** (OPA ↔ PWD ↔ RTT) is a first-class, tested concern — the join keys are not aligned upstream.
