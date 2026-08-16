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

The in-window count against our own filtered corpus is **not yet measurable** — `case_status` is populated only from Slice 0 onward. Measure after the Slice 0 backfill and append here before Slice 5.

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

`is_absentee` returns `False` whenever `mailing_address` is NULL, so today those parcels read as owner-occupied by absence of evidence. For vacant land the mailing address is almost never the property address, so most of the 29,001 will flip. **The realised count must be measured after backfill, not assumed at 29,001** — that figure is the population that gains data, not the population that flips.

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

**Still unmeasured:** how many recovered rows resolve to a parcel at all. Address-fallback collisions go unattributed by policy, so the realised comp-pool addition is a subset of 133,395. Measure after backfill.

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
