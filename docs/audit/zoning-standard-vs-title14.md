# Audit — `zoning_standard` seeds vs. the parsed Title 14 dimensional tables

**Date:** 2026-08-11 · **Branch:** `feat/land-tab-audit-and-display` · **Base:** `main` @ `6e28166`
**Corpus:** phillycode `d3`, 21,512 documents, `verify-derivation --require-complete` OK
**Seed under audit:** `backend/src/lotscope/zoning/seed.py`, `TITLE_14_STANDARDS`, `title14-quickguide-2026-02` (39 districts)

This audit compares every seeded dimensional value against the parsed Philadelphia Code. **Nothing is corrected here.** Dispositions D1–D4 are the owner's, and no migration, re-seed, or recompute runs before sign-off.

---

## 0. Concurrency check — what was already done elsewhere

The Slice 4 eval session (branch `feat/phillycode-eval-cutover`, unmerged) had already reached the RSA-5 question. Re-verification was not repeated:

- **`eb67a9c`** closed the RSA-5 chain at the printed page: `philadelphiahomerulecharter.pdf` p.951 read with pdfplumber's raw page text, independent of the parser's table pipeline. Parser and page agree on `960 [2]`. Cell alignment cross-checked by footnote anchors ([1]→RSA-4, [2]→RSA-5). **A3 for this discrepancy is therefore already closed at the primary source and is cited, not redone.**
- **`98cadfa`** already changed the RSA-5 seed to 960 *on that branch*, with `test_seed_dimensional.py` pinning all eleven Table 14-701-1 districts.

**That commit is on the eval branch only — `main` still ships 1,440.** This audit runs against `main`, so RSA-5 appears below as a live discrepancy. **§6 records why that pending correction should not merge as written**: its impact reasoning rests on an overlay footprint this audit measures to be roughly twice what the commit message assumes, and the trade is far closer than stated.

---

## 1. A1 — Extraction and the column→district alignment

Four district dimensional tables carry the seeded fields. All are `code_provision` rows with `table_data`:

| Table | `cite` | page | districts |
|---|---|---|---|
| 14-701-1 | `14-701(2)(b)[11]#table1` | 951 | RSD-1…RTA-2 (11) |
| 14-701-2 | `14-701(2)(c)[9]#table1` | 952 | RM-1…RMX-3 (7) |
| 14-701-3 | `14-701(3)(a)[4]#table1` | 953 | CMX-1…CA-2 (7 cols, 8 districts) |
| 14-701-4 | `14-701(4)(a)[5](.b)#table1` | 954 | IRMX…I-P (6) |

**Alignment method, and the evidence for it.** Alignment is not inferred from column position. Tables 14-701-1/-2/-3 each carry a literal `District Name` header row inside `table_data.rows`; the mapping is read from that row, so a shifted column would have to shift the header identically to go unnoticed:

```
14-701-1  ['RSD-1','RSD-2','RSD-3','RSA-1','RSA-2','RSA-3','RSA-4','RSA-5','RSA-6','RTA-1','RTA-2']
14-701-2  ['RM-1','RM-2','RM-3','RM-4','RMX-1','RMX-2','RMX-3']
14-701-3  ['CMX-1','CMX-2','CMX-2.5','CMX-3','CMX-4/CMX-5','CA-1','CA-2']
14-701-4  ['IRMX','ICMX','I-1','I-2','I-3','I-P']       <-- not from a header row; see below
```

**Table 14-701-4 has no header row in `table_data.rows`** — the parser dropped it into the provision's flat `text` instead. Its mapping is recovered from that text (`"District Name IRMX ICMX I-1 I-2 I-3 I-P [2]"`) and independently corroborated three ways: the IRMX column is the only one carrying notes [4]/[5], and §14-701(4)(a)[4] and [5] both open *"In the IRMX district…"*; the I-P column is the only one with no FAR entry, matching a parks-industrial district; and the six-column width matches the six industrial districts exactly. **This is the one table where a reviewer should not take alignment on trust**, and it is flagged as such in D4.

