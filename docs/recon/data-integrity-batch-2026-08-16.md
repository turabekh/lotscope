# Recon — data-integrity batch (delinquency vintage, prior-owner attribution, L&I status, buyer census)

**Date:** 2026-08-16 · **Status:** Phase 0 complete, awaiting D1–D7 approval · **No implementation written.**

Audited against production (`main @ a52977f`, verdicts `v10`/`d2`) and the live Carto API. The four defects are real. **Three of them differ materially from the brief's stated mechanism**, and one is roughly nine times larger than described.

---

## Corrections to the brief

### 1. Defect B's annotation does *not* have the data it needs

The brief states: *"We already hold all three facts needed to detect this: the delinquency record's `owner` name, the subsequent deed's `grantor`/`grantee` and `document_type`, and the dates. No new data source is required."*

We hold the deed side. We do **not** hold the delinquency side. `ingestion/loaders/tax.py:19`:

```python
TAX_COLUMNS = ("cartodb_id", "opa_number", "total_due", "principal_due", "num_years_owed")
```

Neither `owner` nor `year_month` is requested from Carto, and `TaxRecord` has no field for either. `tax_status` (`risk/models.py:21`) has no owner column. It *does* have `as_of_date`, which `to_tax_row` never populates — **959 rows citywide carry it**, none of them Philadelphia delinquency.

**Consequence:** the prior-owner rule needs an ingestion change (two columns + a migration) before any annotation logic can run. This moves work from Slice 3 into a prerequisite.

### 2. Defect D drops at RTT ingestion, not the census join

The brief presumes *"the deed→parcel join keys on `opa_account_num` and NULL rows drop silently."* The census join is `sale s JOIN parcel p ON p.parcel_number = s.parcel_number` (`buyers/service.py:50`) — it never sees `opa_account_num`.

The drop is one layer earlier, in `ingestion/loaders/rtt.py:42`:

```python
def to_sale_row(record: RttRecord) -> dict[str, Any] | None:
    parcel_number = to_parcel_key(record.opa_account_num)
    if parcel_number is None or not document_id:
        return None
```

A NULL `opa_account_num` means the deed **never enters the `sale` table at all**. The census cannot recover it because the row does not exist. Any fallback must live at ingest (or read raw RTT), and the fix must **backfill `sale`**, not just rebuild the census.

### 3. Defect D's mailing half is a wrong-column ingestion defect — and it is citywide

The brief frames this as an aggregation gap needing a modal-address rule. It is not. OPA publishes:

```
parcel 201133900  mailing_address_1: NULL
                  mailing_street:    8319 CHILDS RD
                  mailing_city_state: WYNDMOOR PA      mailing_zip: 19038
```

Our loader ingests **only `mailing_address_1`** (`loaders/opa.py:25`). Measured against live OPA:

| | rows |
|---|---|
| total OPA rows | 583,681 |
| `mailing_address_1` populated | 57,602 (9.9%) |
| `mailing_street` populated | 580,056 (99.4%) |
| **we discard a mailing address we could have** | **522,832 (89.6%)** |

All 12 `SHLAYEN RACHEL` parcels have a mailing address upstream and **zero** in our database. There is nothing to aggregate. D6 as scoped — modal selection, typo-variant handling — solves a problem that does not exist yet; it becomes relevant only *after* the column fix, and probably not even then.

This affects every outreach, skip-trace and owner-mail surface, not just buyer profiles.

### 4. The v9 sequencing premise is stale

The brief asks whether *"the RM-1 small-lot provision gap slated for verdict v9"* might flip this parcel. v9 shipped 2026-08-11 and v10 today. `phl:201133900` is already stored at `v10`/`d2`:

```
can_build_by_right f · by_right_units 1 · needs_variance t · high_entitlement_risk · risk 70
```

RM-1 requires 1,440 sqft / 16 ft; the parcel is 884 sqft / 14 ft — it fails **both**, so no small-lot provision on area alone would flip it. **There is no v9 dependency to sequence around.** D2 is a straight choice about this batch's own bump.

---

## Confirmed as described

### Defect A — the delinquency source is frozen, and freshness cannot see it

Verified directly: `real_estate_tax_delinquencies` is a single snapshot, `year_month` min = max = **202206**, 54,401 rows.

