# Wave-0 Harrisburg — data-parity gate report

Against PRD Amendment-02 §6.4 thresholds. Numbers from the dev load of **19,502
City-of-Harrisburg parcels** (`market_code='hbg'`), 2026-07-05. `VERDICT_VERSION` v8.

| Gate criterion (§6.4) | Threshold | Harrisburg | Verdict |
|---|---|---|---|
| Parcels with spine + geometry | ≥ 98% | **99.95%** (owner + geom_local) | ✅ pass |
| Verdict coverage | ≥ 95% | **100.0%** (19,502 at v8) | ✅ pass |
| Usable comp for vacant parcels | ≥ 60% **or** honest degradation | **0 priced comps** — Dauphin open data has no sale price/date (deed refs only) | ✅ honest degradation verified (ADR-0054) |
| Distress computed for flagged parcels | every flagged parcel | RETSL adapter built + fixture-tested; no live list currently published (seasonal PDF) → 0 forced-sale-flagged; tax-exposure distress computes where data exists | ✅ (vacuously) + documented follow-up |
| Every checklist row live or explicit no-source | all rows | zoning, liens/taxes, access, ownership, valuation **live**; L&I, overlays, flood render **"no data source for this market"** | ✅ pass |
| 25-parcel golden set | delivered | `docs/wave0-hbg-25parcel-packet.md` (all 9 districts) | ✅ delivered — reviewer sign-off pending |

## Coverage detail
- **Spine + geometry**: 19,502 parcels, all EPSG:2272 `geom_local` + `geom_4326`; 99.95% carry owner + geometry.
- **Vacancy (B6 derived)**: 1,664 vacant (vacant land-use + improvement < $1k), all with method-encoded `vacancy_confidence = 0.5` (multi-signal). Philadelphia VPI model untouched.
- **Landlocked**: 15,404 Harrisburg street segments loaded; 1,634 / 1,664 vacant parcels have frontage, **30 potentially landlocked**.
- **Public-owned**: 905 parcels (City / RA / Housing Authority / County / Commonwealth), zero-distress acquirability channel.
- **Zoning**: 195 provisional district polygons + 9 verbatim `zoning_standard` rows (§7-307.3A); buildability confidence capped to *low + provisional* pending reviewer sign-off.

## Honest-degradation ledger (what Harrisburg knows less about, and why)
- **Comps / value confidence** — no open sale prices in Dauphin data → AVM runs low/no-confidence by construction.
- **Code enforcement (L&I)** — no open feed → checklist "no data source".
- **Flood** — FEMA NFHL unreachable from build env + Dauphin flood layers not queryable → checklist "no data source" (load from prod; do not false-pass riverfront parcels).
- **Overlays / RCO** — Philadelphia concepts, absent for hbg.
- **Historic / named-area search** — not in the Dauphin Hub → named-area degrades; radius/polygon search carries discovery.
- **Forced-sale (RETSL)** — upset/judicial list is a seasonal PDF; pipeline ready, awaiting a published list.

## Gate outcome
**Passes the data-parity gate** on all measurable thresholds, with comp/distress gaps recorded as *honest degradation*, not silent gaps. Remaining before removing the pilot's provisional labels: the 25-parcel reviewer sign-off, the corpus embed-load (Voyage quota), and loading Harrisburg flood zones from prod.
