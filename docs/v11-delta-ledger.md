# v11 delta ledger

Appended as each slice proves its own delta, so Slice 5's ADR consolidates measured numbers rather than re-derived ones. Every figure carries where it came from.

**Version:** `VERDICT_VERSION` v10 → v11 · distress profile `philly-distress-v1` → `philly-distress-v2`.

---

## Distress: violations that were never open (Slice 2)

| | |
|---|---|
| violations counted "Open" that are not open | **273,271 of 343,862 (79.5%)** |
| parcels with violations but none open | **68,750** |
| effect | each loses `li_violations` +5 |

**Provenance:** production `li_event`, 2026-08-16, `group by upper(status)`.

**The 14,017-row judgement call.** Upstream, 14,017 rows read `COMPLIED` on `violationstatus` and `IN VIOLATION` on `casestatus` — the line item complied while the case stayed live. `is_open_violation` requires `violationstatus = 'OPEN'` first, so **these resolve as not-open**.

Consequence, stated plainly: an owner with a live case whose individual line items have complied reads as having no open violation. The alternative — counting them open — would double-count complied line items inside open cases. Neither is wrong; this one was chosen because "COMPLIED means complied" is the reading a user would defend, and because the case-level signal is recoverable later from `case_status` now that it is ingested.

### Measured in-window, 2026-08-16, after `case_status` populated (99.8% coverage)

| | rows |
|---|---|
| open under the old predicate (`violationstatus = 'OPEN'`) | 70,591 |
| open under the shipped predicate (also requires case not closed) | **70,577** |
| **`COMPLIED` on a live case** (the judgement call) | **13,836** |

Two things this settles.

**The case-status guard barely bites on the OPEN class** — 14 rows in the whole corpus are `OPEN` on the violation and `CLOSED` on the case. Reading both fields remains right, because the guard costs nothing and the fields demonstrably disagree elsewhere, but it is not where the delta comes from. The delta is the status filter itself.

**The judgement call is worth 13,836 rows**, close to the 14,017 seen upstream. Those parcels have a live enforcement case whose line items complied, and under v11 they contribute no `li_violations` weight. That is the cost of reading "COMPLIED means complied", in numbers rather than in principle, and it is why the case-level signal is filed in `docs/feature-ledger.md` rather than discarded.

Distribution across 343,081 of 343,862 rows: CLOSED 232,558 · IN VIOLATION 72,685 · IN VIOLATION - COURT 13,087 · COMPLIED, BALANCE DUE 12,428 · SVN ISSUED, BALANCE DUE 11,634 · UNDER INVESTIGATION 423 · CANCELLED 266.

**Getting this number took three re-ingests and two fixes.** `case_status` had to survive four layers — loader, `_staging_row`, staging model, merge — and only the loader had it. Each ingest reported success. The column was read at the destination each time, which is the only reason the gap was visible at all.

---

## Distress: debt owed by someone else (Slice 3)

| | |
|---|---|
| delinquency snapshot vintage | `year_month` 202206, single value, 54,401 rows |
| delinquent parcels with a post-snapshot sale | **15,219** |
| …of them by sheriff's deed | **2,282** |

**Provenance:** production `tax_status` ⋈ `sale`, 2026-08-16.

**Effect by class:**

### Measured against the shipped rule, 2026-08-16

The earlier ≈2,282 figure was an **upper bound** and should not be used. It counted any sheriff's deed recorded after the snapshot. The shipped rule is narrower on two counts: the **first** transfer after the snapshot month must be the sheriff's deed (that is the conveyance which moved title away from the debtor; later ones are subsequent owners), and the grantor must name-match the debtor.

| class | parcels |
|---|---|
| delinquent with any post-snapshot transfer | 12,439 |
| first transfer is a sheriff's deed, grantor **exactly** matches debtor | **764** |
| …of those currently carrying deal-killer weight | **672** |
| nominal consideration — **guard retains the distress signal** | 3,143 |

764 is a lower bound: SQL can only test exact equality, while `match_parties` also accepts a two-shared-token partial. The true sheriff class sits between **764 and 2,282**.

### Fourth movement class: risk scores, not just copy

`info` severity carries weight **0.0**, so the sheriff-deed downgrade does not merely soften wording — it removes the flag's contribution to `risk_score`. **Up to 672 parcels lose deal-killer weighting**, which is a distinct movement from the three distress changes and belongs in the ADR's delta table as its own row.

`phl:201133900` is the concrete instance: risk 70/100 and distress 45/100 should both fall visibly at step 12.

