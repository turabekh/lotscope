# ADR-0077 — Parking modelled for the uses we actually model

Status: accepted (2026-08-04) — implemented, with three deviations recorded below

Unblocks the `parking` checklist row, which **ADR-0075** deliberately left unanswerable: `min_parking_spaces` was forbidden a disposition until Chapter 14-800 was ingested, because a null there could not be read as "no requirement" without evidence. The chapter is now available locally and the evidence exists.

## Context

The dossier's parking row reads:

> Parking and loading requirements are not modelled. Confirm the district's minimum against Title 14 before relying on the unit count.

That is honest but useless, and it undercuts the unit count immediately above it on every Philadelphia parcel.

`min_parking_spaces` is null for **all 96 districts** and always has been. The Base Districts Quick Guide — the source for every other dimensional field — carries no parking table at all; parking appears in it only as a §14-702 *bonus*. The requirements live in Chapter 14-800, a separate document.

### The chapter is not shaped like our field

`zoning_standard.min_parking_spaces` is a single integer per district. Chapter 14-800 is a **matrix**: use category × district group, and many cells are conditional formulas rather than numbers.

```
Assembly and Entertainment
  col 1  1/10 seats or 1/1,000 sq. ft., whichever is greater
  col 2  none for first 100 seats then 1/10 seats, or
         none for first 2,500 sq. ft. then 1/1,000 sq. ft.
  col 3  none for the first 200 seats then 1/10 seats, or
         none for first 4,000 sq. ft. then 1/1,000 sq. ft.
```

No integer per district can hold that, and forcing one in would produce a confident figure that is wrong for most uses — the failure ADR-0072 exists to prevent, and worse here because it would look authoritative.

### But the uses we model are simple

The product models one thing on a vacant lot: **household living** — single-family, two-family, or multi-family. Restricted to those rows, the tables are plain ratios, not formulas.

**Table 14-802-1 — Residential districts**

| use | RSD-1/2/3, RSA-1/2/3, RTA-1, RMX-1 | RSA-4/5/6, RTA-2, RM-1 | RM-2/3/4, RMX-2/3 |
|---|---|---|---|
| Single-Family | 1/unit | **0** | **0** |
| Two-Family | 1/unit | **0** | 1/2 units |
| Multi-Family | 1/unit | **0** | 3/10 units |

**Table 14-802-2 — Commercial districts** (except CMX-1, CA-1, CA-2, which §14-802(7) handles separately)

| use | CMX-2/2.5 | CMX-3 | CMX-4/5 |
|---|---|---|---|
| Household Living | **0** | 3/10 units | **0** |
| Multi-Family | **0** | 3/10 units | **0** [1] |

[1] Applies notwithstanding the provisions of any overlay to the contrary.

### What that is worth

Counting Philadelphia parcels by the district groups the tables actually use:

| group | requirement for household living | parcels |
|---|---|---:|
| RSA-4/5/6, RTA-2, RM-1 | **none** | **402,478** |
| RSD, RSA-1/2/3, RTA-1, RMX-1 | 1 per unit | 96,944 |
| CMX-2/2.5, CMX-3 | 0 or 3/10 units | 21,167 |
| CMX-4/5 | **none** | 2,553 |
| RM-2/3/4, RMX-2/3 | 0 or 3/10 units | 1,856 |
| other / unresolved | — | 20,335 |

**405,031 parcels — 74% of the city — require no off-street parking at all** for the use we model. Another 96,944 need exactly one space per unit. The row that today says "not modelled" can give a definite answer on roughly 96% of Philadelphia, and for three quarters of it that answer is *none required*.

This also settles the CMX-4 case that prompted the question: **CMX-4 requires no off-street parking for multi-family**, notwithstanding any overlay.

## Decision

**Model parking for household living only, and say so.**

The requirement is held as a ratio of `spaces` per `per_units` — `1/1`, `0/1`, `1/2`, `3/10` — keyed by district and dwelling use, with the table it came from carried alongside for citation.