Two further extraction observations, neither blocking:

- Every `#table2` continuation row (`14-701(3)(a)[4]#table2`, `14-701(4)(a)[5](.b)#table2`, `14-701(5)…#table2`, `14-701(6)#table2`) has **zero rows** but non-empty `text` carrying the same body content. The substantive data survives in `#table1`; the continuations are empty shells. Reported to the phillyruleparser workstream (§5), not worked around here.
- `14-701(5)` and `14-701(6)` are *not* district dimensional tables (sky-plane controls and height/yard encroachment exceptions respectively) and are correctly out of scope.

**Coverage:** 32 of 39 seeded districts appear in these four tables. The seven `SP-*` districts do not — their standards live in §§14-404…14-409 (Special Purpose Districts), outside the audited scope. They are **unaudited**, recorded in §4.

---

## 2. A2 — The discrepancy table

Full per-district, per-field output is reproducible with the query set in §7. Summary across 32 in-table districts × 7 dimensional fields:

| class | count | meaning |
|---|---|---|
| **match** | 71 | seeded scalar equals the printed cell exactly |
| **conditional** | 25 | cell is a conditional/textual rule; seed holds one scalar |
| **seed-missing** | 6 | table states a value, seed has none |
| **seed-asserts-blank** | 2 | seed states a value, table cell is blank |
| **numeric mismatch** | **1** | seed and table disagree on a number |

### The single numeric mismatch

| district | field | seeded | parsed | note | table |
|---|---|---|---|---|---|
| **RSA-5** | `min_lot_area_sqft` | **1,440** | **960** | `[2]` | 14-701-1, p.951 |

**Every other district in every other numeric field matches exactly.** This is the strongest result in the audit: the seed's transcription convention is sound, and 71 of 72 determinate values are correct. RSA-5 is an isolated slip, not a systematic inversion — and the likely mechanism is visible one table over, where **RM-1's minimum lot area genuinely is 1,440** (Table 14-701-2, p.952, `1,440 [1]`). Adjacent-row confusion between the two most common small-lot residential districts fits the evidence.

### Near-misses, classified (not waved through)

No unit or rounding differences exist. All 71 matches are exact, including footnoted cells (`1,620 [1]`, `25 [10]`, `80[3]`, `35 [11]`, `9 [7]`) where the seed correctly takes the numeral and drops the marker.

### Conditional cells — seed scalar vs. a rule (25 cases)

These are **not** errors; they are a modelling limitation worth stating because the Land tab renders them as flat numbers:

- **Occupancy, intermediate vs. corner** (RSA-5, RTA-2, RM-1, RM-4, CMX-2, CMX-2.5, CMX-3, IRMX): table reads `Intermediate: 75; Corner: 80`. Seed takes the intermediate figure. Defensible default, understates corner lots by 5pp.
- **Rear yard, use-conditional** (RSA-3, RSA-4, RTA-1): table reads `Single-Family 15; other 20`. Seed takes the single-family figure — correct for the vacant-residential-lot case the product serves.
- **Rear/side yard, "if used"** (CA-1, RM-4, ICMX, I-1, I-2, I-3): table reads `8 if used`. Seed states `8` unconditionally, i.e. treats an optional yard as required. Conservative (understates buildable area).
- **CMX-2/CMX-2.5 rear yard**: table reads `The greater of 9 ft. or 10% of lot depth`. Seed holds `9`. Understates on deep lots.
- **RMX-1 occupancy**: cell is footnotes only, `[3][4]`. §14-701(2)(c)[3] gives *"no more than fifty percent (50%) of the master plan area"* — the seeded `50` is **correct in value** but is a percentage of *master plan area*, not lot area. Semantically different quantity, same number.
- **CMX-4/CMX-5 FAR**: one shared cell, `CMX-4: 500 CMX-5: 1,200 [2]`. Seed splits it correctly (500 / 1,200).

