# ADR-0083 — Whose debt, which violations, and the records we were dropping (verdict v11)

**Status:** DRAFT — pending Slice 5 figures and owner acceptance · **Date:** 2026-08-__ · **Bumps `VERDICT_VERSION` v10 → v11 and the Philadelphia distress profile `philly-distress-v1` → `philly-distress-v2`**

Recon: `docs/recon/data-integrity-batch-2026-08-16.md`. Measured delta with per-figure provenance: `docs/v11-delta-ledger.md`.

**Open at acceptance.** Four figures are pending and each names the step that produces it — see *Pending figures*. The ADR is not accepted until they are filled.

---

## Context

A field audit of `phl:201133900` against Philadelphia's primary sources found four defects. Everything geometric and documentary verified exact — zoning, overlays, RCOs, lot dimensions, assessment, deed record, comps to the dollar, flood zone. The defects were all in how we ingest, attribute or aggregate, and three of the four had a mechanism different from the one first supposed.

**A — the delinquency source is frozen and freshness could not see it.** `real_estate_tax_delinquencies` is one snapshot, `year_month` min = max = 202206, 54,401 rows. The nightly job re-downloaded a four-year-old file and reported success, because the freshness system measured fetch recency and nothing else.

**B — prior-owner debt attributed to the current owner.** On the audited parcel the debt is `MATUSOW JOSEPH`'s, the grantor on the 2025 sheriff's deed that made `SHLAYEN RACHEL` the owner. She was shown a deal-killer for it and scored 30 of her 45 motivated-seller points on a stranger's discharged debt.

> **Correction to the premise.** The recon brief held that we already had everything needed to detect this. We did not: `TAX_COLUMNS` requested neither `owner` nor `year_month`, and `tax_status` had no column for either. The rule had no data to run on, which is why Slice 0 exists.

**C — a complied, closed violation counted as open.** `distress/service.py` counted every violation regardless of status behind a factor labelled "Open L&I violations". The correct predicate existed thirty lines above in the same file, in the tired-landlord subquery, and had simply not been applied to the signal named after it.

**D — deeds and mailing addresses discarded at ingest.**

> **Two further corrections.** The deed drop is not at the census join; `to_sale_row` returns `None` when `opa_account_num` is NULL, so the row never enters `sale` and the census cannot recover what does not exist. And the mailing gap is not an aggregation problem: OPA leaves `mailing_address_1` NULL on 89.6% of parcels and publishes the address in `mailing_street`, which we never requested. There was nothing to aggregate.

---

## Decisions

### D1 — Keep the frozen source, label its vintage

No source swap. Checked: Carto's `real_estate_tax_balances` is parcel-level but ends at `tax_period` 2016 — older than what we hold. OpenDataPhilly's balances dataset publishes only ZIP, council-district and census-tract aggregations. **No fresher parcel-level machine-readable feed exists.** The June-2022 snapshot stays and is labelled everywhere it surfaces.

### D2 — One bump for the batch

v10 → v11 plus `philly-distress-v2`, one recompute. v9 and v10 both shipped before this batch, so there was nothing to ride. Timing: the v10 sweep runs to completion first and is not invalidated.

### D3 — Risk is about the parcel; distress is about the owner

The layers answer different questions and are split accordingly.

**Risk.** Liens run with the land in Pennsylvania, so a parcel-level flag never silently disappears on an unconfirmed settlement. Only a **sheriff's deed whose grantor name-matches the debtor** downgrades to informational, and the copy cites the prior owner, the deed date and the document id so a reader can check it. Every other post-snapshot transfer keeps the flag, gains the vintage, and is worded *verify* rather than *deal-killer* — an arm's-length sale normally clears delinquency at closing, but "normally" is not "verified".

**Distress.** The motivated-seller score models a person's financial stress, so a debt owed by someone else stops counting **regardless of deed type**. Two guards keep that from hiding real distress:

- **Partial name match** → treated as the current owner's, with the ambiguity labelled.
- **Nominal consideration ($0/$1)** → signal retained, because re-titling for a dollar moves a deed without moving a household.

**Name matching is one function with eight tests.** Exact after normalisation, or two shared tokens for partial, with suffixes and articles excluded so `JR` and `THE` cannot carry a match. No fuzzy identity graph.

### D4 — Open means OPEN

`case_status` is ingested alongside `violationstatus`. A violation is open when `violationstatus = 'OPEN'` **and** the case status is not closed; the two fields can disagree, so the rule reads both rather than trusting either.

