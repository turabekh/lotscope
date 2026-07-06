# Harrisburg zoning_standard — corpus coverage (graduation Slice 2)

Cross-checked every field of the 9 `hbg` `zoning_standard` rows against the verbatim Title 7 corpus (§7-307.3A Development Standards attachment + the chapter narrative). Corpus gate: fields filled only where the ordinance states them; genuinely-unstated fields stay NULL with a reason. `code_version = hbg-provisional-2026`.

## Dimensional coverage — complete
All stated dimensional values are filled. The NULLs are **genuinely unstated or conditional**, verified against the §7-307.3A table:

| District | NULL field(s) | Reason (from corpus) |
|---|---|---|
| DC (Downtown Center) | max_height | "45 ft minimum, **no maximum**" — no cap exists |
| IND (Industrial) | max_height | "**no maximum**" |
| RF (Riverfront) | min_lot_width, front_setback, rear_setback | **location-conditional**: width 20 ft south / 50 ft north of Reily St; front/rear setbacks depend on Front vs State St frontage — no single value; verbatim language preserved in the `dimensional` JSONB |

Every other dimensional cell (lot area, width, height, coverage, front/rear/side setback) is populated per district. No new dimensional value was fillable from the corpus — the Wave-0 transcription was complete.

## The one systematic gap — `permitted_uses` (all 9 NULL)
`permitted_uses = []` for every district because **the use matrix is a separate eCode360 attachment**, not in the chapter export. §7-305.7 footnote 16 states verbatim: *"The use table is included as an attachment to this chapter."* — the exact pattern as the §7-307.3A dimensional table in Wave 0.

**Consequence:** without permitted uses, buildability cannot affirm `can_build_by_right` (it requires a matching by-right use), so every Harrisburg parcel currently reads *not by-right / needs a use check* — honest, but incomplete. The engine degrades correctly (the reason names the missing use table).

**To close:** acquire the **§7-305.7 use-table attachment** from eCode360 (Track-C handoff — same as the dimensional table). When it lands, encode the P / SE / N per-district-per-use matrix (P = permitted by right, SE = special exception, N = not permitted, 7-309 = specific criteria) into `permitted_uses`, cited, then re-verify + recompute.

## Status
- Dimensional standards: **corpus-complete**, cited to §7-307.3A.
- Permitted uses: **NULL pending the §7-305.7 use-table attachment** (Track-C).
- Corpus embed-load: **pending Voyage quota** (Track-C) — blocks Ask-the-Parcel grounding only, not buildability.
