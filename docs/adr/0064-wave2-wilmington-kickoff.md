# ADR-0064 — Wave 2: Wilmington kickoff

Status: accepted (2026-07-19)

## Context
Fourth market, and the **first outside Pennsylvania** — so the first that reuses none of the PA
data stack (OPA/PWD/RTT via Carto) and the first off the EPSG:2272 analysis plane. City of
Wilmington sits inside New Castle County (NCC), Delaware; parcels + assessment are county-provisioned,
statewide geometry is DE FirstMap. Reachability and dataset inventory are in `docs/wave2-nj-de-recon.md`
(Camden, NJ was audited in the same pass and **shelved** — its zoning is not published as
per-parcel GIS, a structural product hole). `launch_status='pilot'` at wave end; graduation is a
later effort. `VERDICT_VERSION` stays **v8** through Slice 7.

Wilmington clears the two bars Camden failed — **per-parcel zoning GIS exists** (24 differentiated
codes, verified live) and **owner names are public** (DE FOIA; no Daniel's Law). The critical path
therefore shifts away from zoning (which is the pgh risk) and onto two Wilmington-specific hazards:
NCC's public web tier is behind a **Link11 WAF (HTTP 471)** that blocks automated REST, and there
is **no bulk recorded-sales feed** analogous to `rtt_summary`.

## Decision
- **Scope & filter:** City of Wilmington only. FirstMap parcels are county-wide (203,757 NCC); filter
  to Wilmington by the NCC "hundred" district — parcel `PIN` prefix `26` (≈26,106 parcels, matches the
  zoning `ZONECODE` parcel count). Cross-check against the city-boundary polygon from the Wilmington
  ArcGIS org in Slice 2; keep a `coverage` field if the county fringe is revisited.
- **SRID (first non-2272 market):** analysis `geom_local` = **DE State Plane, NAD83 ftUS** (EPSG:2776
  per recon — **verify the exact SRID in Slice 2**, do not assume the 2272 no-op that hbg/pgh enjoyed);
  tiles 4326. This slice has genuine CRS work.
- **Market code & key:** market code **`wlm`**, slug `wilmington`. Key = FirstMap/NCC `PIN`, 10-digit
  numeric (e.g. `0600500019`; Wilmington = `26…`). `WlmKeyNormalizer` → `wlm:<PIN>`; golden files from
  real FirstMap samples (padding/prefix quirks captured in Slice 1).
- **Transports:** three, one of them new.
  - FirstMap ArcGIS REST (`DE_StateParcels/FeatureServer/0`) — parcel geometry (clean, public).
  - **NCC assessment via ArcGIS Hub bulk download** (GDB/Shapefile) parsed offline — NOT REST, because
    NCC's `.gov` tier (gis.nccde.org, www3.newcastlede.gov) is WAF-blocked. This is a **new
    transport pattern** (download-and-parse) the codebase does not yet have; a data-request fallback
    if the free GDB lacks value/sale fields.
  - Wilmington City ArcGIS org (`services.arcgis.com/hQ3wdpbjO3fPf612`) — zoning districts, land-bank
    side-lots, FEMA flood (all in the `LUP_Map…` service).
  - CivilView sheriff — reuse `sheriff_civilview.py` transport with `countyId=24` + a **per-county
    list-column map** (the PHL column order does not transfer; see recon).
- **Owner surfaces ON (unlike pgh):** owner name + mailing address are public (DE FOIA). Enable the
  Leads owner-dimension and owner-portfolio panel for `wlm`. (PII handling still per §13.)
- **Zoning:** resolve by centroid against the City Zoning polygon layer (24 codes), with the parcel
  `ZONECODE` as a cross-check — **normalize the `26` hundred-prefix** (`26R-3` → `R-3`) and clean stray
  values (`26R3`, `OR`). Ordinance text from Municode (`library.municode.com/de/wilmington`) for the
  `zoning_standard` table — browser-grade scrape, corpus-gated like pgh.
- **Assessment vintage:** DE court-ordered reassessment — NCC values are **FMV as of 2024-07-01**
  (ratio ≈ 1.0, not PA fractional assessment). `assessment_ratio` = **1.0** for `wlm`; implied market ≈
  assessed value. Record vintage in provenance; expect appeal churn.
- **Comps (proposed, STOP-gated):** MVP = the per-parcel **last-sale** fields from the NCC assessment
  GDB (price/date, MOD-IV-style), `assumptions_source='market_default'`. **STOP-gate:** if the free GDB
  carries no sale price, the comps slice escalates to a sourcing decision — licensed vendor
  (Regrid/ATTOM) vs Recorder DTS-PAXWorld scrape — before proceeding. No bulk transaction history in v1.
- **Distress & launch posture (proposed):** launch `wlm` as **pilot** with a **reduced distress
  stack** — sheriff/monition (CivilView) + DE state delinquent-taxpayer list + land-bank side-lots +
  FEMA flood — because Wilmington's **code-violation and vacancy records are portal-only**
  (BuildingBlocks/Tolemi, MUNIS) with no bulk export. Graduation to `live` is gated on adding a
  violations/vacancy source (a Tolemi/BuildingBlocks data agreement or FOIA feed). A **`wlm` distress
  scoring profile MUST be registered** in Slice 4 (precompute tripwire) and calibrated to the
  available signals; distress coverage is surfaced honestly (reduced) via capabilities.
- **Forced-sale label:** DE monition = **"Sheriff sale"** (phl "Sheriff sales" / hbg "Tax sales" /
  pgh "Treasurer's sale") via capabilities.
- **Capabilities:** owner surfaces ON; `zba_variance` hidden (DE BZA exists, no dataset); reduced
  distress coverage flagged; forced-sale surface under the `wlm` "Sheriff sale" label.
- **Recorder deep-link:** NCC Recorder / parcel-search template in the market row.
- **License ledger:** FirstMap, NCC, Wilmington, and CivilView terms each recorded in
  `docs/data-licenses.md` as loaded.

## Consequences
- **First real CRS work** — Slice 2 introduces DE State Plane; the 2272-assert pattern from hbg/pgh
  does not apply. Get the SRID right before geometry loads.
- **New download-and-parse transport** for NCC assessment (WAF); it becomes reusable infrastructure
  for future WAF-gated or bulk-file markets.
- **Comps are the critical path**, not zoning (the pgh inversion). If the GDB lacks prices, Wave 2
  stalls on a vendor/scrape decision — surface early.
- **Owner-side product is available** for the first time since phl — DE's public-record posture
  enables leads/skip-trace surfaces that pgh (3478-07) and hbg (no names) could not offer.
- **Distress is the weakest leg** — pilot launches without a Philly-grade "what's wrong with it"
  layer; the verdict leans on sheriff + tax + flood + land-bank until a violations/vacancy source is
  secured. This is the graduation gate.
- **Four-market regression** — phl + hbg + pgh golden parcels on every shared-code slice; `wlm`
  goldens added in Slice 7.

## Slice plan
0. **Kickoff** — this ADR + `docs/wave2-nj-de-recon.md` (done); register market (`Market` enum, slug→code
   map, `markets/seed` row with map center/bounds + recorder template); `wlm` distress-profile stub.
1. **Key normalizer** — `WlmKeyNormalizer` → `wlm:<PIN>`; golden files from real FirstMap samples.
2. **Parcels + SRID** — FirstMap parcel loader; DE State Plane analysis SRID (verify EPSG) + 4326 tiles;
   Wilmington `26`-hundred filter cross-checked against the city boundary; GiST indexes.
3. **Assessment + comps** — NCC Hub GDB download-and-parse loader: owner (public), FMV-2024 values,
   land use/class; per-parcel last-sale as MVP comps (**STOP-gate on missing price**).
4. **Distress** — sheriff (CivilView `countyId=24` + per-county parse map), DE delinquent-taxpayer list,
   land-bank side-lots, FEMA flood; **register + calibrate the `wlm` distress profile**.
5. **Zoning** — Wilmington City zoning districts (centroid resolve) + parcel `ZONECODE` (26-prefix
   normalize); Municode ordinance → `zoning_standard` (corpus-gated; STOP if compliant tooling impossible).
6. **Verdict** — compose `wlm` parcel verdict + provenance; owner surfaces ON; capabilities/labels.
7. **Parity gate + packet** — four-market regression, 25-parcel Wilmington packet, `launch_status='pilot'`,
   v8 unchanged.

## Addendum (2026-07-19) — Slice 3 source found; GDB/WAF path dropped, comps STOP-gate resolved

The Slice-3 STOP-gate investigation found that the **City of Wilmington ArcGIS org's own
parcels layer** (`LUP_Map…/FeatureServer/0`, "Wilmington Parcels", the same no-WAF org as zoning)
carries the full assessment + owner + sale payload, verified live across all 26,106 parcels:
`OWNER` 100%, `OWNRADD1` (mailing), `ASMTLAND` 99.7% + `ASMTSTRT` 92% (assessed land/structure),
`SALEPRC` 90.4% + `SALEYR`/`SALEMON` 94% (last-sale price + date), `PRCLID` 100% (10-digit key =
FirstMap PIN, joins to Slice-2 geometry), `PROP_CLASS` 99.1%, `ZONECODE` 100%.

Consequences that supersede the Decision above:
- **The NCC ArcGIS Hub GDB download-and-parse transport is dropped.** Slice 3 is a normal ArcGIS
  loader against the Wilmington City org — the NCC WAF is never touched. No new transport.
- **The comps STOP-gate is resolved in-source.** `SALEPRC` + `SALEYR`/`SALEMON` give per-parcel
  last-sale price + date; no licensed vendor or Recorder scrape. (Month/year granularity, one sale
  per parcel — full transaction history remains out of scope.)
- **Open decision #2 (comps sourcing) is closed** — answered by the source, not a purchase.
- Owner surfaces are confirmed viable (owner 100% populated, public).

## Open decisions to confirm at review
1. **Pilot without a Philly-grade distress layer?** (proposed: yes — reduced stack, graduation-gated).
2. **Comps sourcing** if the NCC GDB lacks prices — licensed vendor vs Recorder scrape (proposed: STOP-gate
   the comps slice and decide then).
3. **Scope** — City of Wilmington as Wave 2, Camden shelved (proposed: yes).
