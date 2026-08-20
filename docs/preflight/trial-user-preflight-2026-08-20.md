# Pre-flight — first external trial user, 2026-08-20

Read-only. Every figure below came from a query against production or a live primary source; nothing was written, and nothing found here was fixed in passing. Findings are findings.

**Who.** A sheriff-sale-only buyer holding six vacant Philadelphia lots in two clusters — the Norris corridor (`phl:201133900` 1943 N MARSHALL ST, `phl:191357500` 2138 N FAIRHILL ST, ~325 m apart) and a Mantua/Parkside triangle (`phl:062284300` 810 N 42ND ST, `phl:243169100` 3966 PENNSGROVE ST, `phl:243037700` 3862 ASPEN ST, ~650 m) — plus `phl:362363700` 1329 GROVE ST and roughly eight developed parcels. She is an expert on exactly these parcels and on nothing else in the database, so every field below is one she can falsify from her own closing file.

She is referred to throughout by parcel rather than by name. Her name and mailing address are public record in OPA, but §13 says minimise, and the report reads no worse for it.

**Verdict in one line: not yet.** One defect in the delinquency-attribution join misreads two of her six lots, and the assessment sweep's headline numbers are mostly artifacts. Both are stated precisely below; neither is a blocker to *building*, both are blockers to *showing*.

---

## 1. Five-lot QA sweep

Sources: production `parcel` / `sale` / `tax_status` / `li_event` and the live v11 verdict surface, 2026-08-20; primary sources are Carto `opa_properties_public`, Carto `rtt_summary`, and the city's ArcGIS `Zoning_Overlays` layer, queried the same day.

### 1.1 Deeds and consideration — 6/6 exact

Every deed matches RTT to the dollar, the party, and the document type.

| parcel | our deed | RTT primary source | verdict |
|---|---|---|---|
| `phl:201133900` | 2025-05-08, $33,900, SHERIFF'S DEED, doc 54420482, grantor MATUSOW JOSEPH;MUTNSON JOSEPH | identical; RTT display 2025-03-03, recording 2025-05-08 | ✅ |
| `phl:191357500` | 2025-05-08, $29,100, SHERIFF'S DEED, doc 54420480, grantor ADAMS THOMAS | identical | ✅ **and see 1.2** |
| `phl:062284300` | 2025-03-17, $5,100, SHERIFF'S DEED, doc 54402338 | identical; display 2025-02-25 | ✅ |
| `phl:243169100` | 2025-03-04, $16,600, SHERIFF'S DEED, doc 54398055 | identical; display 2025-01-29 | ✅ |
| `phl:362363700` | 2024-08-29, $32,100, SHERIFF'S DEED, doc 54336921 | identical; display 2024-08-04. **RTT returns this deed twice** — an upstream duplicate, correctly deduplicated by us on `(parcel_number, document_id)` | ✅ |
| `phl:243037700` | 2025-03-04, $26,900, SHERIFF'S DEED, doc 54398054, grantor ASBELL WILLIAM;ASBELL DORA | identical; display 2025-01-29 | ✅ |

**Expected divergence to have an answer ready for.** OPA's `sale_date` is the auction date; ours is the recording date, from RTT. On `phl:201133900` OPA says 2025-03-03 and we say 2025-05-08 for the same $33,900 transaction. She will read that as an error. It is two sources recording two different real events, and both are right.

### 1.2 One lot where we beat the primary source

`phl:191357500`'s deed (doc 54420480) exists in RTT with **`opa_account_num = NULL`** — upstream cannot key it to a parcel. We hold it attached to the right parcel with the right grantor, grantee, date and price. Verified by querying `rtt_summary` on `document_id` directly: the row is there, keyless. This is address-index deed recovery working on one of her own lots, and it is the most defensible single demonstration in the whole account.

### 1.3 Attributes — 6/6 match OPA

Assessed value, lot area, zoning and land use agree exactly on all six: 884/RM1, 797/RSA5, 812/RSA5, 1318/RSA5, 700/RM1, 1440/RSA5 sq ft; assessments $66,800 / $40,800 / $37,700 / $44,900 / $83,900 / $48,900. Overlays spot-checked against the city's live layer at `phl:201133900`'s centroid (−75.14514, 39.98115): ArcGIS returns `/VDO Fifth District` and `/NIS Narcotics Injection Sites`, which is exactly what our flag names.

