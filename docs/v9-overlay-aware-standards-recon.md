# Recon — Verdict v9: overlay-aware standards and the audit's corrections

**Date:** 2026-08-11 · **Branch:** `feat/v9-overlay-aware-standards` (off `main` @ `3197d8f`) · **Status: recon, nothing built**
**Evidence base:** `docs/audit/zoning-standard-vs-title14.md` (PR #143, **still open**) · corpus phillycode `d3`, `verify-derivation --require-complete` **OK, 21,512/21,512**

Recon only. No migration, seed edit, resolution change, or recompute has run. D1–D6 await sign-off.

---

## 0. Preconditions — carried forward from the stop report

| # | check | state |
|---|---|---|
| 1a | PR #143 merged | ❌ still **OPEN** |
| 1b | 98cadfa unwound | ❌ still live on `feat/phillycode-eval-cutover` (local + origin) |
| 2 | `verify-derivation` | ✅ OK |
| 3 | Slice 4 | PAUSE 2 **not reached**, cutover **not decided** |

Proceeding at the owner's direction on the assumption both clear. **File overlap is direct:** the eval branch edits `backend/src/lotscope/zoning/seed.py` (the exact RSA-5 line v9 owns) and adds `zoning/tests/test_seed_dimensional.py` (pins RSA-5 at 960). Nothing else on that branch touches zoning resolution.

---

## 1. R1 — The current resolution path

### The chain

```
parcel_number
  └─ _PARCEL_SQL                     zoning/service.py       → base_zoning_code, has_geometry
  └─ resolve_district(...)           zoning/service.py:82    → DistrictResolution(code, method, corroborated)
        spatial (ST_Intersects zoning_district) → else base_zoning_code ("opa_attribute")
  └─ _get_standard(session, code, market_code)   zoning/service.py:132
        _STANDARD_SQL → zoning_standard WHERE upper(replace(code,'-','')) = :code
                        AND market_code = :market  ORDER BY code_version DESC LIMIT 1
        → DistrictStandard   (dataclass, zoning/buildability.py:26)
```

### **The seam**

`_get_standard` has **exactly two callers**, and both already hold `parcel_number`:

| caller | file:line |
|---|---|
| `get_parcel_standard` | `zoning/service.py:174` |
| `assess_parcel` (buildability) | `zoning/service.py:453` |

**This is the single seam.** Every consumer below reaches `zoning_standard` through one of these two. Nothing else in the codebase reads dimensional values out of `zoning_standard` for parcel-level logic (`ops/service.py` only counts rows for coverage reporting; `worker.py`/`core/provenance.py` handle freshness; the four `seed_*.py` write).

### Consumer tree — enumerated

**Via `assess_parcel` (buildability):**

| consumer | file:line |
|---|---|
| verdict composition | `verdict/service.py:19` |
| deal | `deal/service.py:21` |
| AI / Ask-the-Parcel | `ai/service.py:40` |
| API parcel routes | `api/parcels.py:81` |
| reports / dossier | `reports/service.py:15,39` |
| checklist | `checklist/service.py:27,154` |

**Via `get_parcel_standard`:**

| consumer | file:line |
|---|---|
| subdivision | `subdivision/service.py:60` |
| checklist | `checklist/service.py:43` |
| `assemblage_unit_estimate` | `zoning/service.py:184` → consumed by `assemblage/service.py:162` |

**Underwriting** has no direct zoning import; it reaches buildability through deal/verdict.

### Where overlays touch anything today

Exactly one place, and it is a **blunt boolean**:

```python
# subdivision/service.py:75
has_overlay = bool(await get_parcel_overlays(session, parcel_number))
```

fed to `analyze_subdivision`, which on `has_overlay` **suppresses the small-lot path entirely** (`subdivision/analysis.py:197-202`) with a "verify the §14-500 series" caveat. `get_parcel_overlays` (`zoning/service.py:49`) returns overlay **names** via live `ST_Intersects` against `zoning_overlay`.

**R2 shows this suppression is wrong** — see §2.

---

## 2. R2 — The six overlay sections

### Verbatim text

All six are **textually identical** in substance. Retrieved via:

```sql
select cite, regexp_replace(text,'\s+',' ','g') from code_provision
where market_code='phl' and cite in ('14-514(5)(a)','14-515(2)(c)(.1)','14-520(4)(a)',
  '14-524(2)(a)','14-530(2)','14-548(3)(a)(.3)');
```

> "In the RSA-5 district, the minimum lot area shall be **1,440 sq. ft.**, except that a lot containing at least **1,600 sq. ft.** of land may be divided into lots with a minimum lot size of **800 sq. ft.**, provided that: (.1) At least seventy-five percent (75%) of lots adjacent to the lot to be divided is 1,000 sq. ft. or less; (.2) Each of the lots created is used for one single-family attached home; and (.3) Each of the lots created meets the minimum lot width requirement of the zoning district."

| § | overlay | district | sets |
|---|---|---|---|
| 14-514(5)(a) | /FNE Far Northeast | RSA-5 | 1,440 |
| 14-515(2)(c)(.1) | /NE Northeast | RSA-5 | 1,440 |
| 14-520(4)(a) | /NDO Ninth District | RSA-5 | 1,440 |
| 14-524(2)(a) | /FDO Fourth District | RSA-5 | 1,440 |
| 14-530(2) | /EDO Eighth District | RSA-5 | 1,440 |
| 14-548(3)(a)(.3) | /SIX Sixth District | RSA-5 | 1,440 |

### **Finding: the overlays preserve the small-lot provision**

Each overlay carries the same 1,600 → 800 exception with provisos identical to base §14-701(2)(b)[2] (verified against `14-520(4)(a)(.1)/(.2)/(.3)`). **The overlays raise the base minimum only; they do not remove small-lot division.** The current blanket suppression at `analysis.py:197` therefore withholds a correct result inside these six — and it fires on *any* of the 193 overlays, not just these. This is a live defect the design must fix, not merely a modelling gap.

### Membership data

`get_parcel_overlays` computes membership **live** via `ST_Intersects(zo.geom_local, p.geom_local)`. There is **no materialized `parcel_overlay` table** (`\dt *parcel*` → parcel, parcel_assemblage, parcel_correction, parcel_distress, parcel_event, parcel_verdict, saved_parcel).

`zoning_overlay` coverage and provenance:

```sql
select count(*), count(code), count(code_section), count(name),
       count(distinct source), max(last_synced_at) from zoning_overlay where market_code='phl';
-- 193 | 193 | 193 | 193 | 1 (zoning_overlays) | NULL
```

**`code_section` already holds the §14-500 cite** — this is the natural join key for D2:

| code | code_section | polygons |
|---|---|---|
| /EDO | 14-530 | 1 |
| /FDO | 14-524 (+1 at `14-524(1)(c)`) | 9 |
| /FNE | 14-514 | 1 |
| /NDO | 14-520 | 10 |
| /NE | 14-515 | 1 |
| /SIX | 14-548 | 4 |

Two provenance gaps: **`last_synced_at` is NULL on all 193 rows** (no freshness signal for the layer the effective standard depends on), and membership is `ST_Intersects` — a parcel merely *touching* an overlay boundary is counted in. For a restrictive standard that errs safe, but it should be a stated choice, not an accident.

### Scoping check, measured

§14-524(2) applies to the *"Fourth District Area"* subarea (§14-524(1)(a)), not to every /FDO polygon — the commercial-review sub-areas are separate subareas. Whether keying on `code_section` alone over-applies:

| code | district-wide polygon only | any polygon of that code |
|---|---|---|
| /EDO | 13,530 | 13,530 |
| /FDO | 12,117 | 12,117 |
| /FNE | 8 | 8 |
| /NDO | **16,679** | **16,703** |
| /NE | 8 | 8 |
| /SIX | 12,042 | 12,042 |

**Divergence is 24 parcels of 54,376 (0.04%)** — the sub-areas are effectively subsets. Code-level keying is materially equivalent; polygon-level is technically correct. Surfaced as a D2 sub-decision.

### Reconciliation with the audit

Distinct flip-band parcels across the six: **54,376** — matches `docs/audit/zoning-standard-vs-title14.md` §6 exactly.

---

## 3. R3 — Effective-standard design

### Proposed resolution

```
base zoning_standard row  +  overlay modifications applicable to (district, parcel)
        → EffectiveStandard  (values + per-field provenance)
```

**Storage — a seeded `overlay_standard` table**, matching house patterns (seeded, cited, auditable, version-stamped like `zoning_standard`):

| column | value for the six |
|---|---|
| `market_code` | `phl` |
| `code_section` | `14-514` … `14-548` (joins `zoning_overlay.code_section`) |
| `overlay_code` | `/FNE` … `/SIX` |
| `district_code` | `RSA-5` |
| `field` | `min_lot_area_sqft` |
| `value` | `1440` |
| `citation` | `§14-514(5)(a)` … (the operative subsection, not the chapter) |
| `code_version` | new `title14-overlay-2026-08` |

Six rows. Keyed on `code_section` so the join to `zoning_overlay` is a column equality, not a name match.

**Signature.** `_get_standard` gains the parcel context it needs and returns the effective standard:

```python
async def _get_standard(
    session, code, market_code, *, parcel_number: str | None = None
) -> DistrictStandard | None
```

Overlay resolution applies only when `parcel_number` is passed. Both existing callers pass it (both already hold it), so behaviour is unchanged for any caller that does not — which keeps the seed/coverage paths and tests working untouched. `DistrictStandard` gains one field:

```python
overlay_modifications: list[OverlayModification]   # (field, value, base_value, overlay_code, citation)
```

Additive, so **no consumer breaks**; the eight consumers in §1 keep reading `min_lot_area_sqft` and simply get the effective number. Consumers that want provenance (Land tab, dossier, AI citations) read the new list. This is the smallest change that reaches every consumer at once, because all eight funnel through the one seam.

**Conflict rule — do not invent one.** Measured: of the 54,376 flip-band parcels, **54,344 sit under exactly one of the six, and 32 under two** — and all six set the identical value (1,440), so **no parcel has a conflicting value**. The code states no precedence rule. Recommendation: resolve deterministically (order by `code_section`), and **log/flag** any case where two applicable modifications on the same field disagree rather than silently picking. Most-restrictive-wins is not supported by the code's text and should not be asserted.

**Scope guard.** `overlay_standard` supports one field (`min_lot_area_sqft`) at one district (RSA-5). The table shape generalises; the seeded content does not. That is deliberate — see D4 non-goals.

---

## 4. R4 — The other three corrections

### 4a. RSA-5 base → 960

`seed.py` `min_lot_area_sqft: 1440` → `960`. Safe **only** once overlay resolution lands (§3), which is the whole ordering argument in R7. Cite: Table 14-701-1, `14-701(2)(b)[11]#table1`, p.951; verified at the printed page in `eb67a9c`.

### 4b. RM-1 small-lot provision — **the RSA-5 pattern does not transfer clean**

Base provision, verbatim (`14-701(2)(c)[1]` and children):

> "In the RM-1 district, a lot containing at least **1,920 sq. ft.** of land may be divided into lots with a minimum lot size of **960 sq. ft.**, provided that: **(.a)** At least **seventy-five percent (75%)** of lots adjacent to the lot to be divided are **1,000 sq. ft.** or less; and **(.b)** Each of the lots created meets the minimum lot width requirement of the zoning district."

| `SmallLotProvision` field | proposed | code text | note |
|---|---|---|---|
| `trigger_lot_area_sqft` | 1920.0 | "at least 1,920 sq. ft." | exact |
| `min_child_lot_area_sqft` | 960.0 | "minimum lot size of 960 sq. ft." | exact |
| `adjacent_small_share` | 0.75 | "seventy-five percent (75%)" | exact |
| `adjacent_small_max_area_sqft` | 1000.0 | "1,000 sq. ft. or less" | exact |
| `min_lot_width_ft` | 16.0 | "minimum lot width requirement of the zoning district" | RM-1 width = 16 (Table 14-701-2, p.952) |
| `citation` | `§14-701(2)(c)[1]` | — | |

**Two structural differences from RSA-5, both material:**

1. **RM-1's provision has only two provisos.** It lacks RSA-5's *"used for one single-family attached home"* restriction. Immaterial to the arithmetic; relevant to the reasons text, which should not copy RSA-5's wording.
2. **RM-1 has its own overlay variant with different constants.** §14-502(4)(c)(.2), **/CTR Center City Overlay**, "Center City Residential District Control Area":
   > "Lots zoned RM-1 with a lot size of at least **1,600 sq. ft.** may be divided into **two lots** with a minimum lot size of **800 sq. ft.**"

   Different trigger (1,600 vs 1,920), different floor (800 vs 960), and a **hard cap of two lots** that the base provision does not have. `SmallLotProvision` has no field that can express a lot-count cap. **Recommendation: seed the base RM-1 provision only, and treat /CTR as explicitly out of scope for v9** (flagged in the reasons, not modelled). Modelling it needs a schema change to `SmallLotProvision`, which is a slice of its own.

Also found and **out of scope**: §14-533(3)(e)[1] (**/MIN Mixed Income Neighborhoods**) modifies RM-1's *lot area per dwelling unit* — a different field (`lot_area_per_unit_sqft`), correctly excluded by D4's non-goals.

### 4c. Industrial FAR restorations

Table 14-701-4, `14-701(4)(a)[5](.b)#table1`, **p.954**, row *"Max. Floor Area (% of lot area)"*: **500** for IRMX, ICMX, I-1, I-2, I-3; blank for I-P. Seed carries none for all five. Restoring `max_floor_area_ratio_pct: 500`.

Alignment caveat carried from the audit: **this table has no `District Name` header row in `table_data`** (parser defect, filed upstream). Its column mapping was recovered from the provision `text` and corroborated three ways. Of the four tables, this is the one whose values a reviewer should re-check at the page before D3 is signed.

---

## 5. R5 — Impact projection **(PROVISIONAL)**

> **Why provisional.** Local `zoning_standard` already holds RSA-5 = 960 (drifted from the eval branch) while `main`'s seed holds 1,440 — **under the same `code_version` string**, `title14-quickguide-2026-02`. The counts below are computed directly from `parcel.lot_area_sqft` against literal thresholds, so they are *independent of that drift*; but any comparison against **stored verdicts** is not, and must be re-run after re-seeding from `main`. Treat the direction and magnitude as sound and the stored-verdict deltas as unconfirmed.

### RSA-5 — overlay-aware, versus production's flat 1,440

```sql
with rsa5 as (select p.parcel_number, p.lot_area_sqft, exists (select 1 from zoning_overlay o
   where o.market_code='phl' and o.code in ('/FNE','/NE','/NDO','/FDO','/EDO','/SIX')
     and ST_Intersects(o.geom_4326,p.geom_4326)) as in_1440_overlay
  from parcel p where p.market_code='phl'
   and coalesce(p.resolved_zoning_code,p.base_zoning_code) in ('RSA5','RSA-5')
   and p.lot_area_sqft is not null)
select in_1440_overlay, count(*),
  count(*) filter (where lot_area_sqft>=960 and lot_area_sqft<1440) as conformity_flips,
  count(*) filter (where lot_area_sqft>0 and floor(lot_area_sqft/960)>floor(lot_area_sqft/1440)) as maxlots_increases
from rsa5 group by 1;
```

| | parcels | conformity flips | max_lots increases |
|---|---|---|---|
| **outside** the six overlays | 175,843 | **58,540** | **68,280** |
| **inside** the six overlays | 136,783 | *54,376 → **0*** | *75,032 → **0*** |

**The in-overlay zero falls out of the design, it is not asserted.** Inside the six, the effective minimum resolves to 1,440 — numerically identical to what production already stores — so the comparison is between equal values and no verdict can move. The 54,376 and 75,032 figures are precisely what a *bare scalar* correction would have changed, and they are exactly the false positives the audit measured.

**Net v9 RSA-5 delta: 58,540 conformity flips (all corrections of genuine false negatives) and 68,280 subdivision changes.** Against the bare-scalar alternative's 112,916 flips of which 54,376 would be wrong.

### RM-1 — **and a correction to the audit**

| measure | count |
|---|---|
| RM-1 parcels | 75,824 |
| **≥ 1,920 (base §14-701(2)(c)[1] trigger)** | **10,946** |
| ≥ 1,600 (/CTR variant trigger — out of scope) | 19,435 |
| upper bound on max_lots increases at a 960 floor | 39,759 |

**The audit's §4 misstates this.** It reads *"19,435 of them clear the 1,920 trigger"* — 19,435 is the **≥1,600** count; the ≥1,920 count is **10,946**. Two columns of the same query were transposed in the prose. The audit's *conclusion* is unaffected (RM-1's provision is missing and the fix is additive), but the headline number is wrong by 1.8×. **Recommendation: correct §4 and §6 of the audit in the v9 ADR's evidence section rather than silently restating.** Surfaced under D3.

Actual reachable count is below 10,946 — every candidate is still gated on the ≥75%-adjacency test, which needs the assemblage computation per parcel and cannot be projected in SQL.

### Industrial FAR

| district | parcels | with lot area |
|---|---|---|
| I2 | 3,097 | 3,031 |
| ICMX | 2,982 | 2,921 |
| I1 | 679 | 672 |
| IRMX | 606 | 586 |
| I3 | 420 | 407 |

**7,784 parcels; 7,617 with area.** Effect is additive — `estimate_density_units` gains a `far_estimate` basis where it currently returns none. No existing number changes; unit estimates appear where they were previously absent.

### Combined v9 delta (provisional)

Direction is one-way for RSA-5 and RM-1 (more permissive: false negatives corrected) and additive for industrial. **No correction in v9 makes any parcel *less* buildable** — which is worth stating plainly, because it means the release cannot introduce the false-positive class the audit warned about, *provided* overlay resolution ships in the same commit as the seed change.

---

## 6. R6 — `verify-zoning-standards`

**Built against the effective layer, and value-based — never version-based.** The drift in §5 is the argument: RSA-5's value changed from 1,440 to 960 while `code_version` stayed `title14-quickguide-2026-02`. Any check keyed on the version stamp is blind to precisely the error class it exists to catch.

**Scope — exhaustive, not sampled.** The space is small: 39 districts × 7 dimensional fields for the base layer, plus 6 overlay modifications. Exhaustive comparison is cheap and removes sampling risk.

**Two passes:**

1. **Base:** each seeded value vs the corresponding `code_provision.table_data` cell, aligned via each table's `District Name` header row — *never* by column position. Table 14-701-4 has no header row and must align via its provision `text` (§4c). Conditional cells (the 25 in the audit) need an explicit allowlist keyed to `district × field`, or the check reports 25 false alarms every run.
2. **Overlay:** each `overlay_standard` row vs the verbatim text of its `citation`, asserting the numeral appears in the cited provision; plus a referential check that every `code_section` in `overlay_standard` matches at least one `zoning_overlay` polygon.

**Invocation:** `make verify-zoning-standards` → `python -m lotscope.zoning.verify`, exit nonzero on divergence, mirroring `verify-derivation`. **Runtime:** seconds — all reads, no spatial work.

**Precondition:** requires a loaded phillycode corpus, so like `verify-derivation` it is an **ops command, not a CI test** — CI provisions an empty testcontainer and the check would fail for the wrong reason.

---

## 7. R7 — Recompute and rollout

### Ordering — the whole safety argument

1. **Alembic migration** — create `overlay_standard` (hand-written; autogenerate is untrusted in this repo).
2. **Seed** the six overlay rows **and** flip the RSA-5 base to 960 **and** add RM-1's provision **and** the five industrial FARs — **one commit.** The base flip and the overlay layer must be atomic; a deploy that lands 960 without the overlay rows is exactly the ~54,376-parcel false-positive window the audit warned about.
3. **Resolution change** — `_get_standard` overlay awareness (§3).
4. **`VERDICT_VERSION` v8 → v9** (`verdict/composition.py:14`).
5. **Deploy**, then **recompute**.

### Recompute

`make recompute-verdicts` → `python -m lotscope.verdict.jobs`, batch size 500 (`jobs.py:25`).

Scope: **550,945 phl parcels** (pgh 143,355 / wlm 26,197 / hbg 19,502 unaffected — v9's corrections are phl-only, so **scope the recompute to `market_code='phl'`** rather than running all 740k). Existing `parcel_verdict` rows: 476,404 v5, 228,600 v8, 34,491 v7, 16 v6.

**Runtime is unestimated and should be measured, not guessed** — the RSA-5 path now adds a live `ST_Intersects` per parcel (no materialized membership, §2). At 313k RSA-5 parcels that spatial join is the dominant cost and is new work the current recompute does not do. **Recommendation: benchmark a 5,000-parcel batch before scheduling, and treat materialising `parcel_overlay` as a live option if the projection is poor.** Do not schedule the full run on an unmeasured estimate.

### Locks and deploy safety

`overlay_standard` is a **new** table — `CREATE TABLE` takes no lock on hot tables, so the migration itself is safe. The recompute writes `parcel_verdict` in 500-row batches (no long transaction). `scripts/deploy.sh` takes a `pre-migration` backup automatically when migrations are pending (`docs/runbook.md:109`), which this deploy will trigger.

### ADR evidence recording

One ADR, four corrections, each carrying: the audit reference, the page/`code_provision` cite, and the measured flip count from §5 — with the RM-1 figure **corrected** per §5.

---

## 8. Named decisions

### D1 — Effective-standard architecture
**Recommend as §3:** seeded `overlay_standard` keyed on `code_section`; `_get_standard` gains optional `parcel_number`; `DistrictStandard` gains an additive `overlay_modifications` list carrying both cites. All eight consumers funnel through one seam and none breaks. **Conflict rule: deterministic order + flag on disagreement — do not adopt most-restrictive-wins**, which the code's text does not support and which no measured parcel needs (32 multi-overlay parcels, all agreeing).
**Sub-decision:** key on `code_section` (simpler) or polygon-level (technically correct)? Measured divergence is 24 parcels / 0.04%. **Recommend `code_section`**, with the 24-parcel discrepancy recorded in the ADR.

### D2 — The seeded overlay modifications
**Recommend the six rows in §3**, all `RSA-5 / min_lot_area_sqft / 1440`, cited to the operative subsection (`§14-514(5)(a)`, `§14-515(2)(c)(.1)`, `§14-520(4)(a)`, `§14-524(2)(a)`, `§14-530(2)`, `§14-548(3)(a)(.3)`).
**Attached defect to fix in the same slice:** the blanket `has_overlay` suppression at `analysis.py:197` is wrong — these overlays *preserve* the small-lot exception. v9 should replace the suppression with the effective minimum plus the overlay's own (identical) small-lot terms.

### D3 — RM-1 constants and industrial FAR
**Recommend** the six-field `SmallLotProvision` for RM-1 in §4b (all five constants verbatim-matched), **base provision only** — /CTR's 1,600/800/two-lot variant is out of scope and needs a schema change. Reasons text must not copy RSA-5's, which carries a proviso RM-1 lacks.
**Industrial FAR: 500 for IRMX/ICMX/I-1/I-2/I-3**, p.954 — but this is the header-less table; **re-check at the page before signing.**
**Also under D3:** approve correcting the audit's RM-1 count (19,435 → 10,946) in the ADR's evidence section.

### D4 — ADR-v9 outline
Corrections: (1) overlay-aware effective standards, (2) RSA-5 base → 960, (3) RM-1 small-lot provision, (4) five industrial FARs. Evidence: audit reference + page cite + measured flips per correction. **Non-goals, explicit:** general overlay dimensional support beyond `min_lot_area_sqft`; use-permission overlays; /CTR's RM-1 variant; /MIN's `lot_area_per_unit_sqft`; other markets; the 25 conditional cells; RMX-3's unresolved setbacks.

### D5 — `verify-zoning-standards`
**Recommend §6:** exhaustive, **value-based not version-based**, two passes (base + overlay), header-row alignment with a documented exception for Table 14-701-4, an explicit allowlist for the 25 conditional cells, `make verify-zoning-standards`, ops command not CI.

### D6 — Sequencing, and whether v9 waits for PAUSE 2
**Recommend: yes, wait — but the dependency is narrow and can be cut.** The only overlap is `zoning/seed.py` plus `test_seed_dimensional.py`. If 98cadfa is dropped from the eval branch (which restores that slice to its own stated constraint — *"this slice measures shipped behaviour, and a change to `zoning_standard` moves stored verdicts"*), the branches are disjoint and v9 need not wait for the cutover decision at all. **Preferred path: drop 98cadfa, adopt its `test_seed_dimensional.py` into v9, and let v9 and Slice 4 proceed in parallel.** Failing that, v9 waits.
Rollout per §7, with the **atomicity requirement** as the non-negotiable: base 960 and the overlay rows ship in one commit, or not at all.

---

## 9. Open items for the owner

1. **PR #143 is unmerged** — v9's evidence base is not on `main`.
2. **`zoning_overlay.last_synced_at` is NULL on all 193 rows.** The effective standard is only as good as this layer and it currently carries no freshness signal.
3. **Membership is `ST_Intersects`** — boundary-touching parcels count as inside. Errs restrictive (safe), but should be a recorded choice.
4. **Recompute runtime is unmeasured** and now carries a new per-parcel spatial join. Benchmark before scheduling.
5. **Parser defect** (Table 14-701-4 header row) remains filed upstream, unpatched.
