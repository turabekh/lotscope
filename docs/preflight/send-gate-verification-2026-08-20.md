# Send-gate verification — 2026-08-20 (second pass)

Everything below was verified over the serving path a user actually touches — HTTPS against production, authenticated as a registered account — or by query against a dated database copy. Session memory was not accepted as evidence for anything.

The account used was registered, used, and deleted; child-row counts reconciled (§6).

---

## 1. Charter reconciliation

| deliverable | status | evidence |
|---|---|---|
| 2.1 valuation attribution | **VERIFIED, and completed this session** | `docs/v11-delta-ledger.md` §"Diligence: the flagship parcel's valuation move" — table of both numbers, stored provenance `comp_count: 22`, exact leave-one-out reconstruction, four-cause exclusion table. The in-flight-ingest hypothesis was excluded only by absence; it is now excluded positively (§2 below) |
| 2.2 portfolio residual | **VERIFIED** | same file, §"Residual: the owner-portfolio count is short by one" — class stated as `owner_2` matching not lag, proven arithmetically ($1,454,500 + $143,700 = $1,598,200), marked out of scope per ADR non-goals |
| 2.3 CLAUDE.md — three-ICP rule | **VERIFIED** | Golden Rule 10 |
| 2.3 CLAUDE.md — ingested-column coverage | **VERIFIED** | §12, "post-ingest query against the destination table shows populated coverage" |
| 2.3 CLAUDE.md — cache-key rule | **WAS MISSING — added** | §12. The fix shipped last session; the rule did not. The code also only half-satisfied it (§4) |
| 3.2 assessment sweep | **VERIFIED** | `docs/preflight/trial-user-preflight-2026-08-20.md` §2 — 13-row table, assessed / modelled / status / saving / confidence |
| 3.3 sheriff-sale recon | **VERIFIED** | same file §3 (curation-feasible, but not via `sheriff_sale_only`), ledgered at 0-of-3 in `docs/feature-ledger.md` |
| Phase 4 runbook | **VERIFIED** | `docs/runbooks/trial-concierge-seeding.md` — both saved-search bodies with centroids, tier flip, seeding, verification pass, and a "what NOT to do" section carrying the paid-CTA decision |

---

## 2. The valuation loose end, closed

`sale` was written twice on 2026-08-18, at 04:01 and 04:14 — both after the flagship's 03:56:40Z compute, and the only writes between the 08-16 ingest and the copy.

| burst | market | rows |
|---|---|---|
| 04:01Z | `hbg` | 11,768 |
| 04:14Z | `pgh` | 17,344 |
| | **`phl`** | **0** |

Nearest touched parcel carrying geometry: **484,530 ft (~92 miles)** from the subject. The in-flight-ingest hypothesis is dead. Full entry and provenance in the delta ledger.

---

## 3. Five-lot sweep, re-run over HTTPS

All six snapshots regenerated live (`computed_at` within minutes of the request), all `v11`.

### 3.1 Delinquency posture — the attribution logic on its exact target population

| parcel | severity | posture | names her deed's grantor |
|---|---|---|---|
| `phl:201133900` 1943 N MARSHALL | `info` | discharged | ✅ MATUSOW JOSEPH |
| `phl:191357500` 2138 N FAIRHILL | `info` | discharged | ✅ ADAMS THOMAS |
| `phl:062284300` 810 N 42ND | `info` | discharged | ✅ ANDERSON JR AUGUSTINE |
| `phl:243169100` 3966 PENNSGROVE | `info` | discharged | ✅ SMITH WILLIAM |
| `phl:362363700` 1329 GROVE | **`medium`** | verify | ❌ MCNAIR KENNETH is her deed's 3rd grantor |
| `phl:243037700` 3862 ASPEN | **`medium`** | verify | ❌ ASBELL WILLIAM is her deed's 1st grantor |

**No lot shows a deal-killer delinquency.** The failure mode is `medium`/verify, not `high`. Risk scores: 30 / 40 / 10 / 10 against **60 / 60** on the two degraded lots.

Root cause unchanged and already filed in `docs/verdict-bump-queue.md`: `normalize_party_key` does not split grantor lists on `;`. 297 phl parcels (201 vacant) flip once split.

**Verdict on the logic against its target population: four of six correct, and the two failures are one defect with a measured population and a queued fix.** The four that pass do so because their tokens happen to fall clear of a semicolon — the logic is right and its input normalisation is not.

### 3.2 Violations open-vs-on-record — 6/6 correct over HTTPS

`phl:191357500` is the only lot with open violations and its snapshot says "two open L&I violations"; the other five describe complied history ("all been complied with and closed", "four L&I violations now closed", "no code violations are on record").

### 3.3 Falsifiable claims in this run

1. **`phl:362363700`** — *"requiring title review for modified buildability standards."* The source says check **Title 14** for overlay standards. The model turned a zoning-code citation into a title-search recommendation. Wrong professional, wrong document.
2. **`phl:362363700`** — *"owed 2022–2024."* The facts say $7,839 over 25 years, recorded as of 2022-06. The range is invented.
3. **`phl:062284300`** — *"estimated tax-appeal savings are unspecified."* Awkward but true (the lot is under-assessed, so there is no saving).

Last session's worst claim — "suggesting investor positioning rather than active redevelopment interest" on `phl:243169100` — did **not** recur.

### 3.4 Aspen, the hard case: how OPA lag degrades three surfaces

`phl:243037700`, purchased by sheriff's deed 2025-03-04 (doc 54398054, $26,900). OPA has not processed it, so its record still names the 1947 owner.