### 1.4 Delinquency posture — 4 of 6 correct, **2 wrong, and the cause is a defect**

Every one of the six was a sheriff purchase, so every one should carry the informational, prior-owner-named treatment.

| parcel | posture | severity | names her deed's grantor? |
|---|---|---|---|
| `phl:201133900` | `likely_discharged` | info | ✅ MATUSOW JOSEPH |
| `phl:191357500` | `likely_discharged` | info | ✅ ADAMS THOMAS |
| `phl:062284300` | `likely_discharged` | info | ✅ ANDERSON JR AUGUSTINE |
| `phl:243169100` | `likely_discharged` | info | ✅ SMITH WILLIAM |
| **`phl:362363700`** | **`verify`** | **medium** | ❌ "MCNAIR KENNETH, not the owner of record" — **MCNAIR KENNETH is the third grantor on her own deed** |
| **`phl:243037700`** | **`verify`** | **medium** | ❌ "ASBELL WILLIAM, not the owner of record" — **ASBELL WILLIAM is the first grantor on her own deed** |

**Root cause, proven.** `normalize_party_key` does not split multi-party grantor lists on `;`, so `_tokens()` splits on whitespace and produces fused tokens. Run directly:

```
'MCNAIR KENNETH' vs 'CONNOR JOHN J;CONNOR JOHN J ESTATE OF;MCNAIR KENNETH' -> none   (MCNAIR fused into 'OF;MCNAIR')
'ASBELL WILLIAM' vs 'ASBELL WILLIAM;ASBELL DORA'                           -> none   (WILLIAM fused into 'WILLIAM;ASBELL')
'MATUSOW JOSEPH' vs 'MATUSOW JOSEPH;MUTNSON JOSEPH'                        -> partial
'SMITH WILLIAM'  vs 'SMITH WILLIAM WILKER;SMITH WILLIAM ESTATE OF'         -> partial
```

The four that pass, pass by luck: enough of their tokens happen to fall clear of a semicolon to reach `_MIN_SHARED_TOKENS = 2`. Whether a sheriff-sale buyer is told the debt is the prior owner's therefore depends on where the semicolons land.

**Scope, measured on production.** Philadelphia parcels that are delinquent, whose first post-snapshot deed is a sheriff's deed with a multi-party grantor: **1,077**. Of those, the posture flips from `verify` to `likely_discharged` if the grantor list is split on `;`: **297**, of which **201 are vacant lots**. Two of them are hers.

**Consequences.** `counts_toward_distress` is `False` on both sides of this flip, so distress scores are unaffected — confirmed: both parcels score 20/low from vacancy + absentee only, with no prior-owner signal. But severity moves `info` → `medium`, and both affected lots carry **risk 60** against 30/40/10/10 on the four correct ones. So it moves `risk_score` and therefore `opportunity_score`.

**This is a third, distinct normalisation defect** alongside the two already queued in `docs/verdict-bump-queue.md` (single-letter runs; the literal `'not available'`). Same trap applies and is already documented there: the fix belongs in `party_match`, not `normalize_party_key`, which has a SQL twin backing a generated column. **It must ride a version bump** — it moves stored scores, and lazy recompute fires only on version mismatch.

Reported, not fixed, per the brief.

### 1.5 Two more things she will notice on her own lots

**`phl:243037700` shows the wrong owner.** Our `parcel.owner` reads `WM ASBELL` with a 1947 sale of $1, because OPA has not processed her 2025 deed. Our deed record is right and the dossier's sale history will show her purchase; the owner *field* will name a man who sold the lot before she was born. This is the Aspen class, already known — but it is worth knowing that it renders as a wrong name on a lot she owns, not merely as a stale date.

**`phl:191357500` is not marked vacant.** `is_vacant` is `NULL` while OPA's land use reads `VACANT LAND - RESIDENTIAL`. Visible consequences on her own data: its distress composition is missing the `Vacant lot` +10 that all five siblings carry (it scores 15, not 20), and it will not appear in vacant-only searches or on the vacant-lot map layer. This is the known `phl`-vacancy-fallback carry-forward; it is recorded here because her portfolio is where it becomes legible — five lots behave one way and the sixth does not.

### 1.6 Open vs on-record violations — 6/6 correct

`phl:191357500` is the only lot with genuinely open violations: 8 on record, **2 still open** (both `OPEN` / `IN VIOLATION`, dated 2026-07-28). Every other lot's violations are `COMPLIED`/`CLOSED` and are reported as on-record history. `phl:362363700` carries 8, all complied. `phl:243037700` carries 4, all complied. `phl:201133900` carries 1, complied. The split is right on all six.