**The 14,017-row judgement, recorded.** Rows reading `COMPLIED` / `IN VIOLATION` resolve as **not open**, because the predicate tests `violationstatus` first. Consequence stated plainly: an owner with a live enforcement case whose line items have complied reads as having no open violation. The alternative double-counts complied line items inside open cases. Neither is wrong; "COMPLIED means complied" is the reading a user would defend, and **the case-level signal remains recoverable** now that the column is ingested — filed in `docs/feature-ledger.md`, explicitly out of scope here.

The three `ISSUED` notice states are not open. The risk tab keeps showing violations as history, worded "on record".

### D5 — Recover keyless deeds at ingest, never guess

Address-normalisation fallback in `to_sale_row`. **Collisions resolve to unattributed** — two parcels on one address means the deed is dropped with a reason, not assigned to a guess. Every drop is counted by reason. Dedup is unchanged (`uq_sale_parcel_document` plus package-deed exclusion), so the known duplicate RTT rows still collapse.

### D6 — Fix the column; defer the modal rule

Ingest `mailing_street` with the city/state/zip companions, falling back to `mailing_address_1/2`. **The modal-selection and typo-merge rule is deferred** until coverage is re-measured — at 99.4% upstream coverage the problem it solves may not exist. Distinct owner keys (`SHLAYEN RACHEL` / `LEN` / `LEONID`) are **not** fuzzy-merged; they may be three people.

### D7 — Vintage-aware freshness, worse-of-the-two

`dataset_freshness.data_vintage` sits beside the fetch timestamps; each source declares its own derivation at load time; the displayed state is the worse of fetch-staleness and vintage-staleness, and the reason names which one lost. A source with no derivation keeps its fetch verdict and renders **"vintage unknown"** — deliberately not amber, because an always-amber board is ignored, which is how the ops alerting became furniture.

### Two reclassifications from Slice 0

Both were filed as behaviour-neutral ingestion work and both move scores. They were moved behind the v11 gate:

- **Mailing → distress.** `is_absentee` returns `False` whenever mailing is NULL, so 89.6% of parcels currently read as owner-occupied *by absence of evidence*.
- **RTT recovery → valuation.** `find_comps` reads `sale`, so recovered deeds become comp candidates.

Slice 0 kept only what nothing reads, and asserts it: a test greps every scoring module for the three new column names and fails if one appears.

---

## The delta

| effect | population | provenance |
|---|---|---|
| lose `li_violations` +5 | **68,750 parcels** | prod `li_event`, violations present but none open |
| gain `absentee` +10 | **≤29,001 of 37,706 vacant phl** | prod `parcel`; population gaining data, not confirmed flips |
| delinquency leaves distress | name-mismatch subset of **15,219** | prod `tax_status` ⋈ `sale`; **2,282** by sheriff's deed |
| comp pool | **133,395** eligible recovered deeds | live `rtt_summary` |

**Comp-pool composition improves.** Non-market instruments are **2.5%** of the recovered pool against roughly **44%** of a typical pre-v10 comp set; the v10 deed-type filter (ADR-0081) applies by construction, as do related-party (ADR-0032), package-deed (ADR-0049) and future-sale exclusions. The Fairhill deed that motivated D5 is itself a sheriff's deed — recovered for the census, correctly invisible to valuation.

**Recovery is uniform in time and concentrated in space.** Year-over-year lift is 0.8x-1.2x across 2005-2026. By ZIP it concentrates sharply in Center City: 19106 **10.4x**, 19103 **8.1x**, 19107 **6.6x**, all condo-dense, consistent with unit deeds carrying no single OPA account. Two consequences: the effect lands in the least-vacant parts of the city, away from where the vacant-land product works; and condo density means many recovered deeds share a street address, so the collision policy should absorb much of that concentration. **The second is a prediction to verify against the backfill's collision count, not an assumption.**

## Pending figures

| figure | produced by |
|---|---|
| in-window COMPLIED / IN VIOLATION count | Slice 0 deployed + delinquency re-ingest |
| re-measured mailing coverage | mailing backfill |
| control-fixture identity | `delinquency_owner` populated |
| final recovered-comp and collision counts | RTT recovery backfill |

## Consequences

**Lead lists reshuffle citywide.** That is the size of the defect, not the size of the fix.

**`philly-distress-v2` carries identical weights.** What changed is which signals reach them, which is what a profile version is for.

**The neutrality guard is inverted at Slice 5, not deleted.** It currently fails if any scoring module names the new columns; the wiring makes those references legitimate. It is flipped to assert the references exist and that Philadelphia scores under `philly-distress-v2`. A guard that dies quietly at the moment it fires is worse than no guard, because its green history reads as evidence.

## Non-goals

No source swap (D1). No fuzzy owner-identity graph beyond the single name-match rule. No modal mailing-address rule (deferred, D6). No outreach-targeting changes — it inherits correctness from distress. No OPA-lag ownership reconciliation. No `case_status` scoring (feature ledger).