---

## Distress: absentee owners we could not see (Slice 3b)

| | |
|---|---|
| OPA rows where we discard a mailing address | **522,832 of 583,681 (89.6%)** |
| vacant `phl` parcels that would gain one | **29,001 of 37,706 (77%)** |
| effect | `absentee` +10 on the subset whose mailing ≠ property address |

**Provenance:** live OPA via Carto (`mailing_address_1` 9.9% populated vs `mailing_street` 99.4%), production `parcel`, 2026-08-16.

`is_absentee` returns `False` whenever `mailing_address` is NULL, so today those parcels read as owner-occupied by absence of evidence.

### Backfill executed 2026-08-16

| | |
|---|---|
| coverage before | 57,753 / 588,591 (**9.8%**) |
| coverage after | 580,585 / 588,591 (**98.6%**) |
| **addresses recovered** | **+522,832** |

Scanned 583,681 upstream rows, 580,434 carried a usable address. The projection and the outcome agree to the row.

**For the direct-mail engine this is the headline number**: reachable owners went from roughly one in ten to roughly ninety-nine in a hundred.

The absentee *flip* count is still not the same as the coverage count and is measured at the v11 recompute, since `is_absentee` compares mailing to property address per parcel. The control parcel demonstrates why they differ: `phl:491313100`'s mailing address is its own property, so it gains coverage and no absentee signal.

---

## Valuation: comp-pool composition (Slice 3b)

The concern was that recovering ~18% more deeds pulls a disproportionate slug of distressed prices into comp sets. Measured, it does the opposite.

| | rows |
|---|---|
| RTT rows with a NULL parcel key | 957,458 |
| …passing the ingest filter (`%DEED%`, consideration > 0, ≥ 2005) | **136,758** |
| …excluded from comps by the v10 deed filter (ADR-0081) | 3,363 (**2.5%**) |
| …eligible to reach comp sets | 133,395 |

**Provenance:** live `rtt_summary` via Carto, 2026-08-16.

The remaining ~820k are mortgages, satisfactions, notary commissions and financing statements — never comp candidates, because `rtt_sales_where` already requires `%DEED%` and positive consideration.

**Composition, not just size:** non-market instruments are **2.5%** of the recovered pool against roughly **44%** of a typical pre-v10 comp set. Recovering these deeds should improve comp composition. The Fairhill deed that motivated D5 is itself a sheriff's deed and sits in the excluded 3,363 — recovered for the buyer census, correctly invisible to valuation.

**Exclusions apply by construction.** Recovered rows land in `sale` and are read by the same `_COMPS_SQL`, so related-party (ADR-0032), package-deed (ADR-0049), future-sale and the v10 deed-type filter all apply without further work. Verified by reading the query, not assumed.

### Where recovery concentrates (A1.1)

**Uniform in time.** Recovered share by recording year tracks the attributed share within 0.8x-1.2x across 2005-2026. No era clustering, so this is not a one-off feed break being undone.

**Concentrated in space.** Recovered share by ZIP, against the attributed baseline:

| zip | recovered | share | attributed share | lift | area |
|---|---|---|---|---|---|
| 19106 | 6,275 | 11.2% | 1.1% | **10.4x** | Old City / Society Hill |
| 19103 | 7,371 | 13.2% | 1.6% | **8.1x** | Rittenhouse |
| 19107 | 3,806 | 6.8% | 1.0% | **6.6x** | Washington Sq West |
| 19123 | 5,771 | 10.3% | 3.5% | 3.0x | Northern Liberties |
| 19130 | 5,872 | 10.5% | 6.1% | 1.7x | Fairmount |
| 19125 | 3,162 | 5.7% | 12.7% | 0.4x | Fishtown |
| 19111 | 2,815 | 5.0% | 12.5% | 0.4x | Northeast |
| 19121 | 2,734 | 4.9% | 13.6% | 0.4x | Strawberry Mansion |

Every high-lift ZIP is Center City and condo-dense, which fits the mechanism: a unit deed carries no single OPA account, so the recorder's row has no parcel key.

**PREDICTION RESOLVED — validated.** Predicted: the collision policy would absorb much of this Center City concentration, because condo units share a street address. Measured at backfill: **59,714 of 136,758 deeds (43.7%) went unattributed on collision**, and the resolved set fell from a possible 133,395 to 32,188. Directionally and proportionally right.