### 1.7 Distress composition — 6/6 clean of prior-owner signals

| parcel | score | composition |
|---|---|---|
| `phl:201133900` | 20 / low | Vacant +10, Absentee +10 |
| `phl:191357500` | 15 / low | Open L&I +5, Absentee +10 (no Vacant — see 1.5) |
| `phl:062284300` | 20 / low | Vacant +10, Absentee +10 |
| `phl:243169100` | 20 / low | Vacant +10, Absentee +10 |
| `phl:362363700` | 20 / low | Vacant +10, Absentee +10 |
| `phl:243037700` | 20 / low | Vacant +10, Absentee +10 |

No prior owner's delinquency counts toward any of them, which is the batch's whole purpose meeting its exact target population. Absentee is present on all six, so the mailing backfill reached her portfolio. All six score under `philly-distress-v2`.

### 1.8 Snapshots — generated post-fix, six clean, four claims to watch

Generated with the v11-vocabulary generator against the 2026-08-18 local production copy. No snapshot calls a complied violation active, and none reads a named distress signal as evidence of absence. `phl:191357500` reads "Two open L&I violations … remain unresolved; eight violations are on record overall" — the exact distinction that was wrong before.

Falsifiable claims that go beyond the facts supplied, in descending order of concern:

1. **`phl:243169100`** — "absentee … suggesting investor positioning rather than active redevelopment interest." A motivational conclusion the score legend explicitly forbids. She is the absentee owner; being told her intent is inferred from her mailing address is the worst sentence in the set.
2. **`phl:062284300`** — "current title is clean of this burden." The source says *likely* discharged, verify with Revenue. The snapshot dropped the hedge on a lien question.
3. **`phl:243037700`** — "a low-to-medium mixed-income overlay." The flag's *severity* is low; the overlay is `/MIN Mixed Income Neighborhoods`. The model fused the two into a property of the overlay that does not exist.
4. **`phl:191357500`** — "Ownership is current and not tax-delinquent." A defensible reading of an informational flag, but stated as fact about her rather than about the record.

None is a vocabulary regression; all four are the generator reaching past its facts. Worth a prompt tightening before a wider send, not before this one.

---

## 2. Assessment sweep across the portfolio

Thirteen parcels — the twelve attributed to her in OPA plus `phl:243037700`. Read-only, existing modelled-market machinery, production, 2026-08-20.

| parcel | address | vacant | assessed | modelled market | status | est. saving/yr | confidence |
|---|---|---|---|---|---|---|---|
| `phl:121045000` | 59 E GARFIELD ST | – | $173,300 | $53,195 | over | **$1,681** | medium |
| `phl:421187000` | 128 E WELLENS ST | – | $181,000 | $101,229 | over | **$1,117** | low |
| `phl:352285800` | 5945 MALTA ST | – | $159,400 | $84,971 | over | **$1,042** | medium |
| `phl:352272000` | 5918 COLGATE ST | – | $167,800 | $94,454 | over | **$1,027** | medium |
| `phl:592306600` | 6224 CLEARVIEW ST | – | $159,600 | $88,115 | over | **$1,001** | medium |
| `phl:492125600` | 5159 N 8TH ST | – | $142,000 | $72,551 | over | **$972** | low |
| `phl:362363700` | 1329 GROVE ST | ✅ | $83,900 | $58,126 | over | **$361** | medium |
| `phl:651147800` | 4729 SHEFFIELD AVE | – | $197,300 | $217,941 | under | — | medium |
| `phl:243037700` | 3862 ASPEN ST | ✅ | $48,900 | $102,857 | under | — | low |
| `phl:243169100` | 3966 PENNSGROVE ST | ✅ | $44,900 | $61,661 | under | — | medium |
| `phl:062284300` | 810 N 42ND ST | ✅ | $37,700 | $49,933 | under | — | medium |
| `phl:201133900` | 1943 N MARSHALL ST | ✅ | $66,800 | $62,363 | fair | — | low |
| `phl:191357500` | 2138 N FAIRHILL ST | – * | $40,800 | $44,682 | fair | — | low |

\* `is_vacant` is NULL; the lot is vacant land (see 1.5).

**Six of the seven "found money" claims are artifacts. Do not show them.**