The freshness system measures fetch recency only. `dataset_freshness` holds `last_attempt_at` / `last_success_at` / `status` / `detail` — **no vintage column exists**. `ops/cadence.py` evaluates age-since-fetch against a per-source cadence and correctly reports "fresh" for a file re-downloaded today. The failure class is structurally invisible, exactly as stated.

### Defect C — root-caused, and larger than reported

`distress/service.py:79`:

```sql
count(*) FILTER (WHERE event_type = 'violation') AS violations   -- no status filter
```

`distress/scoring.py:96` labels that count **"Open L&I violations"**. The correct predicate already exists twelve lines earlier in the same file — the tired-landlord subquery at `:47` filters `upper(coalesce(status,'')) = 'OPEN'`. The filter was written, then not applied to this signal.

`violationstatus` **is** ingested and stored on `li_event.status`. `casestatus` is not requested. Observed values in production, complete set:

| status | rows |
|---|---|
| COMPLIED | 215,696 |
| OPEN | **70,591** |
| CLOSED | 38,692 |
| SVN ISSUED | 17,977 |
| WARNING ISSUED | 872 |
| CVN ISSUED | 34 |

**273,271 of 343,862 violations (79.5%) are counted as "Open" while not being open.** **68,750 parcels** have violations but none open, and every one of them carries a spurious +5.

### Defect B — the flag and the score

`risk/scoring.py:115` builds the flag; severity is `high` when `total_due >= _TAX_HIGH_DUE` **or** `years_owed >= _TAX_HIGH_YEARS`, so 44 years forces deal-killer regardless of amount. `distress/scoring.py:73` adds the delinquency weight.

Candidate population, production:

| | count |
|---|---|
| delinquent parcels with a sale after the 2022-06 snapshot | 15,219 |
| …of which by **sheriff's deed** (strongest signal) | **2,282** |

---

## D1 — Source strategy · **Recommend: label the vintage; do not swap**

I checked for a fresher parcel-level feed and there is not one.

- **`real_estate_tax_balances` on Carto exists** — 683,926 rows, parcel-level, carries `owner`, `lien_number`, `principal/interest/penalty/total`, per-year `tax_period`. **But `max(tax_period) = 2016`**, range 1972–2016, 102,829 parcels. It is *older* than the snapshot we already have.
- **OpenDataPhilly's "Real Estate Tax Balances"** publishes only **ZIP / council-district / census-tract aggregations**. Not parcel-level. Cannot back a per-parcel flag.
- ArcGIS Hub pages are JS-rendered and returned no metadata; the underlying layer is the same Carto table.

**Recommendation:** keep the June-2022 snapshot, label it with its vintage everywhere it surfaces, and stop implying currency. Revisit if Revenue publishes a parcel-level feed — the 2024-09 balances release suggests the department is moving, but not at parcel grain yet. **Non-goal confirmed:** no live Revenue scraping.

## D2 — Versioning · **Recommend: one bump, this batch's own**

v9 and v10 are both shipped; there is nothing to ride. The L&I predicate and the delinquency exclusion both move distress scores, and the delinquency severity change moves a risk flag that feeds `_DECISION_IMPACT` (`verdict/decision.py:30` ranks `tax_delinquent` among deal-killers) — so verdict output moves too.

Propose: **one ADR, `VERDICT_VERSION` v10 → v11, distress profile `philly-distress-v1` → `v2`** (ADR-0057 requires the new profile registered or precompute trips its coverage tripwire), one coordinated recompute. Note the current v10/d2 sweep is mid-flight (~15h remaining) — a v11 bump invalidates it exactly as d2 invalidated its predecessor. **Sequence the bump to land after the sweep completes, or accept restarting it.**

## D3 — Annotation semantics · **Recommend: downgrade to informational, only on the strong signal**

Downgrade severity to informational **only** when all hold: delinquency `owner` normalizes equal to the deed `grantor`, the deed post-dates 2022-06-30, and `document_type = 'SHERIFF''S DEED'`. That is the 2,282-parcel set. Copy as the brief drafts it, citing document id and dates.

For the other ~13k (ordinary deeds after the snapshot), **keep the flag, add the vintage note**. A normal sale does not discharge tax debt the way a sheriff sale does; downgrading there would hide live debt. Ambiguous name match → keep the flag and say the match was ambiguous.

