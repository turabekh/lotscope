# ADR-0077 — Parking modelled for the uses we actually model

Status: proposed (2026-08-04)

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

A new `district_parking_requirement` reference table, seeded from Chapter 14-800 and keyed by `(market_code, district_code, dwelling_use, code_version)`, storing a ratio as `spaces_per_unit` (`0`, `1`, `0.5`, `0.3`) plus the citation. It is reference data like `zoning_standard`, so it seeds on deploy and needs no migration of parcel-level data.

`min_parking_spaces` on `zoning_standard` is **removed**, not populated. It has been null for every district since it was introduced, it cannot represent the source, and leaving it invites exactly the wrong fill-in later.

The checklist row becomes three honest states rather than one evasion:

- **satisfied** — *"RSA-5 requires no off-street parking for a single-family home (Table 14-802-1)."* `not_applicable`.
- **quantified** — *"RSD-3 requires 1 off-street space per dwelling unit; the modelled 1-unit home needs 1 space (Table 14-802-1)."* `pass`, with the count carried into the program statement.
- **unmodelled** — for a district the tables handle separately (CMX-1, CA-1, CA-2) or a use we do not model, the current wording stands, naming the section that governs instead of Title 14 generally.

**Non-residential uses are out of scope and stay unmodelled.** We never model a stadium or an assembly hall on a vacant lot, so the conditional formulas need not be encoded. Encoding them would be speculative work against a schema we cannot validate.

**Every value is verified visually against the printable table before it is seeded.** Text extraction of Table 14-802-3 returned five column headers against three values per row — a silent misalignment that would have produced plausible, authoritative, wrong numbers. That table is not to be seeded from extracted text under any circumstances, and neither are the other two without a visual check. This is the same class of error as ADR-0073's rejected improved-land comps: a number that looks well-supported and measures the wrong thing.

## Consequences

**The check stops undermining the unit count on 96% of Philadelphia.** For 74% it becomes a positive statement — no parking required — which is a genuine selling point for an infill buyer and is currently hidden behind "not modelled".

**A schema change, but not a verdict-contract change.** `parking` is a checklist row and a program claim, both computed on read. No `VERDICT_VERSION` bump, no recompute. Dropping `min_parking_spaces` is a hand-written migration; it is null everywhere, so nothing is lost.

**Scope must not creep to loading.** Chapter 14-800 also sets loading requirements, keyed by use and floor area. The checklist row is titled "Parking & loading" and will now answer only the parking half. Either the row is retitled or the loading half stays explicitly unanswered — it should not be quietly implied.

**Industrial districts wait.** IRMX and ICMX permit multi-family, so they belong in the model eventually, but their values come from Table 14-802-3 — the one whose extraction is known-unreliable. They stay unmodelled until that table is read visually.

**The 20,335 "other" parcels are unaffected** — they carry a district code the tables do not cover or none at all, and keep today's wording.

**Bonuses and overlays are not modelled.** §14-702(9) trades parking for FAR, and overlays can alter requirements — except where the table says otherwise, as CMX-4/5 multi-family does. The claim is therefore the base-district minimum, and the citation says so.