That is the second prediction this batch has resolved. The first went the other way: the concern that recovery would tilt comps toward distressed prices was **inverted** by measurement — non-market instruments are 2.5% of the recovered pool against roughly 44% of a typical pre-v10 set. Recording both directions is the point. A ledger that kept only the predictions that came true would be worth nothing.

**Two consequences the ADR should state.** First, recovery is concentrated in the highest-value, least-vacant parts of the city - the opposite of where the vacant-land product does its work, so the comp-pool effect on our core inventory is smaller than the raw count suggests. Second, condo density means many recovered deeds share one street address, so the collision policy should absorb a large share of exactly this concentration and leave them unattributed. **That is a prediction; verify it against the backfill's collision count rather than assuming it.**

Queries: recovered/attributed split on `rtt_summary` filtered to `document_type ILIKE '%DEED%' AND total_consideration > 0 AND recording_date >= '2005-01-01'`, grouped by `extract(year from recording_date)` and by `left(zip_code,5)` (ZIPs with >2,000 rows).

### Measured at backfill (2026-08-16, dry run against production)

The prediction was that condo density would send much of the Center City concentration into the collision branch. It did.

| outcome | deeds | share |
|---|---|---|
| resolved to a single parcel | **32,188** | 23.5% |
| **collision — left unattributed** | **59,714** | **43.7%** |
| no matching parcel in our data | 42,982 | 31.4% |
| no street address on the deed | 1,874 | 1.4% |
| scanned | 136,758 | |

**Live run 2026-08-16:** 32,188 resolved, **27,037 newly inserted** — the 5,151 difference is `ON CONFLICT DO NOTHING` catching deeds already present under the same `(parcel_number, document_id)`, which is the dedup working at scale rather than a shortfall. The Fairhill deed that motivated D5 landed: `phl:191357500`, sheriff's deed, 2025-05-08, $29,100.

Some recovered documents appear against two parcels. That is one deed conveying two parcels — a package deed — and `package_deed_exclusion_sql` filters them at query time, so they cannot reach comps.

**The realised comp-pool addition is 32,188, not 133,395** — a quarter of the eligible pool, because the collision policy refuses to guess between units sharing a street address. That is the policy working as designed rather than a shortfall: 59,714 deeds we cannot place are 59,714 we do not place.

It also settles the composition question at its final size. 32,188 additions against a `sale` table of ~788,000 is a ~4% enlargement, with a lower share of non-market instruments than the pool it joins.

**Carried forward:** the 42,982 no-match deeds are addresses we hold no parcel for. Worth a look later — some will be recorder formatting we do not normalise, some genuinely outside our parcel set — but not this batch.

---

## Step 11 — the sweep, measured (2026-08-18)

ADR-0083 accepted 2026-08-18. `VERDICT_VERSION` v10 → v11 deployed to production as `8fa8c87`; drift guard confirmed prod serving it, and the running API reports `VERDICT v11` / `PROFILE philly-distress-v2`. No migrations were pending, so `deploy.sh` correctly skipped the pre-migration backup. A per-parcel baseline was captured first into `pre_v11_distress` (588,591 rows) and `pre_v11_verdict` (551,168 rows) so every movement class could be measured rather than estimated.

### Distress sweep — complete

588,591 Philadelphia parcels in **~4 minutes**, all now `philly-distress-v2`.

| movement | parcels |
|---|---|
| unchanged | 509,875 |
| fell | **78,711** |
| rose | 5 |

| delta | parcels | reading |
|---|---|---|
| −5 | 62,655 | loses `li_violations` only |
| −15 | 4,983 | loses `tax_delinquent` |
| −20 | 927 | loses `tax_delinquent` + `li_violations` |
| −30 | 7,952 | loses `tax_delinquent` + `severe_delinquency` |
| −35 | 2,178 | loses both delinquency factors + `li_violations` |
| −10 | 16 | |
| +5 | 5 | |

**Against prediction.** Parcels losing `li_violations` total **65,760** (62,655 + 927 + 2,178) against a predicted 68,750 — 4.3% under. Parcels losing delinquency total **16,040** (2,178 + 7,952 + 927 + 4,983) against a predicted name-mismatch subset of 12,439 — 29% over. Both predictions were computed on 2026-08-16 and two nightly ingests have run since, so the populations moved underneath them. Recorded as measured, not reconciled.

**Tier migration — this is the part that changes who gets contacted.**

| before → after | parcels |
|---|---|
| low → none | 26,071 |
| medium → low | 8,299 |
| medium → none | 3,726 |
| high → medium | 723 |
| high → low | 31 |

