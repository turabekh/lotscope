# ADR-0081 — Comparable sales are market sales (verdict v10)

**Status:** Accepted · **Date:** 2026-08-16 · **Supersedes nothing; bumps `VERDICT_VERSION` v9 → v10**

**Open at acceptance.** Accepted with these known and unclosed — none blocks the decision:

1. **Only Philadelphia is measured and registered.** `pgh`, `hbg` and `wlm` keep their current selection exactly. Pittsburgh's vocabulary plainly contains non-market instruments (`TREASURER DEED`, `QUIT CLAIM`, `FIDUCIARY DEED`, `EXECUTORS DEED`, `GUARDIAN'S DEED`) but none of them has been measured, and registering them on inspection alone would be the same unmeasured guess this ADR exists to remove.
2. **No time adjustment.** Comps span three years with no indexation. Philadelphia land moved over that window; the estimate treats a 2023 sale as equal to a 2026 one.
3. **The residual dispersion is real.** After this change the median coefficient of variation is 0.53, still above the `medium` threshold of 0.5. That is not believed to be further contamination — see *Consequences*.
4. **Production recompute is unrun**, deliberately, per the owner's instruction. Reads recompute lazily on version mismatch, as they did under v9.

## Context

Two thirds of Philadelphia vacant lots carried a land value the product itself scored `low` confidence, and the reported range was routinely an order of magnitude wide — a measured median high/low ratio of **7.0×**. A parcel would report "est. $6,902–$71,051", which is not a valuation.

The obvious hypotheses were wrong, and measuring them mattered:

- **Comps are not scarce.** 81.8% of vacant lots find five or more local comps; the wide-area fallback fires on only 7%.
- **The fallback is not being blocked.** Deduplicating repeat sales of the same parcel to the most recent *worsened* the outcome (15.8% vs 17.0% reaching `medium`), because it removes supporting comps without removing the dispersion.

The actual cause is that `find_comps` never filtered `sale.document_type`. Every recorded instrument counted as a comparable sale, and in the vacant-land pool the dominant non-market instrument is the **sheriff's deed** — a foreclosure auction, sold as-is for cash without open-market exposure, concentrated in exactly the distressed blocks where vacant lots are. Sheriff's deeds made up roughly **44% of a typical comp set** (average comps per subject fell 17.5 → 9.8 when excluded).

Land Bank dispositions, estate transfers and condemnations are nominal-price instruments too, but they are statistically irrelevant here: excluding them alone changed nothing measurable (850 rows citywide against 3,850 sheriff's deeds).

**The direction of the error is what makes this urgent.** Sheriff prices sit below market, so including them dragged land values down: median estimate **$28,966 → $45,291**, a **56% understatement**. For a screening product that is the worst possible error direction — it reports that deals do not pencil when they do, and a false negative is never investigated, so it never gets corrected by a user.

There is also an internal contradiction. LotScope surfaces sheriff sales as *buying opportunities* — the premise being that they clear below market. Valuing land *at* those prices asserts the opposite in the same product.

## Decision

### 1. Comp selection is a per-market registered policy

`valuation/policy.py` holds `CompSelectionPolicy` and a registry keyed on market code, mirroring the existing `WideAreaCompPolicy` in `fallback.py`. An unregistered market resolves to `None` and its selection is unchanged. Philadelphia registers `phl-comp-selection-v1`.

Registration is deliberate rather than defaulted: a market's `document_type` vocabulary is its own. Philadelphia records `SHERIFF'S DEED`, Pittsburgh records `TREASURER DEED` and `SPECIAL WARRANTY`, Wilmington records the single synthetic value `assessment_last_sale`. A shared exclusion list would be wrong everywhere at once.

### 2. Non-market instruments are excluded in SQL

The exclusion is a bound `text[]` parameter on the comps query, applied before `LIMIT`, so the limit returns 25 eligible market sales rather than 25 rows that are then thinned. `NULL` document types are kept — absence of a type is not evidence of a non-market transfer.