Name rule: reuse the existing `normalized_name_sql` / `normalize_party_key` used by the buyer census — one function, exact match after normalization, **no fuzzy threshold**. Smallest change, and it is already tested.

## D4 — L&I semantics · **Recommend: open = `OPEN` only**

Distress counts only `status = 'OPEN'`. `COMPLIED` and `CLOSED` are plainly not open. `SVN ISSUED` / `CVN ISSUED` / `WARNING ISSUED` (18,883 rows, 5.5%) are notices whose disposition we cannot determine from the field we hold — **treat as not-open and surface as history**, since counting them as open reproduces the current overcount at smaller scale. Risk tab keeps showing violations as history with their status rendered, which is defensible and already accurate.

Recommend also ingesting `casestatus` in the same slice — it is one column and is what would let us classify the notice states properly later.

## D5 — Census join fallback · **Recommend: fix at ingest, backfill `sale`**

Fallback in the RTT loader when `opa_account_num` is NULL: normalize `street_address` and match against `parcel.address`. Collisions (>1 parcel) → **do not attach**; record the deed as unattributed rather than guessing. Requires a place to record it — recommend keeping such rows in `raw` and logging a count, so the drop is measured rather than silent.

Dedup keys are unaffected: dedup is `uq_sale_parcel_document (parcel_number, document_id)` plus `package_deed_exclusion_sql`. The Grove St duplicate collapses on document_id and will continue to.

## D6 — Mailing address · **Recommend: fix the column, drop the modal rule**

Ingest `mailing_street`, `mailing_city_state`, `mailing_zip`, falling back to `mailing_address_1/2`. That recovers 522,832 parcels. Re-measure before building anything else — with 99.4% coverage the modal-selection and typo-merge problems the brief anticipates may not exist. **Do not fuzzy-merge** `SHLAYEN RACHEL` / `LEN` / `LEONID`: they are three distinct owner keys and may be three people.

## D7 — Vintage-aware freshness · **Recommend: yes, and it is the most valuable item here**

Add `data_vintage` (date) to `dataset_freshness`, derived per source at load time: `max(year_month)` for delinquency, `max(recording_date)` for RTT, `max(violationdate)` for L&I, dataset metadata where published, NULL where genuinely unknowable. Extend `ops/cadence.evaluate_freshness` to judge vintage against the same cadence and return the **worse** of fetch-age and vintage-age. Docs tab shows both — *"fetched today · data as of Jun 2022 · stale"*. NULL vintage renders **"vintage unknown"**, never as fresh.

This generalizes today's other lesson: a check whose failure is indistinguishable from success. Fetch-recency reported success for four years.

---

## Suggested slice order (revised from the brief)

| # | slice | version impact |
|---|---|---|
| 0 | **Ingestion prerequisites** — tax `owner` + `year_month`, OPA mailing columns, L&I `casestatus`, RTT address fallback. Migration, additive. | none (data only) |
| 1 | Vintage-aware freshness (D7) | none — display/ops |
| 2 | L&I open filter (D4) | **scoring** |
| 3 | Prior-owner annotation + distress exclusion (D3) | **scoring** |
| 4 | Census backfill + mailing surfacing (D5, D6) | none |
| 5 | ADR + v11/distress-v2 bump + recompute | **release** |

Slice 0 is new and is a hard prerequisite for slices 3 and 4 — the brief's plan assumed data we do not ingest.

## Regression fixtures

`phl:201133900` pinned as named golden: after the batch, no current-owner deal-killer from the Matusow debt, no +30 distress from it, no +5 from `VI-2025-044445` (COMPLIED/CLOSED), buyer census 6 purchases / $143,700, mailing `8319 CHILDS RD`. Control parcel still required — a delinquency whose `owner` matches the *current* OPA owner, flag unchanged. **Selecting the control needs the tax `owner` column, so it cannot be chosen until Slice 0 lands.**

## Open questions for the owner

1. **D2 timing** — bump after the running v10/d2 sweep finishes (~15h), or restart it?
2. **D3 breadth** — is downgrading only the 2,282 sheriff-deed cases acceptable, leaving ~13k ordinary-sale cases flagged with a vintage note?
3. **D6** — accept that the modal-address work is deferred until after the column fix is measured?
