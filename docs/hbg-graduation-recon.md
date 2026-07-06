# Harrisburg graduation — Slice-0 recon, audit & plan

Graduating `hbg` pilot → live. Audited 2026-07-06 against the repo/DB. Invariants hold: `VERDICT_VERSION` v8 (data changes only), corpus gate absolute, honest states over green, no paid acquisition without owner approval.

## [A] Open-items audit (current state, from DB/freshness)

| Parity-gate open item | State now | Evidence |
|---|---|---|
| Corpus embed-load | **still open** — 0 embedded | `document` has 0 `source='zoning' market='hbg'` chunks (JSONL exists, Voyage 429 blocked) |
| Flood zones loaded | **still open** — 0 rows | `flood_zone` has 0 `market_code='hbg'` |
| RETSL tax-sale lists | **still open** — not wired | no `dc_tax_claim` freshness row; adapter fixture-tested only |
| 25-parcel reviewer packet | **generated, not delivered/signed** | `docs/wave0-hbg-25parcel-packet.md` exists (3.2 KB) |

hbg verdicts: **19,502 @ v8** (100%). Loaded feeds: dc_parcels, dc_deed_references, dc_streets, derived_vacancy, public_ownership, tcrp_zoning_districts.

## [A] Checklist-state taxonomy (drives Slice 1)

Current `hbg` "no data source" set = `{li, overlays, flood}`. `overlays` conflates three concepts that classify differently:

| Checklist concept | Class | Action |
|---|---|---|
| `li` (code enforcement / violations) | **(a) truly-no-source** | keep `no_data_source`; note "requested under PA RTKL" once Slice-6 letter is filed; build pipeline ahead of data |
| `flood` | **(b) pending-load** | load FEMA NFHL (Slice 3) → `pending_load` → live |
| `historic_district` | **(b) pending-load** | **city GIS has Municipal + National Historic Districts** → load (Slice 3) → live |
| named-area search | **(b) pending-load** | **city GIS has Wards + Neighborhood Organizations** → load (Slice 3) → named search live |
| `overlay_district` | **(b) pending-load / corpus** | Harrisburg has overlays (Title 7 §7-313/315/317/319); encode from corpus or locate a layer, else keep truthful |
| `rco` (Registered Community Org) | **(c) structurally-inapplicable** | RCO is a Philadelphia Title-14 construct — **remove the row for `hbg`** (not a gap) |
| upset/judicial tax sale | **(d) seasonal** | arm the pipeline (Slice 4); Sept-2026 list flows in on schedule |
| repository sale | **live-able now** | list published as PDF → load (Slice 4) |

## [B] Web investigation (sources → `docs/data-licenses.md` in the loading slice)