`analyze_parcel_assessment` calls `value_parcel`, whose `vacant_only` defaults to `True`. On a developed parcel it therefore compares an improved property's assessment against a **vacant-land** estimate. Proven directly on the largest claim, `phl:121045000`:

> *"Estimate from 4 comparable land sale(s); median $22/sqft applied to 2,367 sqft."* — comps used: 32 E WISTER ST, 4930 BAYNTON ST, 47 W SEYMOUR ST, 211 E BRINGHURST ST, 4940 RUBICAM ST, all vacant lots.

A rowhouse assessed at $173,300 is "over-assessed" because empty lots nearby trade at $22/sqft. The $1,681 is not a saving; it is a category error. The same construction produces every other developed-parcel row in the table.

**And the disclaimer is on the wrong tab.** `ParcelDossier` shows a banner — *"This parcel already has a structure … the buildability, land value, and deal figures below model a hypothetical teardown or redevelopment — not the property's current value"* — but only on the **verdict** tab. `AssessmentPanel`, with its over-assessment figure and its **$79 appeal-packet** button, sits on the **deal** tab, which carries no such banner. So the number appears with a price attached and the caveat one tab away.

**The only defensible talking point in the whole sweep is `phl:362363700` — 1329 GROVE ST, $361/yr, medium confidence** — a vacant lot valued against vacant-land comps, model matched to subject. Even that carries the standing low-confidence caveat: the estimate rests on a thin, dispersed comp set, and $361 is an order-of-magnitude indication, not a number to put in a filing.

Reported, not fixed. The gating question — whether the assessment surface should render at all on a developed parcel — is a product decision, not an edit.

---

## 3. Sheriff-sale list recon (timeboxed)

**What the scraper captures.** Production `sheriff_sale` holds **867 upcoming rows across 10 sale dates** (2026-08-25 through 2026-09-25 and beyond). Parcel linkage is near-complete — 62/62, 56/56, 357/357, 25/25, 113/113 keyed on the major dates; only one batch of 5 on 2026-09-08 is unkeyed. Opening bids are largely present (62/62, 228/357, 110/113), which is the COALESCE merge preservation accumulating across nightly runs as intended. Joined to `parcel`, the vacant subset per sale date runs **11–36 lots** — a curatable size.

**Answer: curation-feasible, but not by the route you would reach for first.**

The obvious route does not work. `AreaSearchRequest.sheriff_sale_only` filters on `coalesce(ts.in_sheriff_sale, false)`, which is the Revenue delinquency dataset's flag — 989 parcels — and it has **zero overlap** with the 866 distinct parcels on the scraper's upcoming calendar. Measured:

```
tax_status.in_sheriff_sale = true                              989
upcoming sheriff_sale parcels                                  866
…of which also flagged in tax_status                             0
```

Two disconnected populations wearing the same name. A saved search with `sheriff_sale_only` would return next month's list to nobody.

The route that works today, with no build: query the existing sheriff-sale calendar for a sale date, take the parcel numbers whose `parcel.is_vacant` is true, and seed them into a saved list by parcel number — the same mechanism the concierge runbook uses for her six lots. That is admin curation.

**To the feature ledger at 0-of-3:** connecting `sheriff_sale_only` to the live sheriff-sale calendar so that upcoming-auction lots are reachable from search. It is the single highest-leverage thing for a buyer who sources exclusively at sheriff sales, and it still waits for three named requests.

---

## 4. What has to be true before she sees this

**Blocking:**

1. **Nothing.** Both defects above are showing-problems with curation answers, not build gates — provided §2's numbers stay out of the first session and §1.4's two lots are either explained or left out of the seeded list.

**Must be decided, not built, before the send:**

2. **The $79 appeal-packet CTA.** It will render on developed parcels in her portfolio against vacant-land arithmetic. Either keep her first-session path on the six vacant lots, or comp the packet. Do not leave it as a paywall over a number we cannot defend.
3. **`phl:362363700` and `phl:243037700` will show a medium-severity delinquency flag** naming a party who is a grantor on her own deed. If she opens either, she will catch it — she was in the room when those deeds were signed. Better she hears it from us first, framed as a known join defect with a measured population of 297.

**Already true and worth leaning on:** six deeds exact against RTT, one of them recovered from a keyless upstream row; overlays exact against the city's live layer; every prior owner's debt correctly kept out of her distress score; open-vs-complied violations right on all six.
