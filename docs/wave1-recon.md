# Wave 1 (Pittsburgh) — Slice-0 recon

Pittsburgh city (~150k parcels) via Allegheny County data through the **WPRDC CKAN datastore** (`data.wprdc.org`). Docs-only. `launch_status='pilot'` at wave end.

## 1. Reachability — YES (first wave with live dev data)
`data.wprdc.org` is reachable from the build environment (HTTP 200, ~1.5s). Unlike the Wave-0/field-test county sites (dauphincounty.gov firewalled, FEMA NFHL unreachable), the CKAN datastore API + `datastore_search_sql` work directly. Dev works against live data; **fixtures remain the test substrate** regardless (golden files captured from real samples).

## 2. Dataset inventory (CKAN datastore resource_ids)
| Dataset | resource_id | Role |
|---|---|---|
| Property Assessments (API) | `65855e14-549e-4992-b5be-d629afc676fa` | spine |
| Parcel Boundaries | `3f50d47a-ab54-4da2-9f03-8519006e9fc9` | geometry |
| Property Sale Transactions | `5bbe6c55-bce6-4edb-9d04-68edeb6bf7b1` | comps (validation-coded) |
| Tax Liens | `d1e80180-5b2e-4dab-8ec3-be621628649e` | distress |
| PLI/DOMI/ES Violations | `70c06278-92c5-4040-ab28-17671866f81c` | violations (real — unlike hbg) |
| Condemned & Dead-End | `0a963f26-eb4b-4325-bbbc-3ddf6a871410` | facts (unscored at v8) |
| City-Owned Properties | `e1dcee82-9179-4306-8167-5891915b62a7` | public inventory |
| Mortgage Foreclosures | `859bccfd-0e12-4161-a348-313d734f25fd` | distress |
| Zoning (GIS) | `6127f35e-f36b-4a53-80b3-f4409609e9df` | district resolution |
| Neighborhoods (90) | `4af8e160-57e9-4ebf-a501-76ca1b42fc99` | named-area search |
| Land Bank inventory, City delinquency | *to confirm resource_id in S3/S4* | inventory / distress |

## 3. Spine, key, city filter, lot area
- **Parcel key = `PARID`** (assessment) = **`PIN`** (boundaries): 16-char block-lot, alphanumeric (e.g. `0011S00062000000`, note the letter). Drives **`PghKeyNormalizer`**; canonical `pgh:<PARID>`. Boundaries also carry `MAPBLOCKLO`, `CALCACREAG` (polygon acreage), WKB in `dataspatial_wkb`.
- **City-of-Pittsburgh filter = `MUNIDESC ILIKE '%PITTSBURGH%'`** (values are `"Nth Ward - PITTSBURGH"`, 32 wards; `MUNICODE` in the Pittsburgh range). County-fringe excluded (city-only, per the Wave-0 pattern; `coverage` field exists if revisited).
- **Lot area:** `LOTAREA` (stated, assessment) vs `CALCACREAG × 43560` (polygon). **Run the Wave-0 polygon-vs-stated comparison on a sample in Slice 2 before choosing** — do not assume; record `lot_area_source` in provenance either way (field-test lesson: coarse stated fields can lose to the polygon).
- **Assessment values:** `COUNTYTOTAL`/`LOCALTOTAL` (base-year 2012 assessed), `FAIRMARKETTOTAL/LAND/BUILDING` (assessor fair-market). Allegheny is a **base-year county** → the field-test `assessment_ratio` mechanism applies.

## 4. Common level ratio
- **Allegheny County 2024 CLR = 50.14 → `assessment_ratio` 0.5014**, base year 2012, eff Jul 1 2025 – Jun 30 2026 (PA Bulletin 55-27; STEB). Implied market = assessed ÷ 0.5014. (Seed in Slice 5/assessment, same as hbg 0.4042 / phl 1.0.)