- **Dauphin Tax Claim repository list — published PDF, year-round.** `dauphincounty.gov/docs/default-source/tax-assessments/tax-claim/updated-repository-list.pdf` (+ a master repo PDF). $2,000 min bid. → **Slice 4 loads it now** (ExtractClient + PDF parse).
- **Upset/judicial lists** — seasonal PDF (Sept 2026 upset; judicial per calendar). → **Slice 4 arms the parser + scheduled ingest**; flows in on publication.
- **Sales depth** — **STEB/DCED publishes only the aggregate Common Level Ratio, not raw county sales** (`dced.pa.gov/.../tax-equalization-division`). County sales exist only at the **Dauphin Recorder of Deeds (Landex/Acclaim)** — online search is free (`deeds.dauphincounty.gov/AcclaimWeb`) but **bulk export is a paid Landex subscription** (contact 717-780-6560 / jzugay@dauphincounty.gov; no public price). → **Slice 5 = Track C handoff** (report cost/terms, load nothing without approval); thin comps remain honest until then.
- **City of Harrisburg GIS DataHub** (`harrisburg-open-data-cohbg.opendata.arcgis.com`, `services5.arcgis.com/9n3LUAMi3B692MBL`): **Municipal Historic Districts** (7), **National Historic Districts**, **Wards** (15), **Neighborhood Associations** (20), a city **Zoning** layer (7 dissolved polygons, full names — coarser than TCRP's 195; use as cross-check, not replacement). → **Slice 3** loads historic + wards + neighborhoods.
- **Violations RTKL** — City of Harrisburg **Office of the City Solicitor** (10 N Second St, Suite 402) is the open-records path; online form `laserfiche.harrisburgpa.gov/Forms/Righ-to-Know-Request`, policy PDF on harrisburgpa.gov. → **Slice 6 = Track C letter** to the City Solicitor / Open Records Officer.

## Per-item plans (A/B/C)
- **Checklist states + RCO removal** → Slice 1 **[A]**.
- **Corpus embed + standards verification + reviewer packet + cap-lift mechanism** → Slice 2 **[A]**, packet delivery **[C]**, cap-lift executes only on your sign-off.
- **Flood + historic + wards/neighborhoods** → Slice 3 **[A]** (all sources located).
- **Repository (now) + upset/judicial (armed) + market-aware Tax-sales surface** → Slice 4 **[A]**.
- **Comps depth** → Slice 5 **[B]** done (STEB no raw sales; Recorder bulk paid) → **[C]** handoff options/cost; load nothing; report coverage ceiling.
- **Violations pipeline built + RTKL letter** → Slice 6 **[A]** pipeline, **[C]** letter to City Solicitor.
- **Deal calibration + graduation flip** → Slice 7 **[C→A]** + **[A]**.

## Draft graduation-gate checklist (finalized in Slice 7 as `docs/hbg-graduation-gate.md`)
Required green (or a recorded written waiver):
1. Standards verification pass complete; **reviewer sign-off recorded, cap lifted, `hbg` recomputed at `hbg-2026-verified`**.
2. Corpus embedded; Ask-the-Parcel live with Harrisburg citations; cross-market isolation green.
3. Flood live; historic live; wards/neighborhoods live (named search) — or truthful classification recorded.
4. Repository wired (live); upset/judicial pipeline armed on schedule.
5. Comps at best-available; **coverage numbers reported** (whatever they are).
6. Violations pipeline built; **RTKL filed** (you confirm).
7. Checklist states truthful everywhere; **RCO structural removal in**; forced-sale surface = market-aware "Tax sales".
8. Full `hbg` recompute at final data; **full Philadelphia regression pass**; `VERDICT_VERSION` still v8.

## Slice plan
| Slice | Branch | Files (indicative) | Migration? | Tests | Primary risk |
|---|---|---|---|---|---|
| 1 checklist states + RCO removal | `feat/hbg-grad-checklist-states` | checklist/schemas+logic, markets/capabilities, ai/prompts | maybe (status enum) | per-state render + phl regression | phl checklist output drift |
| 2 corpus + standards verify + packet + cap-lift | `feat/hbg-grad-zoning-verify` | ai/corpus run, zoning seed_hbg, cap-lift target, packet doc | no | coverage table, retrieval isolation, phl golden | Voyage quota; corpus-gate discipline |
| 3 flood + historic + wards/neighborhoods | `feat/hbg-grad-layers` | loaders/hbg (+ historic/neighborhoods), jobs, flood | maybe | loader fixtures; phl untouched | FEMA NFHL reachability; SR 3857 transforms |
| 4 repository + upset/judicial + Tax-sales surface | `feat/hbg-grad-retsl` | hbg_taxclaim loader, capabilities surface, frontend | maybe | parser fixtures, adapter, phl sidebar regression | PDF format variance |
| 5 comps depth | `feat/hbg-grad-sales-depth` | (loader or handoff), coverage report | maybe | dedup/coverage | paid-source gate (no load) |
| 6 violations pipeline + RTKL | `feat/hbg-grad-violations-pipeline` | violations loader (fixture) + flag wiring, RTKL letter | maybe | fixture loader + flag | unknown response format |
| 7 calibration + graduation flip | `feat/hbg-grad-launch` | market row (launch_status), deal overrides, gate doc, landing copy | yes (launch_status update) | gate eval, phl regression, e2e | premature flip |