### Seed-missing (6)

| districts | field | table value |
|---|---|---|
| IRMX, ICMX, I-1, I-2, I-3 | `max_floor_area_ratio_pct` | **500** (all five) |
| I-P | `rear_setback_ft` | **0 [3]** |

The industrial FAR omission is a genuine coverage gap: the table states 500 for five districts and the seed carries none, so FAR-dependent output is silently unavailable across the industrial districts.

### Seed-asserts-blank (2) — **unresolved, needs the Quick Guide page**

| district | field | seeded | table 14-701-2 cell |
|---|---|---|---|
| RMX-3 | `front_setback_ft` | 25 | *(blank)* |
| RMX-3 | `rear_setback_ft` | 25 | *(blank)* |

The table legend reads *"Denotes building type not permitted or zoning requirements not applicable."* Taken at face value, RMX-3 has **no** minimum front or rear yard and the seeded 25 ft is a constraint the code does not impose — which would understate buildable area on every RMX-3 lot. I could not resolve these against Title 14: a corpus search for RMX-3 yard requirements returns only §14-604(14)(e) (balconies *may extend into* required yards), which presumes yards without setting them. **These two values are the only ones in the audit I am leaving unresolved**, because resolving them requires the Quick Guide page itself — a secondary transcription, not the code — and that is a source this audit did not have. Carried into D1 as an explicit open item rather than guessed.

---

## 3. A3 — Primary-source verification of the mismatch

One numeric mismatch, one classification required.

**RSA-5 `min_lot_area_sqft`: `seed wrong`.** The printed page agrees with the parser.

Verified in `eb67a9c` (see §0) at `philadelphiahomerulecharter.pdf` p.951 via pdfplumber raw page text, deliberately bypassing the table pipeline because cell-level extraction is this parser's known defect class. The printed row reads:

```
10,000  7,800  5,000  5,000  3,150  2,250  1,620 [1]  960 [2]  700  2,250  1,080
```

against eleven districts; RSA-5 is position 8 and position 8 reads `960 [2]`. Alignment is cross-checked by two independent footnote anchors — `[1]` on RSA-4 with §14-701(2)(b)[1] opening *"In the RSA-4 district"*, and `[2]` on RSA-5 with §14-701(2)(b)[2] opening *"In the RSA-5 district"*. Shifted cells would have misplaced both. **No extraction defect; the seed is the wrong side.**

**No mismatch is left unclassified.** There is exactly one, and it resolves to seed-wrong. No `parser wrong` findings arose in the numeric comparison — the two parser defects found (§5) are structural, not value-level.

---

## 4. A4 — The small-lot provision check

`subdivision/analysis.py` hardcodes `SMALL_LOT_PROVISIONS` with a single `RSA5` entry. Verbatim code text, retrieved from `code_provision`:

> **§14-701(2)(b)[2]** — "In the RSA-5 district, a lot containing at least **1,600 sq. ft.** of land may be divided into lots with a minimum lot size of **800 sq. ft.**, provided that:
> **(.a)** At least **seventy-five percent (75%)** of lots **adjacent to the lot to be divided** is **1,000 sq. ft.** or less;
> **(.b)** Each of the lots created is used for one single-family attached home; and
> **(.c)** Each of the lots created meets the minimum lot width requirement of the zoning district."

### Constant-by-constant

| implemented | value | code | verdict |
|---|---|---|---|
| `trigger_lot_area_sqft` | 1600.0 | "at least 1,600 sq. ft." | **exact** |
| `min_child_lot_area_sqft` | 800.0 | "minimum lot size of 800 sq. ft." | **exact** |
| `adjacent_small_share` | 0.75 | "seventy-five percent (75%)" | **exact** |
| `adjacent_small_max_area_sqft` | 1000.0 | "1,000 sq. ft. or less" | **exact** |
| `min_lot_width_ft` | 16.0 | "the minimum lot width requirement of the zoning district" | **correct but coupled** — see below |