No parcel rose a tier. **12,056 parcels leave the medium-or-high band entirely** and with it the lead surfaces, which is the mistargeting this batch existed to stop.

### The absentee class had already shipped — through data, not code

The ledger predicted **≤29,001 of 37,706 vacant parcels gaining absentee +10**. Measured population is **30,119**, slightly above that ceiling — and **every one of them already carried the points before this sweep ran**. Only 5 parcels rose at all, none by 10.

`is_absentee` is unconditional in `score_distress`, and this batch never touched it — what changed was the `mailing_address` data it reads. The backfill went into production on 2026-08-16 as a step-5 "data operation", and `cron(recompute_distress, hour=8, minute=0)` scored it that night. The class reached production roughly two days before the gate opened.

The reasoning is closed rather than inferred: if the points had not already been applied, all 30,119 would have gained +10 in this sweep, because the scoring code is identical before and after. Zero did.

**The gate held the code and the data walked in.** ADR-0083 reclassified the mailing fix as a scoring change and moved it behind the v11 gate — but what was gated was `ingestion/loaders`, while the score is a function of `parcel.mailing_address`, which a backfill wrote directly. A version gate on a derived-score pipeline only holds if the inputs are gated too, and a nightly recompute cron is enough to publish an ungated input on its own schedule.

Nothing here is wrong in the output — the absentee scoring is the correct scoring, and it is what v11 would have produced anyway. What failed is the claim that nothing scoring-related was live.

### Verdict sweep — running

Four shards on `abs(hashtext(parcel_number)) % 4`, re-verified disjoint and exhaustive against production: 146,480 / 147,819 / 146,961 / 147,331 = 588,591.

**The ~4h projection was wrong.** Measured throughput is **~14 parcels/s across all four shards**, giving **~11.5 hours**, a 1.3× speedup over the sequential estimate rather than 4×. `top` shows four postgres backends at 76–100% CPU with **0.0% idle and 0.0% iowait** — the box is fully saturated at four shards, so more shards cannot help. The earlier "DB 85% of one core, three idle" reading was taken of a sequential run and did not survive contact with four.

**Production is not degraded.** End-to-end latency of 0.76s decomposes as three round-trips at a 247ms RTT; server processing is ~16ms.

First 6,000 rows verified sane: `risk_score` and `recommendation` populated on all, mean risk 22.27 → 22.14, 39 risk drops, zero rises. Extrapolated that is ~3,825 risk drops against a predicted sheriff class of 764–2,282 — expected to exceed it, because `risk/service.py` also reads `open_violation_sql`, so violation-status corrections drop risk scores alongside the sheriff downgrades. To be confirmed at completion.

Verdict reads self-heal lazily on version mismatch, so users see current verdicts throughout.

### The fourth movement class was three, and two were never counted

The ledger predicted **672 parcels** losing deal-killer weight through the sheriff downgrade. Measured against a 25.06% sample (147,500 rows), risk drops project to **~15,547 citywide**. The prediction was not wrong so much as partial: `risk/scoring.py` has **three** paths that lower the tax-delinquency flag, and the ledger counted one.

| path | severity move | sample | citywide est. | predicted |
|---|---|---|---|---|
| name-matched sheriff's deed → `likely_discharged` | high → `info` (40 → 0) | 561 | ~2,239 | 764–2,282 ✓ |
| ordinary post-snapshot transfer → `verify` | high → medium (40 → 20) | 1,496 | ~5,970 | **not counted** |
| **name mismatch with no transfer at all → `verify`** | high → medium (40 → 20) | 1,546 | ~6,169 | **not counted** |
| sheriff variants (medium → `info`, and non-matching) | 20 → 0 | 258 | ~1,030 | partly |

The sheriff class itself lands inside its stated 764–2,282 band, so that figure held. What the delta table missed is that `verify` does not only reword the flag — `elif tax.attribution.posture == "verify": severity = "medium"` **halves the weight** of any delinquency that was `high`, and `verify` is reached by two populations, not one.

**A correction earlier in this file follows from that.** The classification of delinquent Philadelphia parcels is 41,962 with no post-snapshot transfer, 10,167 with an ordinary transfer, 2,272 with a sheriff transfer; of those, 26,409 / 5,859 / 1,964 would score `high`. The `verify` posture reaches the second and third groups **and** the name-mismatch subset of the first.