## 5. Sales validation codes (Slice-3 filter driver)
`SALECODE`/`SALEDESC` on the sales dataset. **Keep only `VALID SALE`** for comps. Exclude: MULTI-PARCEL, LOVE AND AFFECTION, CORPORATION TRANSFER, GOVERNMENT SALE, ESTATE SALE, QUIT CLAIM, CORRECTIVE DEED/DUPLICATE, INCLUDES PERSONAL PROPERTY, SALE OF PREVIOUS FORECLOSURE-INVALID, OTHER INVALID, SHERIFF SALE, CITY TREASURER SALE, BANK/FINANCIAL, CHANGED AFTER SALE, TIME ON MARKET, SALE NOT ANALYZED, NOT APPLICABLE, OTHER. This **supersedes the phl document-id package heuristic** for pgh (assessor-validated comps — expected to be the strongest comp coverage of any market). Provenance: `"sales_validation_filtered": true`.

## 6. Distress semantics — Pittsburgh forced-sale = "Treasurer's sale"
The city **Treasurer's Sale** (+ sheriff sale) is the forced-sale pipeline (both appear as sale-validation codes; the Treasurer's Sale is the tax-foreclosure channel). Surface naming: phl "Sheriff sales" / hbg "Tax sales" / **pgh "Treasurer's sale"**. Foreclosures + tax liens + city delinquency map to the forced-sale weight; stages named in flag details. (ADR-0034-style mapping table in the kickoff ADR.)

## 7. Zoning code source — Municode (primary) + eCode360
Pittsburgh Zoning Code = **Title Nine** on **Municode** (`library.municode.com/pa/pittsburgh` → `PIZOCO_TITNINEZOCO`); also an eCode360 mirror (`ecode360.com/PI6865`). The code is **substantially larger than Harrisburg's**. **Slice-5 attachment inventory required** (the eCode360 lesson: use tables + dimensional tables often live as separate exhibits) — inventory Municode's structure + verify text-acquisition terms; the corpus-gate STOP applies if compliant acquisition is impossible. Flag now: **Municode terms + attachment structure are the Slice-5 critical-path risk.**

## 8. Ordinance 3478-07 — owner surfaces OFF (data reality + legal)
See `docs/pgh-ordinance-3478-07-memo.md` (HANDOFF for your legal read). Key: 3478-07 prohibits public search of assessment records **by owner name**, and **the WPRDC assessment feed carries no owner names at all** (`OWNERCODE`/`OWNERDESC` are owner-*type* codes, not names). So the Leads owner-dimension + owner-portfolio panel are off for `pgh` **by data reality**, not only caution — capabilities ships them off; turning on is your decision after the legal read.

## 9. v9 batch proposal (Slice 8 — separately gated)
See the updated `docs/verdict-bump-queue.md`. Proposed v9 contents: (a) **hbg condemned scoring** (queued from the field-test batch); (b) **pgh condemned → unsafe-structure-class severity**; (c) **pgh dead-end (owner unlocatable per PLI) → new high-value distress factor**. Recompute bill (batched behind one version, ADR-0028): Philadelphia citywide ~4–5h, Harrisburg ~12 min, Pittsburgh ~1.2h. One ADR, one bump, one coordinated recompute.

## Plan
| Slice | Branch | Migration? | Notes |
|---|---|---|---|
| 0 recon + ADR + v9 proposal | `feat/wave1-recon` | no | this |
| 1 market row + PghKeyNormalizer + switcher | `feat/wave1-market-pgh` | yes (seed row) | golden keys from real PARIDs |
| 2 spine + geometry (CkanDatastoreClient) | `feat/wave1-spine-geometry` | maybe | polygon-vs-stated decision; 2272 no-op assert |
| 3 sales + liens + delinquency + distress | `feat/wave1-sales-distress` | maybe | VALID-SALE filter; Treasurer's-sale naming; liens live |
| 4 violations + condemned/dead-end + inventories | `feat/wave1-violations-inventories` | maybe | PLI real; condemned/dead-end unscored facts |
| 5 zoning authoring (corpus-gated) ⚠ | `feat/wave1-zoning-pgh` | maybe | Municode acquisition + attachments; biggest slice |
| 6 layers + derived vacancy | `feat/wave1-layers-vacancy` | maybe | B6 config-shaped for 3 markets |
| 7 verdicts + surfaces + parity gate | `feat/wave1-verdicts-gate` | no | v8 compute; literal sweep; parity report |
| 8 v9 bump (SEPARATELY GATED) | `feat/v9-bump-batch` | maybe | only on explicit approval |
