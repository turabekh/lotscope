# Harrisburg graduation gate — evaluation

The conditions that must be green (or carry a recorded written waiver) before `hbg` flips `pilot → live`. Re-evaluated 2026-07-11 against prod DB/repo (session 26 reconciliation). **Result: NOT YET FLIPPABLE — 4 of 8 met; the other 4 are blocked on external / prod handoffs, not on code.** Every remaining blocker has its owner named; none require further build work.

## Scorecard

| # | Condition | State | Evidence / blocker |
|---|---|---|---|
| 1 | Standards verified; **reviewer sign-off recorded, cap lifted, hbg recomputed** at `hbg-2026-verified` | 🔴 **blocked** | Standards corpus-complete + cap-lift mechanism built (`make graduate-hbg-zoning`), but still `hbg-provisional-2026`. **Blocker (you): deliver the 25-parcel packet, record sign-off, then run the cap-lift.** |
| 2 | Corpus embedded; Ask-the-Parcel live with Harrisburg citations; cross-market isolation green | 🔴 **blocked** | 0 chunks embedded. **Blocker (you): run the embed-load when the Voyage quota resets** (buildability is unaffected). |
| 3 | Flood live; historic live; named-area (search) live | 🟢 **met** | Historic ✅ (7 districts) · named-area ✅ (20 neighborhoods) · **flood ✅ — 3,200 city `Flood_Parcels` zones loaded 2026-07-10 (session 21), risk scoring classifies 100/500-Year as SFHA/moderate, 180 hbg verdicts carry a flood flag** (`dataset_freshness.city_flood_parcels` 2026-07-11). |
| 4 | Repository wired (live); upset/judicial pipeline armed | 🟢 **met (repository)** | Repository list LIVE — 191 city parcels loaded from the 2026-06-25 CSV (normalized from the county PDF); dossier badge + Tax-sales repository tab live; monthly prod-origin refresh job registered (dev reads the committed CSV fixture). Upset/judicial pipeline still armed for the August list. |
| 5 | Comps at best-available; **coverage reported** | 🟢 **met** | Reported (`hbg-comps-coverage.md`): 0 priced sales / 0 value estimates — the honest ceiling; AVM degrades correctly, weights not renormalized. |
| 6 | Violations pipeline built; **RTKL filed** | 🟡 **partial** | Pipeline built + fixture-tested ✅; RTKL request drafted. **Blocker (you): file the RTKL request; on delivery, load + flip the note.** |
| 7 | Checklist states truthful everywhere; **RCO structural removal in**; forced-sale surface market-aware | 🟢 **met** | Distinct `no_data_source` / `pending_load` states ✅; RCO removed for hbg ✅; sheriff/tax-sale surface market-scoped + labelled ✅ (surface stays hidden until data — honest). |
| 8 | Full hbg recompute at final data; **full Philadelphia regression**; `VERDICT_VERSION` still v8 | 🟢 **met** | 19,502 hbg verdicts @ v8 ✅; Philadelphia byte-unchanged across all 7 slices ✅. |

## What "not flippable" means here
Nothing in the remaining blockers is a defect or missing code — the pipelines, adapters, cap-lift, and surfaces are **all built and tested**. hbg is gated purely on **data that cannot be reached from the build environment** (Dauphin tax-claim, the eCode360 use-table attachment, the Voyage embed quota) plus **two human actions** (reviewer sign-off, filing the RTKL). When those land, the flip is mechanical. (Flood cleared 2026-07-10 via the city GIS `Flood_Parcels` layer — not FEMA NFHL, which stays unreachable.)

## The flip (Slice 7 tail — held until the gate is green + you approve)
When green: `market.launch_status hbg pilot → live`; pilot badge off; header "Harrisburg · city data"; minimal two-market landing copy (factual — the "LotScope PHL" brand question stays out of scope). Post-deploy pass: Harrisburg dossier end-to-end incl. PDF, tax-sales page, an Ask-the-Parcel answer with citation, market-switcher round-trip, Philadelphia regression, next-morning `ingest_market('hbg')` green.

## Handoff summary (to reach `live`)
1. **Reviewer sign-off** on the 25-parcel packet → `make graduate-hbg-zoning CONFIRM=--confirm` (lifts the cap). *(gate row 1)*
2. **Corpus embed-load** when Voyage resets → Ask-the-Parcel live. *(gate row 2)*
3. **Dauphin tax-claim** from prod / provided PDFs → un-hide the Tax-sales surface.
4. **Use-table attachment** (§7-305.7) → by-right *use* determinations.
5. **File the RTKL** → violations pipeline receives data. *(gate row 6)*

~~Flood from prod~~ — **DONE 2026-07-10** (3,200 city `Flood_Parcels` zones; gate row 3 now met).

Items 3–4 also enable the deal panel to move from "market default" to calibrated assumptions once you supply Harrisburg construction $/sqft after the reviewer session.