**One judgement worth an owner's eye, stated rather than buried.** D3's stated principle is that liens run with the land, so a parcel-level flag never silently disappears on an unconfirmed settlement. It does not disappear — but for roughly **6,169 parcels its weight is halved on a name mismatch alone**, with no deed of any kind to explain it, against a snapshot frozen in June 2022. A mismatch there can be a spelling variant, an estate, or a name format `match_parties` does not handle, and the lien on the parcel has not changed at all. That is a product decision rather than a defect, and it was not in the ADR's delta.

### Pinned parcels, measured mid-sweep

| parcel | risk | distress | tier |
|---|---|---|---|
| `phl:201133900` (audited) | **70 → 30** | **55 → 20** | medium → low |
| `phl:491313100` (control) | 100 → 100 | 55 → 55 | medium → medium |

Both pins hold. **Correction:** this file records the audited parcel's distress baseline as 45/100; the measured baseline was **55**. The fall is real; the stated starting figure was not.

### Two defects found while the sweep ran

**Scheduled jobs never got the timeouts they declare.** arq resolves a cron job's timeout from the `cron()` entry, not the `func()` registration, and all six long-running jobs carried theirs on the `func()` side only — so every one ran on its schedule under the thirty-minute worker default. `cron(recompute_verdicts, weekday="sun")` is among them: an ~11.5h job under a thirty-minute cap, cancelled every Sunday since it was scheduled. **This is a large part of why v9 and v10 were never swept.** Found because OPA failed at 04:30:01, thirty minutes and one second after its 04:00 cron, with this sweep saturating the box. Fixed in #155 with a guard comparing the two registries — a guard that was itself vacuous twice before it worked, because `cron()` prefixes `"cron:"` and the two name sets never intersected.