### The adjacency predicate — **no divergence**

The prompt's hypothesis was that the code might condition on the same block face or another restricted population. **It does not.** The code says only *"lots adjacent to the lot to be divided"*, with no block-face, street-frontage, or same-side qualifier anywhere in [2] or its provisos.

The implementation (`subdivision/service.py:35-50`) takes `compute_assemblage` neighbours filtered to `shared_boundary_ft >= 1.0` and computes `small / len(adjacent)`. Reading "adjacent" as "shares a boundary" is a faithful and defensible reading of the unqualified term. The 1 ft floor is an implementation detail that excludes point-touching parcels — sensible, and if anything slightly conservative.

**Verdict: implemented predicate matches the law as written.** No correction required. This is a clean result and D3 should record it as such.

### Three secondary findings

1. **`min_lot_width_ft=16.0` is correct but hardcoded against the wrong authority.** The code defers to *"the minimum lot width requirement of the zoning district"*, which is a pointer to `zoning_standard.min_lot_width_ft` (RSA-5 = 16, and that value matches the table exactly). Freezing 16 in the provision table means a future correction to the district's width would silently not propagate. Low risk today, latent.
2. **Proviso (.b) — "used for one single-family attached home" — is unmodelled.** Immaterial for a land-only analysis, but it means a reported split count is a dimensional maximum, not a permission.
3. **The citation string is wrong.** `citation="Title 14 Table 14-701-1 small-lot provision"`. The provision is **§14-701(2)(b)[2]**; the table only carries the `[2]` marker. This string is user-facing.

### **Other districts carry an analogous note the map omits — RM-1**

> **§14-701(2)(c)[1]** — "In the **RM-1** district, a lot containing at least **1,920 sq. ft.** of land may be divided into lots with a minimum lot size of **960 sq. ft.**, provided that: **(.a)** At least seventy-five percent (75%) of lots adjacent to the lot to be divided are 1,000 sq. ft. or less; and **(.b)** Each of the lots created meets the minimum lot width requirement of the zoning district."

Structurally identical, different constants (1,920 / 960), and **absent from `SMALL_LOT_PROVISIONS`**. Consequence: **76,042 RM-1 parcels** never receive small-lot subdivision analysis at all; **19,435** of them clear the 1,920 trigger and are currently evaluated against the plain 1,440 minimum instead of the 960 small-lot floor.

A further overlay-scoped variant exists at **§14-502(4)(c)(.2)** ("Lots zoned RM-1 with a lot size of at least 1,600 sq. ft. may be divided into two lots with a minimum lot size of 800 sq. ft."), which is a *different* rule for RM-1 inside that overlay — more evidence that a single flat map cannot hold this domain.

---

## 5. Parser findings for the phillyruleparser workstream

