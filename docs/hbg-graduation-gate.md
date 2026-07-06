# Harrisburg graduation gate — evaluation

The conditions that must be green (or carry a recorded written waiver) before `hbg` flips `pilot → live`. Evaluated 2026-07-06 against the DB/repo. **Result: NOT YET FLIPPABLE — 3 of 8 met; the other 5 are blocked on external / prod handoffs, not on code.** Every remaining blocker has its owner named; none require further build work.

## Scorecard

| # | Condition | State | Evidence / blocker |
|---|---|---|---|
| 1 | Standards verified; **reviewer sign-off recorded, cap lifted, hbg recomputed** at `hbg-2026-verified` | 🔴 **blocked** | Standards corpus-complete + cap-lift mechanism built (`make graduate-hbg-zoning`), but still `hbg-provisional-2026`. **Blocker (you): deliver the 25-parcel packet, record sign-off, then run the cap-lift.** |
| 2 | Corpus embedded; Ask-the-Parcel live with Harrisburg citations; cross-market isolation green | 🔴 **blocked** | 0 chunks embedded. **Blocker (you): run the embed-load when the Voyage quota resets** (buildability is unaffected). |
| 3 | Flood live; historic live; named-area (search) live | 🟡 **partial** | Historic ✅ (7 districts, 3,657 parcels) · named-area ✅ (20 neighborhoods) · **flood 🔴 (0 rows) — blocker: FEMA NFHL unreachable from build; run from prod.** |
| 4 | Repository wired (live); upset/judicial pipeline armed | 🟢 **met (repository)** | Repository list LIVE — 191 city parcels loaded from the 2026-06-25 CSV (normalized from the county PDF); dossier badge + Tax-sales repository tab live; monthly prod-origin refresh job registered (dev reads the committed CSV fixture). Upset/judicial pipeline still armed for the August list. |
| 5 | Comps at best-available; **coverage reported** | 🟢 **met** | Reported (`hbg-comps-coverage.md`): 0 priced sales / 0 value estimates — the honest ceiling; AVM degrades correctly, weights not renormalized. |
| 6 | Violations pipeline built; **RTKL filed** | 🟡 **partial** | Pipeline built + fixture-tested ✅; RTKL request drafted. **Blocker (you): file the RTKL request; on delivery, load + flip the note.** |
| 7 | Checklist states truthful everywhere; **RCO structural removal in**; forced-sale surface market-aware | 🟢 **met** | Distinct `no_data_source` / `pending_load` states ✅; RCO removed for hbg ✅; sheriff/tax-sale surface market-scoped + labelled ✅ (surface stays hidden until data — honest). |
| 8 | Full hbg recompute at final data; **full Philadelphia regression**; `VERDICT_VERSION` still v8 | 🟢 **met** | 19,502 hbg verdicts @ v8 ✅; Philadelphia byte-unchanged across all 7 slices ✅. |

## What "not flippable" means here
Nothing in the remaining blockers is a defect or missing code — the pipelines, adapters, cap-lift, and surfaces are **all built and tested**. hbg is gated purely on **data that cannot be reached from the build environment** (FEMA NFHL, Dauphin tax-claim, the eCode360 use-table attachment) plus **two human actions** (reviewer sign-off, filing the RTKL). When those land, the flip is mechanical.

## The flip (Slice 7 tail — held until the gate is green + you approve)
When green: `market.launch_status hbg pilot → live`; pilot badge off; header "Harrisburg · city data"; minimal two-market landing copy (factual — the "LotScope PHL" brand question stays out of scope). Post-deploy pass: Harrisburg dossier end-to-end incl. PDF, tax-sales page, an Ask-the-Parcel answer with citation, market-switcher round-trip, Philadelphia regression, next-morning `ingest_market('hbg')` green.

## Handoff summary (to reach `live`)
1. **Reviewer sign-off** on the 25-parcel packet → `make graduate-hbg-zoning CONFIRM=--confirm` (lifts the cap).
2. **Corpus embed-load** when Voyage resets → Ask-the-Parcel live.
3. **Flood from prod** (FEMA NFHL) → flood live.
4. **Dauphin tax-claim** from prod / provided PDFs → un-hide the Tax-sales surface.
5. **Use-table attachment** (§7-305.7) → by-right *use* determinations.
6. **File the RTKL** → violations pipeline receives data.

Items 3–5 also enable the deal panel to move from "market default" to calibrated assumptions once you supply Harrisburg construction $/sqft after the reviewer session.