**Deviation 1 — a module constant, not a database table.** The proposal called for a `district_parking_requirement` table seeded like `zoning_standard`. It is implemented as a pure constant in `zoning/parking.py` instead. Nothing queries parking except the checklist, which is computed on read, so a table plus seeder plus migration would buy nothing over a tested constant. Should a second consumer appear that needs to filter or join on parking, the constant moves to a table then.

`min_parking_spaces` on `zoning_standard` is **removed**, not populated. It has been null for every district since it was introduced, it cannot represent the source, and leaving it invites exactly the wrong fill-in later.

The checklist row becomes three honest states rather than one evasion:

- **satisfied** — *"RSA-5 requires no off-street parking for a single-family home (Table 14-802-1)."*
- **quantified** — *"RM-4 requires 3 off-street spaces per 10 dwelling units for multi-family dwellings; the modelled 10 unit(s) would need 3 space(s)."*
- **unmodelled** — for a district the tables handle separately (CMX-1, CA-1, CA-2) or a use we do not model, the row names the governing section instead of Title 14 generally.

**Deviation 2 — both answered states are `pass`, not `not_applicable`.** The proposal assigned `not_applicable` to the zero case. That is wrong under ADR-0075's own distinction: `not_applicable` means *the district sets no such standard*, and a requirement of zero **is** a stated standard.

**A ratio that does not divide exactly yields no count.** Four units at 3 per 10 is 1.2 spaces; the chapter's rounding rule was not read, so the requirement is stated and the count withheld rather than guessed.

**Non-residential uses are out of scope and stay unmodelled.** We never model a stadium or an assembly hall on a vacant lot, so the conditional formulas need not be encoded. Encoding them would be speculative work against a schema we cannot validate.

**Deviation 3 — layout-preserving extraction replaced visual verification, and changed the outcome.** Naive text extraction of Table 14-802-3 returned five column headers against three values per row — a silent misalignment that would have produced plausible, authoritative, wrong numbers. Page rendering was unavailable (no poppler on the machine), so `pypdf`'s `extraction_mode="layout"` was used instead: it preserves x-position, which is exactly the property the misalignment destroyed.

That resolved the ambiguity rather than merely flagging it. Table 14-802-3 has **three** columns, not five — `IRMX` | `ICMX, I-1` | `I-2/3, I-P` — and the naive pass had merged the stacked header cells. **Industrial districts are therefore included**, not deferred. Every value in all three tables was read from layout-preserved output with the header positions checked against the value positions.

The risk this guards against is unchanged and remains the rule: no parking value is ever taken from flat extracted text. It is the same class of error as ADR-0073's rejected improved-land comps — a number that looks well-supported and measures the wrong thing.

## Consequences

**The check stops undermining the unit count.** Measured through the real code path on 200 spread-sampled Philadelphia parcels after implementation: **97.0% answered** (`pass`), **79.5% answered "no off-street parking required"**, 3.0% still `not_evaluated`. Slightly better than the projection above, which counted district codes rather than running the checklist.

**A schema change, but not a verdict-contract change.** `parking` is a checklist row and a program claim, both computed on read. No `VERDICT_VERSION` bump, no recompute. Dropping `min_parking_spaces` is a hand-written migration; it is null everywhere, so nothing is lost.

**Scope must not creep to loading.** Chapter 14-800 also sets loading requirements, keyed by use and floor area. The checklist row is titled "Parking & loading" and will now answer only the parking half. Either the row is retitled or the loading half stays explicitly unanswered — it should not be quietly implied.

**Industrial districts are included.** IRMX (3 per 10 units) and ICMX (1 per 2 units) permit multi-family and are modelled. I-1/2/3 and I-P carry values in Table 14-802-3 but do not permit housing, so those rows are unreachable for the use we model.

**The 20,335 "other" parcels are unaffected** — they carry a district code the tables do not cover or none at all, and keep today's wording.

**Bonuses and overlays are not modelled.** §14-702(9) trades parking for FAR, and overlays can alter requirements — except where the table says otherwise, as CMX-4/5 multi-family does. The claim is therefore the base-district minimum, and the citation says so.
