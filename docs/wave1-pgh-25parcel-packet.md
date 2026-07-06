# Wave-1 Pittsburgh — 25-parcel zoning verification packet

Provisional Pittsburgh zoning (`pgh-provisional-2026`; dimensional standards + by-right units authored from Title Nine § 903.03 residential and § 904/907 non-residential — see `docs/pgh-zoning-corpus-audit.md`). This packet is the human-review gate before the provisional standards are trusted for production verdicts.

**What to do:** for each parcel, open Pittsburgh's official zoning map (OneStopPGH / ZoneView, or the city zoning GIS), look up the parcel, and record the mapped base district in **City map district**; mark **Agree?** (Y/N) on the district assignment; note any dimensional/unit disagreement in **Notes**. Escalate any disagreement — a wrong district propagates into every downstream verdict field.

## Status of this read
- **District resolution is now deterministic** (ADR-0056, merged main `4a756f2`): resolved by majority overlap area among containing polygons, not arbitrary row order. Every district below is stable run-to-run.
- **Buildability answers height, setbacks, and by-right units.** The read shown is the live `assess_parcel` output.
- **"needs variance"** appears where the lot is below the district minimum lot size (e.g. R2 min-lot 2,400 s.f., R3-L 3,000 s.f.) or the use is not permitted by-right — this is expected product behavior on sub-minimum lots, not an error, but confirm the min-lot figure against the map/code.
- **Provisional cap:** until a Pittsburgh land-use reviewer signs off this packet, pgh buildability stays provisional (`pgh-provisional-2026`) and carries the provisional caveat in-product; standards are not lifted to a trusted code version.

## Flag-2 (RM) validation — the key thing to check
Rows 13–17 are **RM (Multi-Unit Residential)**. Their **By-right units** column reads **"—" by design**: Pittsburgh RM density is envelope-governed — § 903.03 has no minimum-lot-area-per-dwelling-unit rule, so RM units are an estimated, envelope-bounded capacity, **never a firm by-right count** (unlike Philadelphia RM-1). Confirm that no RM parcel is being handed a firm unit number. The height ladder by RM density (RM-M 55 ft, RM-H 85 ft, RM-VH 180 ft — rows 14–17) is the authored § 903.03 value; sanity-check it against the code.

## Packet