### 3. Size similarity is preferred, not enforced

Price per square foot varies with lot size, so comps are narrowed to lots between **0.6× and 1.6×** the subject's area — but only while at least **three** comps survive. Below that the full set is used.

The soft form is the decision, and it was measured against the hard form:

| | ≥ medium | median CV | median range | avg comps | median estimate | **no estimate** |
|---|---|---|---|---|---|---|
| baseline (v9) | 17.0% | 0.65 | 7.0× | 17.5 | $28,966 | 27 |
| deeds only | 26.1% | 0.56 | 4.8× | 9.8 | $41,666 | 30 |
| deeds + hard band | 28.3% | 0.52 | 3.8× | 6.5 | $42,882 | **59** |
| **deeds + soft band** | **33.8%** | 0.53 | 4.0× | 7.3 | **$45,291** | **30** |

The hard band buys a marginally tighter range by refusing to answer for **29 additional parcels** — it converts a wide answer into no answer. The soft band reaches a higher confidence rate at no cost in coverage. Preferring the most similar comps and widening when too few exist is also ordinary appraisal practice.

### 3a. As shipped, measured against the same 400 parcels

The table above is a simulation that filtered deeds in Python, *after* the query's `LIMIT 25`. The implementation filters in SQL, *before* it, so the limit returns 25 eligible market sales. That is the correct design and it does not measure identically:

| | v9 | simulation | **as shipped** |
|---|---|---|---|
| ≥ medium | 17.0% | 33.8% | **29.5%** |
| median range | 7.0× | 4.0× | **4.4×** |
| median estimate | $28,966 | $45,291 | **$46,604** |
| avg comps | 17.5 | 7.3 | **10.4** |
| **no estimate** | 27 | 30 | **6** |

Filtering before the limit reaches further out for eligible comps, which adds some dispersion — 29.5% rather than 33.8% reaching `medium`. It buys something better in exchange: **parcels with no estimate at all fall from 27 to 6**. Twenty-one parcels in four hundred that previously returned no land value now return one, because their comp slots were being consumed by sheriff's deeds that were then discarded. Coverage was not a stated goal of this change and is its largest single effect.

### 4. The wide-area fallback trigger is unchanged

Narrowing the comp set was expected to starve the local tier and require the fallback to fire below a comp-count floor rather than only at zero. Measurement says otherwise: parcels with no estimate stayed flat (27 → 30). The soft band already prevents starvation, so the trigger is left alone. This is recorded because the change was planned and then abandoned on evidence.

### 5. Provenance

`sources[]` records `comp_selection_policy`, `excluded_document_types` and `size_similar_only`. When the size band binds, a reason states it in the user's terms.

## Consequences

**Every Philadelphia land value moves, so this is a version bump.** Value estimates feed ARV, `est_profit`, and `opportunity_score`, which is precisely the batching rule in `docs/verdict-bump-queue.md`. v9 → v10, one coordinated recompute.

**The recompute is owed and unrun.** Reads recompute lazily on version mismatch, so a viewed parcel returns v10 immediately; stored rows stay v9 until the batch runs. Leads and saved-search filters read stored rows and are therefore mixed-version until then. This is the same posture v9 shipped in.

**Confidence rises but stays honest.** 29.5% reaching `medium` or better is roughly double v9's 17.0%, and it is not 90%. The residual dispersion is believed to be genuine market heterogeneity: Philadelphia land value changes block to block in transitional neighbourhoods, and a coefficient of variation above 0.5 within 1,500 ft is a true description of that. The thresholds in `avm.py` were deliberately *not* retuned to make the number look better — doing so would restate the same uncertainty as confidence.

**Estimates rise about 56% at the median.** Anyone comparing a v10 figure against a remembered v9 figure will see a large jump. The v9 number was low, not the v10 number high.

**Fewer comps are shown.** A user who previously saw 17 comps may now see 7. The set they see is the set the estimate came from, which was already true and is now more visibly so.