| surface | what it serves | consequence |
|---|---|---|
| parcel detail `owner` | **`WM ASBELL`** | her name appears nowhere on the page for a lot she owns; only the deed history shows her purchase |
| distress `absentee` | **+10, awarded** | correct outcome, **wrong input**: `is_absentee(address, mailing_address)` compares `3862 ASPEN ST` against **`3706 HAMILTON ST PHILADELPHIA PA 19104`** — the 1947 owner's mailing address, not hers. Right answer, wrong person's record |
| owner-portfolio panel | **`WM ASBELL` · 1 parcel · $48,900 · `parcels: []`** | her twelve-parcel portfolio is invisible from this page; the panel tells her she owns one lot, under someone else's name |

This is the ledgered OPA-lag residual with its surfaces enumerated. It remains out of scope, but it is a page she may open, and it fails visibly on all three.

---

## 4. The cache-key rule was codified and the code half-violated it

Three AI caches existed. Only one carried a prompt version; none carried the model.

| cache | before | after |
|---|---|---|
| `summary:` | prompt version + verdict version | + model |
| `report:` | verdict version only | + prompt version + model |
| `ask:` | parcel + source + question digest | + prompt version + model |

Codifying a rule the code knowingly breaks is the "guard that cannot fail" pattern the ledger already tracks, so all three were brought into line through one shared scope helper. Three tests, including that a model swap invalidates a cached answer.

---

## 5. Assemblage interrogation — `1941 N MARSHALL ST` (`phl:881000216`)

### 5.1 The arithmetic is exact

RM-1: `min_lot_area 1,440` · `min_lot_width 16` · `lot_area_per_unit 480`.

- base `2,666 // 480 = 5` ✅
- combined `4,624 // 480 = 9` ✅
- combined area `2,666 + 884 + 1,074 = 4,624` ✅ exact
- delta **+4** ✅

**"9+4" is not a rendering bug.** `AssemblagePanel.vue` renders `{{ from }} → {{ to }}` and a separate `+{{ added }}` chip, i.e. **5 → 9, +4**, with a sub-line that already says "could add about 4 more unit(s)".

### 5.2 The combined lot is never dimensionally gated — FINDING

`estimate_density_units` returns `max(1, int(area // per_unit))` with **no conformance check**. It never calls `_check_conformance`, which is what single-lot verdicts run and what fails `phl:201133900` on both area (884 < 1,440) and width (14 < 16).

Here the combined lot would pass anyway — 4,624 ≥ 1,440 and 42.1 + 14 + 17 = **73.1 ft** ≥ 16 — so the **9 is defensible for this trio**. But it is right by the arithmetic of this case, not because the engine checked. The same code path will report by-right units for a combined lot that fails the minimums.

### 5.3 Existing improvements are not modelled at all — FINDING

`1941 N MARSHALL ST` is **`APARTMENTS > 4 UNITS`**, assessed at **$1,265,600**. `by_right_units_current: 5` is raw area ÷ 480; the standing building is not an input anywhere.

The existing hedge reads: *"confirm zoning by-right outcomes for the combined lot."* That hedges the **zoning**, not the **structure**. Nothing on the panel says the base parcel is already built, and "5 → 9, +4" invites the reading that four units can be added — a reading that requires reconciling an existing >4-unit building the panel never mentions. **The hedge is not sufficient.** Wording-level finding; no engine change proposed.

### 5.4 `is_city_owned` is structurally unpopulated for Philadelphia — FINDING

`1935 N MARSHALL ST` is owned by **`CITY OF PHILA`** per OPA. The assemblage panel serves `is_city_owned: null`, `has_city_owned_neighbor: false`, `acquirability: "vacant"`.

Measured: **1 of 588,591** phl parcels carries `is_city_owned = true`; 588,586 are NULL. Meanwhile **11,956** phl parcels have an owner string reading `CITY OF PHILA`, Land Bank, or PHDC. The flag is set by loaders for `pgh`, `hbg` and `wlm` — **there is no `phl` loader that sets it at all.**

Consequence for this demo: a City-held parcel is presented as an ordinary private vacant lot. Those are different acquisition paths — a private negotiation versus a Land Bank / PHDC disposition. Report only; a phl derivation is a new capability and goes to the ledger at 0-of-3.

### 5.5 Reciprocity holds, but the story does not run both ways

- `phl:201133900` (hers) and `phl:201133501` both serve `needs_consolidation: true` on the subdivision surface — that is the "consolidation candidate" label, and it is **reciprocal** ✅
- Assemblage potential is `none` for both, with 0 candidates — **geometrically correct**: only 1941 touches both vacant lots; 1943's neighbours are 1941 and 1945, both built.

No surface contradicts another factually. But the **framing** does not run both ways: from `1941`'s page the product says "strong assemblage potential, 2 candidates" — one of which is her lot. From her own page it says there is no assemblage play. **The assemblage story on 1941 is the neighbour's acquisition thesis about her land.** Showing it to her in a demo needs deliberate framing, or it reads as the product helping someone else buy her lot.

One softer tension on her own page: subdivision says *needs consolidation*, assemblage says *no easy assemblage*. Both true under the engine's definitions; together they read as confusing counsel.

---

## 6. Test-account hygiene

Registered `id 39` (free tier), used for every HTTPS check above, then deleted. All seven user-keyed tables checked for child rows before deletion (`appeal_packet`, `credit_ledger`, `deal`, `saved_parcel`, `saved_search`, `underwriting_profile`, `push_subscription`) — zero in each. Post-delete: 0 rows for id 39, **11 real accounts remaining**, token returns 401.