| # | Parcel | Address | District | Use (class) | Lot sqft | By-right units | Our read | Cited | City map district | Agree? | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | pgh:0018A00286000000 | JEROME ST | R1D-VL | vacant (VACANT LAND) | 8,487 | 1 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | |
| 2 | pgh:0010N00114000001 | SWEENEY WAY | R1D-L | vacant (VACANT LAND) | 3,600 | 1 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | |
| 3 | pgh:0003N00185000000 | MCLAIN ST | R1D-M | vacant (VACANT LAND) | 3,683 | 1 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | |
| 4 | pgh:0001J00006000000 | LABELLE ST | R1D-H | vacant (VACANT LAND) | 3,200 | 1 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | |
| 5 | pgh:0005P00050000000 | TROPICAL AVE | R1A-M | vacant (VACANT LAND) | 6,840 | 1 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | |
| 6 | pgh:0006G00069000000 | SHALER ST | R1A-H | vacant (VACANT LAND) | 1,928 | 1 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | |
| 7 | pgh:0003H00237000000 | MURIEL ST | R1A-VH | vacant (VACANT LAND) | 88 | 1 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | ⚠ 88 s.f. lot — data sanity-check |
| 8 | pgh:0013J00140000000 | WAITE ST | R2-L | vacant (VACANT LAND) | 302 | 2 | needs variance; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | ⚠ 302 s.f. lot — below min |
| 9 | pgh:0013J00009000000 | SAINT PATRICK ST | R2-M | vacant (VACANT LAND) | 1,721 | 2 | needs variance; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | below R2-M min-lot 2,400 |
| 10 | pgh:0004A00199000000 | BERTHA ST | R2-H | vacant (VACANT LAND) | 2,030 | 2 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | |
| 11 | pgh:0082P00225000000 | N NEGLEY AVE | R3-L | vacant (VACANT COMMERCIAL LAND) | 2,500 | 3 | needs variance; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | below R3-L min-lot 3,000 |
| 12 | pgh:0028K00018000000 | COLTART AVE | R3-M | built (THREE FAMILY) | 2,480 | 3 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | 3-family on R3 — confirm |
| 13 | pgh:0039F00340000000 | BRETT ST | RM-VL | vacant (VACANT LAND) | 71,003 | — | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | RM — units estimated (Flag-2) |
| 14 | pgh:0002D00313000000 | ROBERTS ST | RM-M | vacant (VACANT COMMERCIAL LAND) | 2,000 | — | needs variance; ht 55ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | RM — units estimated (Flag-2) |
| 15 | pgh:0002H00303000000 | REED ST | RM-M | vacant (VACANT LAND) | 5,068 | — | by-right; ht 55ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | RM — units estimated (Flag-2) |
| 16 | pgh:0010M00215000000 | CENTRE AVE | RM-H | vacant (VACANT COMMERCIAL LAND) | 2,800 | — | by-right; ht 85ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | RM — units estimated (Flag-2) |
| 17 | pgh:0026R00156000000 | BIGELOW BLVD | RM-VH | vacant (VACANT COMMERCIAL LAND) | 29,173 | — | by-right; ht 180ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | RM — units estimated; ht 180ft |
| 18 | pgh:0003G00031000000 | E CARSON ST | LNC | vacant (VACANT COMMERCIAL LAND) | 2,569 | — | by-right; ht 45ft | Pittsburgh Zoning Code § 904.02 (pgh-provisional-2026) | | | non-res — no dwelling count |
| 19 | pgh:0003G00171000000 | S 11TH ST | LNC | vacant (VACANT LAND) | 1,200 | — | by-right; ht 45ft | Pittsburgh Zoning Code § 904.02 (pgh-provisional-2026) | | | non-res — no dwelling count |
| 20 | pgh:0008A00173000000 | RIDGE AVE | NDO | built (OFFICE-WALKUP -3 + STORIES) | 4,025 | — | by-right; ht 45ft | Pittsburgh Zoning Code § 904.01 (pgh-provisional-2026) | | | non-res — no dwelling count |
| 21 | pgh:0031C00082000000 | BECKS RUN RD | GI | vacant (VACANT COMMERCIAL LAND) | 4,370 | — | by-right; ht 75ft | Pittsburgh Zoning Code § 904.06 (pgh-provisional-2026) | | | non-res — no dwelling count |
| 22 | pgh:0002M00155000000 | LOCUST ST | H | vacant (VACANT COMMERCIAL LAND) | 17,424 | — | by-right; ht 40ft | Pittsburgh Zoning Code § 904 Hillside (pgh-provisional-2026) | | | Hillside — verify overlay vs base |
| 23 | pgh:0001D00153000000 | MARKET ST | GT-A | vacant (VACANT COMMERCIAL LAND) | 3,438 | — | by-right; ht —ft | Pittsburgh Zoning Code § 907 (pgh-provisional-2026) | | | Golden Triangle — FAR-governed |
| 24 | pgh:0002A00242000000 | WILLIAM PENN PL | GT-B | built (HOTELS) | 45,570 | — | by-right; ht —ft | Pittsburgh Zoning Code § 907 (pgh-provisional-2026) | | | Golden Triangle — FAR-governed |
| 25 | pgh:0012M00081000000 | S 27TH ST | R2-VH | vacant (VACANT LAND) | 1,425 | 2 | by-right; ht 40ft | Pittsburgh Zoning Code § 903.03 (pgh-provisional-2026) | | | below-ish min — confirm |

## Coverage of this sample
- **18 residential rows** across all 5 base districts and all 5 density subdistricts present in the layer: R1D (VL/L/M/H), R1A (M/H/VH), R2 (L/M/H/VH), R3 (L/M), RM (VL/M/H/VH). Firm by-right units verified: **R1D/R1A → 1, R2 → 2, R3 → 3**.
- **5 RM rows** (13–17) exercising the Flag-2 envelope-estimate call and the RM height ladder (40/55/85/180 ft by density).
- **7 non-residential rows** — LNC (×2), NDO, GI, H (Hillside), GT-A, GT-B — the six authored § 904/907 districts; all read no by-right dwelling count.
- Mix of vacant and built; several deliberately sub-minimum lots to exercise the variance path.

## Handoff / next steps
1. **Reviewer fills City map district + Agree? + Notes** against the official Pittsburgh zoning map. Focus disagreements on the district assignment first (highest-leverage), then the dimensional/unit reads.
2. **Row 22 (H / Hillside):** confirm whether the map treats Hillside as the base district or as an overlay over an underlying base — this feeds the open overlay-stacking follow-up (ADR-0056). If Hillside is an overlay in the official map, these parcels have a base district underneath that our resolver is not yet surfacing.
3. **Data sanity flags** (rows 7, 8): sub-hundred / sub-few-hundred square-foot lots — confirm these are real slivers vs. an extract artifact.
4. **On sign-off:** lift the provisional cap for the validated districts (or record the corrections and re-author), then the pgh standards can inform trusted v8 verdicts (Slice 7). Until then, buildability stays provisional in-product.
