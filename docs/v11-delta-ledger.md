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

- **Sheriff's deed, grantor matches debtor** (≈2,282): risk downgrades to informational with provenance; distress drops `tax_delinquent` +15 and `severe_delinquency` +15.
- **Ordinary post-snapshot sale, name mismatch** (≈12,937): risk keeps the flag with vintage and "verify" wording; distress drops the same 30.
- **Nominal consideration ($0/$1)**: distress **retained**, ambiguity labelled. Count pending — needs `delinquency_owner` populated.
- **Partial name match**: distress **retained**, ambiguity labelled. Count pending — same dependency.

The two "pending" counts are the guards, and they subtract from the two classes above. **Do not publish the 15,219 as the affected population without them.**

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

## Predicate agreement (A1.2)

All five open-violation call sites now resolve through the single `open_violation_sql` definition: both tired-landlord subqueries (`distress/service.py:48,61`), both distress counters (`:82,108`), and the risk service (`risk/service.py:48`). No hand-rolled `= 'OPEN'` predicate survives anywhere.

The tired-landlord query had been correct all along, which is what made the bug survivable - a reader checking the file found a filter and moved on. Three near-identical predicates in two files is how the miss happened, and one definition is the structural fix.

---

## Carry-forward: the neutrality guard has a scheduled death

`ops/tests/test_slice0_neutrality.py` fails if any scoring module references `delinquency_owner`, `snapshot_period` or `case_status`. Slice 3's wiring and 3b's absentee pickup will reference all three **legitimately**, at the gate.

**It must be inverted at Slice 5, not deleted when it starts failing** — flipped to assert the references exist and that Philadelphia scores under `philly-distress-v2`. A guard that dies quietly at the moment it fires is worse than no guard, because its green history reads as evidence.

---

## Review-smell ledger

Three specimens of one species — **a check whose failure is indistinguishable from success**:

1. **The self-confirming test.** Three decision tests pinned `deal_infeasible=True` with a 25% margin, arithmetically impossible. They looked like coverage and asserted nothing reachable.
2. **The masked gate.** `make typecheck 2>&1 | tail -2 && git commit` takes `tail`'s exit code, so a mypy failure committed anyway. Structural fix: gates run bare, or under `set -o pipefail`. The real backstop is CI at PR time — which is why **branch protection remains the open CI-enforcement gap**.
3. **The guard that dies when it fires** (above), if retired by deletion rather than inversion.