Reported, **not patched around in LotScope** (per the slice's hard constraint):

1. **Dropped header row on Table 14-701-4.** `14-701(4)(a)[5](.b)#table1` has no `District Name` row in `table_data.rows`; the header survives only in the flattened `text`. Any consumer aligning that table by position alone is guessing. Same defect class as the continuation orphans in ADR-0078's Slice 2 preconditions.
2. **Zero-row continuation tables.** Four `#table2` provisions parse to `rows: []` while their `text` carries the real body. Generalises across `14-701(3)`, `14-701(4)`, `14-701(5)`, `14-701(6)` — i.e. it is a pattern, not an instance.

Neither affects the value-level comparison in §2, because the substantive cells survive in `#table1` and alignment was recovered independently. Both would corrupt a naive consumer.

---

## 6. A5 — Impact measurement

Measured on the local `phl` corpus. **Both district spellings are present in `parcel`** (`RSA5` and `RSA-5`) — the spelling gotcha the eval session already hit — so all figures union both.

### RSA-5, correcting 1,440 → 960

| measure | parcels |
|---|---|
| RSA-5 parcels total | 313,000 |
| **with a stored verdict** | **312,626** |
| in the `[960, 1440)` conformity flip band | **112,916** (36.1%) |
| of those, stored `can_build_by_right = false` → would become **true** | **112,913** |
| where `max_lots` increases (`floor(a/960) > floor(a/1440)`) | **143,312** (45.8%) |

This is a corpus-wide move: roughly **one in three** RSA-5 parcels changes conformity and **nearly half** change split count.

### The finding that should govern D1 — the overlay footprint is about twice what was assumed

Commit `98cadfa` justifies the correction on the grounds that it trades *citywide* false negatives for false positives *"confined to three overlays"* (`/FNE`, `/NDO`, `/FDO`). **Six overlay sections set the RSA-5 minimum to 1,440**, and the three that were missed are the large ones:

| overlay | section | flip-band RSA-5 parcels inside |
|---|---|---|
| /NDO Ninth District | 14-520(4)(a) | 16,703 |
| **/EDO Eighth District** | **14-530(2)** | **13,530** ← missed |
| /FDO Fourth District | 14-524(2)(a) | 12,117 |
| **/SIX Sixth District** | **14-548(3)(a)(.3)** | **12,042** ← missed |
| /FNE Far Northeast | 14-514(5)(a) | 8 |
| **/NE Northeast** | **14-515(2)(c)(.1)** | **8** ← missed |
| **distinct total** | | **54,376** |

**54,376 of the 112,916 flip-band parcels — 48% — sit inside an overlay where 1,440 is the correct minimum.**

So the real trade is not "citywide false negatives for a confined pocket of false positives." It is approximately **58,540 wrong answers corrected against 54,376 new wrong answers created**, and the new ones are false positives — a lot told it clears a minimum that its overlay actually raises. By the commit's own (correct) reasoning that false positives are the worse failure mode because they are advice someone acts on, **a bare scalar correction is close to a wash and may be a net regression in user harm.** The `/FNE` overlay that anchored the original "confined" claim contributes 8 parcels; the two largest contributors were never counted.

This does not mean 960 is the wrong number — §3 settles that it is the right one for the base district. It means **the scalar correction should not ship without overlay-aware resolution**, and that changes the shape of D1.

### RM-1, adding the missing small-lot provision

| measure | parcels |
|---|---|
| RM-1 parcels | 76,042 |
| clearing the 1,920 small-lot trigger | 19,435 |
| in the `[960, 1440)` band (already conforming; unaffected by RSA-5) | 28,813 |

Adding RM-1 to `SMALL_LOT_PROVISIONS` is **purely additive** — it can only reveal splits currently not offered, and carries no overlay counter-pressure of the RSA-5 kind. It is the lowest-risk, highest-value item in this audit.

---

## 7. Reproducing the audit

Both sides of every value in §2 come from these two sources, and every figure above is re-derivable:

```sql
-- parsed side: any district table, with its District Name header row
select jsonb_pretty(table_data) from code_provision
where market_code='phl' and cite='14-701(2)(b)[11]#table1';   -- Table 14-701-1, p.951

-- verbatim note text (A4)
select cite, regexp_replace(text,'\s+',' ','g') from code_provision
where market_code='phl' and cite like '14-701(2)(b)[2]%' order by ordinal;

-- other districts' small-lot notes (A4)
select cite, left(regexp_replace(text,'\s+',' ','g'),200) from code_provision
where market_code='phl' and title_number='14'
  and text ~* 'may be divided into lots|minimum lot size of' order by cite;

-- overlays raising the RSA-5 minimum (A5)
select cite from code_provision where market_code='phl'
  and text ~* 'RSA-5 district, the minimum lot area shall be 1,440';
```

Seeded side: `TITLE_14_STANDARDS` in `backend/src/lotscope/zoning/seed.py`.

---

## 8. PAUSE — decisions for the owner

**Nothing below has been implemented. No migration, re-seed, or recompute has run.**

### D1 — Per-discrepancy disposition

| # | item | recommendation |
|---|---|---|
| 1 | **RSA-5 `min_lot_area_sqft` 1,440 → 960** | **Hold the bare scalar correction.** The value is confirmed wrong (§3), but §6 shows the correction converts ~58.5k false negatives into ~54.4k false positives — the worse failure mode, at nearly 1:1. Recommend pairing the seed correction with overlay-aware resolution in one slice, so the 54,376 overlay parcels keep 1,440. If the owner prefers to ship the scalar alone, it is still defensible on a strict reading of the base district, but the "confined to three overlays" rationale in `98cadfa` should be corrected first — **that commit should not merge as written.** |
| 2 | **RM-1 small-lot provision missing** | **Correct.** Purely additive, no counter-pressure, 19,435 parcels gain analysis they should already have. Highest value-to-risk item here. |
| 3 | **Industrial FAR missing (5 districts, 500)** | **Correct.** Straightforward transcription gap, table is unambiguous. |
| 4 | **I-P `rear_setback_ft` missing (0)** | **Correct.** Same class, trivial. |
| 5 | **RMX-3 front/rear setback 25 vs blank** | **Hold, open item.** Unresolved against Title 14 (§2). Needs the Quick Guide page before any change; do not guess in either direction. |
| 6 | **Parser: dropped header, zero-row continuations** | **Upstream.** File against phillyruleparser; both patterns generalise. |
| 7 | **25 conditional cells** | **Hold.** Not errors. Candidates for the disclosure treatment Part 2 establishes, not for value changes. |
| 8 | **Small-lot citation string** | **Correct** to §14-701(2)(b)[2]. User-facing and simply wrong. |

### D2 — Versioning posture

**Recommend the deal-fix precedent, as proposed:** no `VERDICT_VERSION` bump; a short ADR recording each corrected value with its page cite and measured flip count; a targeted verdict recompute per affected district after deploy. These are corrections to a transcription of an unchanged source, not a change in how verdicts are computed, so a version bump would misrepresent them as a methodology change. **One amendment:** at 112,916 RSA-5 conformity flips the recompute is not a routine background job — it needs to be scheduled and announced, because a third of the district's stored verdicts change meaning on the day it runs.

### D3 — Small-lot predicate

**No correction required.** A4 found the adjacency predicate faithful to the code as written — the divergence the prompt anticipated does not exist. Recommend recording that finding explicitly (it is worth knowing the rule was checked and held), and separately taking the three secondary items: add RM-1, fix the citation string, and either read `min_lot_width_ft` from the district standard or leave a test pinning it to 16.

### D4 — Standing machinery

**Recommend yes.** This audit found a live value defect, a missing provision affecting 76k parcels, six coverage gaps and two parser defects, and it reduced to a set of queries once the corpus was canonical. A `verify-zoning-standards` ops command in the Slice-1 cross-check pattern — comparing `TITLE_14_STANDARDS` to `code_provision.table_data` and failing on numeric divergence — makes the next `source_version` re-run it for free. Two design notes: it must key off the `District Name` header row rather than column position, and it needs an explicit allowlist for the conditional cells (§2) or it will report 25 false alarms on every run.

---

## 9. Scope note

Seven `SP-*` districts (SP-INS, SP-CIV, SP-PO-A, SP-PO-P, SP-ENT, SP-STA, SP-AIR) carry seeded values and were **not audited** — their standards live in §§14-404…14-409, outside Tables 14-701-1…-4. Whether they warrant the same treatment is a separate scoping call; they are low-volume for vacant-land work, which is why this is a note and not a finding.
