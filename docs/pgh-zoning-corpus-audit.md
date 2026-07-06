# Pittsburgh Zoning Code — corpus completeness audit (Slice 5b, Step 1)

Delivered to `backend/corpus/pgh/` (gitignored):
1. **Title Nine main export** — 573 pp, 1.44M chars: Introduction/Establishment, Base Zoning Districts, Overlay Districts, Planning Districts, Use Regulations, Development Standards, Nonconformities, Review/Enforcement, Measurements & Definitions.
2. **PI6865-009a SP-10 Appendix** — 13 pp: the SP-10 specially-planned district use table (supplementary).

## Audit result — PASS (no material gaps)
| Component | Present | Extractable |
|---|---|---|
| Base districts (residential R1D/R1A/R2/R3/RM; commercial LNC/HC; downtown GT-A..E; industrial UI/EMI; riverfront RIV-*) | ✅ | ✅ |
| **Development (dimensional) standards** | ✅ | ✅ per-page (§903.03 residential density subdistricts; §125/129/138 non-residential tables) |
| Use Regulations / Use Table (§911.02) | ✅ | matrix — confirm at load |
| Measurements & Definitions | ✅ | ✅ |
| SP-10 Appendix table | ✅ | ✅ |

**Extraction-fidelity finding:** pypdf's *linear* text scrambles the density↔value pairing (a concatenated regex mis-associates values), but **per-page extraction is reliable**. Authoring must read each subdistrict table from its own page — done for residential (pages 11–15).

## Confirmed residential dimensional standards (verbatim, per-page)
Residential standards are stated by **density subdistrict** (the code suffix), with one column for "R1D, R1A, R2 & R3" and a separate "RM" column. GIS codes map (base, density) → the matching column.

| Density (suffix) | Min Lot | Front (R1D-R3 / RM) | Rear (R1D-R3 / RM) | Ext side | Int side (R1D-R3 / R1A / RM) | Max Height (R1D-R3 / RM) |
|---|---|---|---|---|---|---|
| Very-Low (VL) | 6,000 s.f. | 30 / 30 | 30 / 30 | 30 / 30 | 5–10 / 5 / 30 | 40 ft 3 st / 40 ft 3 st |
| Low (L) | 6,000 s.f. | 30 / 30 | 30 / 25 | 30 / 30 | 5 / 5 / 25 | 40 ft 3 st / 40 ft 3 st |
| Moderate (M) | 2,400 s.f. | 30 / 25 | 30 / 25 | 30 / 25 | 5 / 5 / 10 | 40 ft 3 st / 55 ft 4 st |
| High (H) | 1,200 s.f. | 15 / 25 | 15 / 25 | 15 / 25 | 5 / 5 / 10 | 40 ft 3 st / 85 ft 9 st |
| Very-High (VH) | *confirm* | 5 / 25 | 15 / 25 | 5 / 25 | 5 / 5 / 10 | 40 ft 3 st / 180 ft |

Cited to §903.03 (each density subdistrict's Site Development Standards table). VH min-lot lands on a page boundary — read carefully or NULL it. Non-residential (commercial/downtown/industrial/riverfront) tables are on later pages — a second authoring pass.

## Authoring plan (Step 3, on go-ahead)
- `zoning_standard` rows keyed by the **full resolved GIS code** (`R1D-VL`, `R1A-H`, `RM-M`, …), `market='pgh'`, `code_version='pgh-provisional-2026'`.
- Corpus-stated values only; **NULL every unconfirmed field** (VH min-lot, density/units where not cleanly stated, non-residential until pass 2).
- `land_use_class` for pgh prefixes derived from the district *definitions* (R1/R2/R3/RM = residential; LNC/HC = commercial; UI/EMI = industrial/institutional), not inferred from letters.
- Coverage table (Step 4) reported before merge.
