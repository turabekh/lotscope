# Wave-1 Pittsburgh — data-parity gate report

Against PRD Amendment-02 §6.4 thresholds. Numbers from the dev load of **143,355
City-of-Pittsburgh parcels** (`market_code='pgh'`), 2026-07-07. `VERDICT_VERSION` v8.

| Gate criterion (§6.4) | Threshold | Pittsburgh | Verdict |
|---|---|---|---|
| Parcels with spine + geometry | ≥ 98% | **99.93%** (143,257 / 143,355 with `geom_local`) | ✅ pass |
| Verdict coverage | ≥ 95% | **100.0%** (143,355 / 143,355 at v8) | ✅ pass |
| Usable comp for vacant parcels | ≥ 60% **or** honest degradation | **3 validated vacant-land sales in the 3-yr window** (83 all-time; VALID-SALE filter) — AVM runs low/no-confidence for vacant land by construction | ✅ honest degradation |
| Distress computed for flagged parcels | every flagged parcel | 24,497 tax-delinquent, 959 Treasurer's-sale (foreclosure filings), 149 L&I-violation parcels, 12,464 city-owned — all scored | ✅ pass |
| Every checklist row live or explicit no-source | all rows | zoning, liens/taxes, L&I, ownership, valuation, deal **live**; flood, access, overlays render **"not yet loaded for Pittsburgh"** (honest pending) | ✅ pass |
| 25-parcel golden set | delivered | `docs/wave1-pgh-25parcel-packet.md` (all 24 authored districts) | ✅ delivered — reviewer sign-off pending |

## Coverage detail
- **Spine + geometry**: 143,355 parcels (assessment spine); 143,257 carry EPSG:2272 `geom_local` + `geom_4326` (99.93%). Lot area from stated `LOTAREA` (`lot_area_source='extract'`).
- **Vacancy (derived)**: 22,438 vacant (assessor `land_use` in {VACANT LAND, VACANT COMMERCIAL LAND, VACANT INDUSTRIAL LAND, >10 ACRES VACANT} with improvement < $1k), all `vacancy_confidence = 0.5`.
- **Zoning**: deterministic majority-area district resolution (ADR-0056); 24 authored `zoning_standard` rows (`pgh-provisional-2026`, §903.03/904/907) → 68.6% of parcels carry standards; buildability answers height + setbacks + by-right units, capped **low + provisional** pending reviewer sign-off.
- **Neighborhoods**: 90 loaded; market intelligence (vacant lots / distress per neighborhood) live and market-scoped.
- **Distress**: tax delinquency (24,497), Treasurer's-sale flag from foreclosure filings (959), L&I violations (149 parcels), city-owned inventory (12,464).

## Honest-degradation ledger (what Pittsburgh knows less about, and why)
- **Comps / value confidence** — assessor VALID-SALE set is strong for *built* property but has only 83 vacant-land sales all-time (3 in the default 3-yr window) → vacant-land AVM runs low/no-confidence by construction. A per-market comp window / fallback is a valuation follow-up (widening to 5 yr reaches only 16 sales — does not change the gate).
- **Flood** — no Allegheny/FEMA-NFHL source wired from the build env → checklist "not yet loaded"; do not false-pass riverfront parcels.
- **Access / landlocked** — no street-centerline source loaded → the low-severity `no_street_access` flag is suppressed for pgh (gated on street-data availability, so parcels are not blanket-penalized) and the checklist reads "street data not yet loaded".
- **Historic / overlays** — no reachable historic-district or zoning-overlay source catalogued → checklist "not yet loaded" (not false-cleaned). Latent market literals that would surface only once this data loads: overlay flag cites "Title 14 §14-500" and historic flag cites "Philadelphia Historical Commission" — both to be market-scoped when pgh overlay/historic data is loaded.
- **Owner surfaces** — Ordinance 3478-07 + the WPRDC assessment feed carries no owner names (type codes only) → owner-dimension leads and the owner-portfolio panel are off for pgh (memo `docs/pgh-ordinance-3478-07-memo.md`).

## Market-literal sweep
Swept the composed pgh verdict + checklist + risk output. One manifesting leak fixed (overlays clear-detail: RCO literal + historic false-clean → honest pending). Flag-level literals (Title 14 overlay, Philadelphia Historical Commission, OPA abatement, RCO flag) do not manifest — pgh carries no overlay / historic / exemption / RCO data to trigger them — and are recorded above as fix-when-data-loads.

## Gate outcome
**Passes the data-parity gate** on all measurable thresholds, with comp/flood/access/overlay gaps recorded as *honest degradation*, not silent gaps. Remaining before removing the pilot's provisional labels: the 25-parcel reviewer sign-off (§903.03 standards), and loading Pittsburgh flood zones, street centerlines, and historic/overlay districts from reachable sources.
