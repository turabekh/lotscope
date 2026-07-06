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

## Authoring coverage — pass 1 (residential), the deliverable table
`code_version='pgh-provisional-2026'`, cited to § 903.03. Buildability verified live (R1D-M→40 ft, RM-H→85 ft, R1A-VH→40 ft; citation "Pittsburgh Zoning Code").

| Field | Filled / 18 | Notes |
|---|---|---|
| max_height_ft | **18/18** | R1-R3 = 40 ft; RM = 40/40/55/85/180 by density |
| front/rear/side setback | **18/18** | side = interior sideyard (binding); other yards in `dimensional` note |
| min_lot_area_sqft | **14/18** | VL 6,000 · L 3,000 · M 2,400 · H 1,200; **VH NULL** (page-boundary, unconfirmed — not guessed) |
| min_lot_width_ft, max_occupancy_pct, max_units, FAR | 0/18 | not in the § 903.03 dimensional table — honestly NULL |
| permitted_uses | 0/18 | Use Table (§ 911.02) not yet parsed — pass 2 |

**Districts authored: 18 residential (R1D/R1A/R2/R3/RM × their density suffixes).** Not yet authored: ~22 non-residential (LNC/HC/GT-A..E/UI/EMI/RIV-* + P/H/AP/CP) — they resolve spatially but read "standards not loaded" until pass 2. **Authoring actuals for Baltimore calibration:** residential pass = 18 suffixed codes from a 573-page code, ~1 focused session; the density-subdistrict table structure (shared setbacks/height across base districts, varying by density) made it far more tractable than per-district authoring would suggest.

## Pass 2 flag determinations (§ 903.03 / § 911.02, page-context rule)
- **Flag 1 — VH min-lot:** the Very-High-Density Site Development Standards table has **no Minimum Lot Size row** (page 15 goes straight to setbacks). NULL is *correct* — the corpus states no VH lot-size floor (consistent with very-high-density infill), not a page artifact. Recorded, not filled.
- **Flag 2 — per-lot vs per-unit:** the "Minimum Lot Size" is a **single per-lot value per density subdistrict** (1,200 s.f. High applies to the whole subdistrict, not per base district), so it is a **per-lot minimum** — encoded as `min_lot_area_sqft`. Pittsburgh RM density is **envelope-governed**: § 903.03 has no minimum-lot-area-per-dwelling-unit rule (the only per-unit figure is a 450 s.f./unit *bonus* cap + the INTENSITY-OF-USE definition). So RM has no `lot_area_per_unit_sqft`; RM units are an **estimated capacity, never a firm by-right count**. This differs from Philadelphia's per-unit RM-1.
- **Flag 3 — by-right units (the deliverable):** derived from the district definition (§ 903 — Single/Two/Three/Multi-Unit): **R1D/R1A → 1, R2 → 2, R3 → 3** (firm `max_units`, verified live); **RM → NULL** (envelope-governed estimate). Primary residential use authored into `permitted_uses` from the district definition, cited. Buildability now answers height, setbacks, **and units**.
- **Min-lot-width sweep (Article IX + district intent):** the code states **no district-wide minimum lot width**; "Lot Width" appears only as a **use-permission condition** (R1A attached use if width ≤ 35 ft), not a dimensional floor. `min_lot_width_ft` NULL stands, noted.

## Recompute plan
Standards + units are a data correction against `pgh-provisional-2026` — **no version bump** (lot-area precedent). Buildability is lazy-on-view, so it reflects the new values immediately; the batch `pgh` verdict compute in Slice 7 picks them up at v8.

## Coverage v2 — after non-residential pass (page-context, header-matched)
**24 districts authored / 57 resolved codes → 68.6% of Pittsburgh parcels have standards.**
- **18 residential** (R1D/R1A/R2/R3/RM × densities) — height/setbacks/units, cited § 903.03.
- **6 non-residential** with clean § 904 tables: **LNC** (FAR 2:1, cov 90%, 45 ft), **NDO** (FAR 3:1, cov 90%, 45 ft), **GI** (FAR 3:1, 75 ft), **H/Hillside** (min-lot 3,200, 40 ft, 50% max disturbance), **GT-A/GT-B** (FAR 13 — Ord. 2022, estimated capacity). Non-residential carry no by-right dwelling count.

**Page-context rule caught two real traps this pass:** (1) the residential 3,000-vs-6,000 scramble; (2) the non-residential **page→district mis-mapping** (p17 "LNC" actually held the NDO table) — authored only from header-matched (`Site Development Standard <X> District`) full-table reads.

**Not yet authored (~33 codes, resolve but read "standards not loaded" — honest):** the remaining commercial/industrial with layout-varied tables that bulk extraction couldn't confirm field-complete (UNC, HC, NDI, UI, P) and the specialized planned districts (SP-*, GPR-*, UC-*, UPR-*, RIV-*, EMI, AP, CP, MTOBOR, R-MU, RP, GT-C/D/E). These need a focused per-district read — deferred rather than guessed, per the corpus gate.

**Authoring actuals (Baltimore):** 24 districts / ~68% parcel coverage from a 573-page code in ~1.x sessions; the density-subdistrict + §904 table structures were tractable, the specialized planned districts (a long tail) are the cost driver — budget them separately.