**Leads displayed the debt as well as ranking on it.** Filed as a cosmetic ordering artifact; both lead queries also *rendered* `"$X owed"` from raw `ts.total_due`, so a lead card could show a prior owner's debt as the owner's. `parcel_distress.debt_counts` now persists the attribution decision and both queries read through it (#155).

**The one red row on the ops board was an orphan.** `tax_restore` had a `dataset_freshness` row and no loader anywhere in the repo, so nothing could ever clear it — two months of permanent red on a board whose value depends on red meaning something. Row deleted. A registry-based filter was written and reverted: `dataset_freshness` stores upstream table names while the registry holds short keys, so it would have emptied the entire board and traded one silent failure for a worse one.

---

## Pinned fixtures

| role | parcel | why |
|---|---|---|
| regression | `phl:201133900` | 1943 N MARSHALL ST — changes on every axis |
| **control** | **`phl:491313100`** | 4941 N HUTCHINSON ST — changes on none |

**Control selected 2026-08-16**, after the delinquency re-ingest made `delinquency_owner` available. KENNEDY PATRICIA, $9,189.94 over 8 years, vacant RSA-5.

It qualifies on every axis the batch touches, and is unchanged on all of them:

- **Delinquency owner exact-matches the current OPA owner** (`match_parties` → `exact`), so the debt stays hers: flag unchanged, distress keeps +15/+15.
- **Two violations, both `OPEN`**, so D4's predicate keeps its +5.
- **Zero sales on record**, so there is no post-snapshot transfer to reason about.
- **`mailing_street` equals the property address** — an owner-occupant — so the mailing backfill gives it no absentee signal.

That last property was the reason for choosing it over the other candidates. A control that gains absentee +10 from a legitimate fix would still be *correct*, but it would stop being a control: "unchanged" has to mean unchanged, not unchanged-except-for-the-part-we-also-changed.

The regression parcel is its mirror: prior-owner debt via sheriff's deed, a COMPLIED/CLOSED violation, and `mailing_street` 8319 CHILDS RD against a property at 1943 N MARSHALL ST — absentee, correctly.

Both are pinned in `risk/tests/test_audited_parcels.py`. Ten assertions; the observed production facts are encoded as inputs so CI can verify the logic without reaching prod.

---

## Step 7 — the buyer census over the recovered deeds

**Measured against production 2026-08-18.** The census rebuild had already happened: the nightly buyer job (revived by PR #146) ran 2026-08-17 09:00 and produced 121 Philadelphia profiles, 115 of them carrying a mailing address. Both step-7 expectations were checked against that run rather than a fresh one.

| expectation | production read | state |
|---|---|---|
| the audited owner's mailing resolves | `8319 CHILDS RD WYNDMOOR PA 19038` | **met** |
| 6 purchases, including 2138 N Fairhill | `purchases_window` = 6, `phl:191357500` present | **met** |
| $143,700 total consideration | **$114,600** | **short by $29,100** |

SHLAYEN RACHEL has eight deeds in the 24-month window; two convey for $1.00 and fall below `BUYER_MIN_PRICE`, which is what makes the count 6 rather than 8. The recovered Fairhill deed is one of the six, so D5 is closed at the census.

### A third defect, found by the shortfall

The missing $29,100 is exactly the Fairhill deed. `derive_buyers` summed `total_consideration` over the **vacant-lot subset** while reporting `purchases_window` over all qualifying purchases — so the count said six and the money said five.

The field is presented unqualified. `BuyerProfilePage.vue` labels it "Total consideration" beside "Vacant lots (24mo)", "All purchases (24mo)" and "Median lot price" — every neighbour carries its scope, and this one does not. `BuyersPage.vue` sorts the roster by it under **"Largest spend"**. Both surfaces read it as the buyer's total outlay.

**Decision: `total_consideration` covers every qualifying in-window purchase; `median_price` stays lot-only, as its label says.** No existing test pinned the lot-only sum, so the narrower scope was never a decision — it was `prices` computed once for the median and reused for the total.

Fairhill fell out of the money because its `parcel.is_vacant` is NULL: it is not in the city's Vacant Property Indicators set, and `bool(None)` is False. **90 of the 121 Philadelphia profiles have `purchases_window > lot_purchases_window`**, so their totals rise at the next recompute.

**Not fixed here, and named:** 2138 N FAIRHILL ST reads `land_use = 'VACANT LAND - RESIDENTIAL'` with zero improvement value, and still `is_vacant` is NULL. Philadelphia's vacancy comes from the city model by design — `derive_vacancy` covers only `hbg` and `pgh` — so a land-use fallback for `phl` would move the vacant-lot universe itself, and with it tiles, verdicts and every count in this ledger. That is an ADR, not a step-7 edit.

### Pins

`buyers/tests/test_service.py::test_the_audited_buyers_census_counts_the_recovered_deed_and_its_money` drives all eight real deeds — document ids, prices, dates, grantors and the two NULL-vacancy parcels — through the real `recompute_buyer_profiles`, and asserts 6 purchases, 5 lots, $143,700, the resolved mailing address, and Fairhill's presence in the purchase list. `buyers/tests/test_derivation.py::test_total_consideration_covers_every_purchase_not_only_the_vacant_ones` pins the rule itself.

Both were verified to **fail** when the one-line fix is reverted.

---

## Lead-surface inclusion gates (verified before step 8)

Every surface reading `ts.total_due` is `FROM parcel_distress pd ... WHERE pd.score >= :min_score`. **Membership comes solely from the v2 distress score**; no surface gates on `is_delinquent` or `total_due` directly. A parcel whose debt belongs to a prior owner loses those points under v2 and never enters the list, so the mistargeting dies in scoring rather than surviving into ranking.

**One residual, stated rather than glossed.** `ORDER BY pd.score DESC, coalesce(ts.total_due, 0) DESC` uses unattributed `total_due` as a **tiebreak within an already-qualified set**. It can reorder two parcels that both cleared the gate on other factors; it cannot admit one. Inclusion is clean, ordering keeps a cosmetic artifact. Fixing it would mean carrying the lateral join into the leads queries for a tiebreak — real cost, no change to who is contacted. Left as a named follow-up rather than silently accepted.

## Predicate agreement (A1.2)

All five open-violation call sites now resolve through the single `open_violation_sql` definition: both tired-landlord subqueries (`distress/service.py:48,61`), both distress counters (`:82,108`), and the risk service (`risk/service.py:48`). No hand-rolled `= 'OPEN'` predicate survives anywhere.

The tired-landlord query had been correct all along, which is what made the bug survivable - a reader checking the file found a filter and moved on. Three near-identical predicates in two files is how the miss happened, and one definition is the structural fix.

---

## Carry-forward: the neutrality guard has a scheduled death

`ops/tests/test_slice0_neutrality.py` fails if any scoring module references `delinquency_owner`, `snapshot_period` or `case_status`. Slice 3's wiring and 3b's absentee pickup will reference all three **legitimately**, at the gate.

**RESOLVED 2026-08-16 — inverted, not deleted.** It fired during step 6, exactly when the wiring made the references legitimate. It is now `ops/tests/test_batch_wiring.py` and asserts the opposite: that risk and distress *do* read `delinquency_owner` and `snapshot_period`, that the open-violation rule reads `case_status`, that `TaxSignal` carries an attribution, that `DistressSignals` distinguishes open from on-record violations, and that Philadelphia scores under `philly-distress-v2`. It also keeps the original claim where it still holds — valuation and verdict composition are asserted to have stayed out of this batch.

The original wording, for the record: it must be inverted at Slice 5, not deleted when it starts failing — flipped to assert the references exist and that Philadelphia scores under `philly-distress-v2`. A guard that dies quietly at the moment it fires is worse than no guard, because its green history reads as evidence.

---

## Review-smell ledger

Three specimens of one species — **a check whose failure is indistinguishable from success**:

1. **The self-confirming test.** Three decision tests pinned `deal_infeasible=True` with a 25% margin, arithmetically impossible. They looked like coverage and asserted nothing reachable.
2. **The masked gate.** `make typecheck 2>&1 | tail -2 && git commit` takes `tail`'s exit code, so a mypy failure committed anyway. Structural fix: gates run bare, or under `set -o pipefail`. The real backstop is CI at PR time — which is why **branch protection remains the open CI-enforcement gap**.
3. **The guard that dies when it fires** — RESOLVED: inverted at step 6, not deleted.
4. **The known trap that re-arms.** `CAST(:param AS date)` under asyncpg binds before the cast and fails at runtime. Hit twice in one day, an hour apart, in different files — a personal pattern rather than carelessness, and personal patterns outlive good intentions exactly as behavioural gate-fixes do. Countered structurally: `core/tests/test_sql_bind_traps.py` greps the SQL-bearing corpus and fails with file and line. Verified by reintroducing the trap. Different species from the success-reporting-failure family; same ledger.

---

## Diligence: the flagship parcel's valuation move (2026-08-20)

The claim under test was the ledger's own — that *values move where recovery lands*. `phl:201133900` looked like a counterexample: North Philadelphia, no recovered-deed geography, and yet its market estimate moved $62,363 → $53,986 (−13%), flipping the assessment read from fairly assessed to over-assessed. It is a counterexample, and a stronger one than expected: **nothing in its comp pool moved at all.**

### What the two numbers actually are

Neither number is stored as "market estimate". The assessment surface computes it live on every read, from `sale`; the verdict stores a snapshot of the same computation taken during the sweep, as `assessment_market_gap`.

| | value | source |
|---|---|---|
| assessed market value | $66,800 | `parcel.market_value` |
| **stored** `assessment_market_gap` | **−$12,814** | `parcel_verdict`, computed 2026-08-18 03:56:40Z |
| implied stored market estimate | **$53,986** | 66,800 − 12,814 |
| **live** market estimate, prod, 2026-08-20 | **$62,363** | `analyze_parcel_assessment` |
| live gap | −$4,437 | fairly assessed |

The stored verdict's own provenance records the sweep-time comp set: **`comp_count: 22`**, `radius_ft 1500`, `years 3`, `use_class residential`, `comp_selection_policy phl-comp-selection-v1`, package deeds excluded, size-similar only. A live run today returns **23** comps under byte-identical parameters.

**Provenance:** `select sources from parcel_verdict where parcel_number='phl:201133900'`; live figures from `value_parcel` / `analyze_parcel_assessment` run inside the production `api` container.

### The delta reconstructed exactly

Leave-one-out over today's 23-comp set: dropping any one of four high-$/sqft comps reproduces the stored estimate **$53,986** and low **$25,975** to the dollar, and two of them also reproduce the stored high **$124,889** exactly —

| dropped comp | sale | $/sqft |
|---|---|---|
| `phl:202073400` 2146 N FRANKLIN ST | 2025-09-11, $150,000, 991 sqft | $151.36 |
| `phl:202160300` 2123 N 9TH ST | 2025-08-25, $125,000, 847 sqft | $147.58 |

So the sweep valued this parcel on today's set minus exactly one high comp. The whole −13% is one comparable.

### Classification: none of the four candidate causes

| candidate cause | verdict | evidence |
|---|---|---|
| recovered rows entering the set | **excluded** | zero `sale` rows within 1,500 ft created after the sweep read |
| prior members displaced by ranking | **excluded** | no distance tie straddles the `LIMIT 25` boundary (rn 25 = 1071.72 ft, rn 26 = 1076.43 ft) |
| a filter behaving differently | **excluded** | valuation, assessment and parcel code are byte-identical between the sweep SHA `8fa8c87` and prod `07e72f9`; package-deed sibling groups for all four candidates were last written 2026-08-16, before the sweep |
| an unrelated data refresh | **excluded** | on the 2026-08-18 database copy, **zero** `sale` rows and **zero** `parcel` rows inside the 1,500 ft pool carry an `updated_at` after the sweep read. The rolling three-year cutoff is not it either: cutoffs 2023-08-18 and 2023-08-20 both return $62,363 |

**Addendum, 2026-08-20 (second pass) — the in-flight-ingest hypothesis is now positively excluded, not merely absent.** The 2026-08-18 database copy shows `sale` was written twice that day, at 04:01 (11,768 rows) and 04:14 (17,344 rows) — both *after* the flagship's 03:56:40Z compute, and the only writes to `sale` between the 08-16 ingest and the copy. They are not Philadelphia rows:

| burst | market | rows |
|---|---|---|
| 2026-08-18 04:01Z | `hbg` | 11,768 |
| 2026-08-18 04:14Z | `pgh` | 17,344 |
| | **`phl`** | **0** |

The nearest touched parcel carrying geometry sits **484,530 ft (~92 miles)** from the subject. Nothing that committed to `sale` on the day of the sweep could reach a 1,500 ft comp pool.

**Provenance:** `select p.market_code, count(*) from sale s join parcel p using (parcel_number) where s.updated_at >= '2026-08-18' group by 1`, and the `ST_Distance` minimum over the same set, against the 2026-08-18 production copy — the only instrument that can answer this, because the nightly RTT merge bumps `updated_at` on every row it touches and production therefore reads 08-20 for the entire pool.

**Why $62,363 is the settled number.** It is what the code returns from the data, today and on the 08-18 copy alike, under the parameters the stored verdict itself records. $53,986 is not a competing reading of the comp set; it is a value with no reproducible input state behind it. The settled number is settled because it is the only one that can be re-derived.

**Finding, not explanation.** Same code, same recorded inputs, two different answers. The stored valuation is not reproducible from the inputs its own provenance names, and the remaining explanation lies inside the sweep run itself — four shards at 0.0% idle — not in the data. Per the diligence brief this is reported and stopped at; no valuation logic was changed.

### The consequence that reaches a user

Two live surfaces now disagree on this parcel by $8,377:

- `VerdictPanel` and `WhyScoreDrawer` render the **stored** `assessment_market_gap` — −$12,814, over-assessed.
- `AssessmentPanel` calls `/assessment` and renders the **live** computation — −$4,437, fairly assessed.

The paid appeal-packet CTA hangs off the live path (`estimated_annual_tax_savings`, currently null), so **the CTA is not showing on this parcel today**. It was reachable at sweep values. A stored snapshot of a live-computed number, rendered beside the live number, is the defect class — not the arithmetic.

**Latent, noted not fixed:** `_COMPS_SQL` orders by `distance_ft` alone and cuts at `LIMIT 25`. Two sales of the same parcel carry identical distances, so ties are routine; the cut is only stable while no tie straddles row 25. A deterministic tiebreak would make the comp set reproducible by construction. Not the cause here — it was checked and excluded.

---

## Residual: the owner-portfolio count is short by one (2026-08-20)

Class: **`owner_2` matching**, not nightly-refresh lag. Explicitly out of scope per the batch ADR's non-goals; recorded, not fixed.

| | parcels | value |
|---|---|---|
| LotScope owner portfolio (`owner_key = 'SHLAYEN RACHEL'`) | 12 | $1,454,500 |
| OPA live, `owner_1 = 'SHLAYEN RACHEL'` **or** `owner_2 = 'SHLAYEN RACHEL'` | 13 | $1,598,200 |
| the missing parcel: `651279700` 7216 HEGERMAN ST, `owner_1 = SHLAYEN LEONID`, `owner_2 = SHLAYEN RACHEL` | 1 | $143,700 |

$1,454,500 + $143,700 = $1,598,200 — exact, so the twelve we hold match OPA's twelve `owner_1` rows to the dollar and **refresh lag is arithmetically excluded**. `owners/service.py` matches on `owner_key`, a generated column derived from `owner_1` alone; `owner_2` is never consulted, so any parcel where the subject is the second-named owner is invisible to the portfolio panel.

The fourteenth holding is a different class again — a 2025 deed OPA has not processed, so OPA itself still names the 1947 owner. Neither residual is a defect in the batch.

**Provenance:** production `parcel`, 2026-08-20; Carto `opa_properties_public` live, same day.
