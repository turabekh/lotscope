# §8.4 missing-data audit

**Requirement:** `docs/PRD-amendment-03-launch-readiness.md` §8.4 · **Backlog:** LR-B-003 (P0)
**Audited:** 2026-07-28 · **Baseline:** `feeb79a`

§8.4 forbids translating missing evidence into: no risk, no violation, buildable, clear title, no flood, zero taxes, zero cost, zero time, or no restriction.

LR-0 marked this **Needs verification** rather than Complete, on the grounds that the handling *looked* strong but had never been checked field by field. This is that check.

---

## Method

Searched domain code for the coercion patterns that produce this failure — `or 0`, `or 0.0`, `or False`, and `.get(key, 0)` / `.get(key, False)` — then traced each hit from storage through scoring to what the user actually sees. Verdict-level behaviour was tested directly by composing a verdict from entirely absent inputs.

Ingestion row counts and SQL `COUNT` aggregates were excluded: those are genuinely zero when nothing matched, not unknown.

---

## Findings

### 1. Unknown tax balance recorded as "not delinquent" — **fixed**

`ingestion/loaders/tax.py:44`

```python
"is_delinquent": (record.total_due or 0) > 0
```

A parcel **listed in the delinquency feed** whose `total_due` is missing was stored as `is_delinquent = False`. Missing amount became *not delinquent* — a §8.4 "no violation" translation, and the same class as the Harrisburg false-clean defect ADR-0057 cites.

The column is already `Mapped[bool | None]`, so the schema supported "unknown" and only the loader was discarding it.

**Fixed:** `None if record.total_due is None else record.total_due > 0`.

### 2. Delinquent parcel with unreported amount displayed "$0 owed" — **fixed**

`risk/scoring.py:116`

```python
due = tax.total_due or 0.0
detail = f"${due:,.0f} owed"
```

A parcel known to be delinquent but with no reported amount rendered as **"$0 owed"** — a zero-taxes claim about a parcel we knew was in arrears, and worse than silence because it reads as reassuring.

It also fed the severity threshold, so an unknown balance scored as low-severity.

**Fixed:** reports "Amount owed not reported"; severity no longer treats unknown as small.

### 3. Checklist reports "clear" when tax status is unknown — **fixed**

`checklist/logic.py:30`

The `liens_taxes` item renders `pass` with *"No tax delinquency, liens, or sheriff-sale exposure on record"* whenever no flag is present.

**Corrected after measuring the data.** The mechanism is narrower than first described here. `real_estate_tax_delinquencies` lists *only delinquent parcels*, so a parcel's **absence** from `tax_status` is genuine evidence of non-delinquency, not missing data — the original wording ("the feed never reported on the parcel") was wrong.

The real case is a parcel that **is** in the table with `is_delinquent IS NULL` — covered by the feed, but with no balance reported. Measured locally: **792 of 78,933 rows**. Those render as a clean pass today.

Finding 1 stops new rows from hiding in `false`, but the checklist still cannot distinguish *verified clear* from *unknown*, because `build_checklist` receives only the verdict and has no view of the underlying tax row.

**Fixed.** `build_checklist` now takes `tax_status_unknown`, resolved per parcel by the checklist service. When the feed covered the parcel but reported no balance, `liens_taxes` reports `not_evaluated` with *"The tax feed covers this parcel but reported no balance, so delinquency is unconfirmed. This is not a clean-title or paid-in-full confirmation."*

An actual delinquency still outranks the unknown state, and a genuinely clear parcel — absent from the feed — still reports `pass`. The unknown case now counts toward the checklist's `not_evaluated` tally rather than its `passed` one.

### 4. Unknown unit count conflated with zero in scenarios — **fixed**

`deal/scenarios.py:58` — `by_right = inputs.by_right_units or 0`.

The original entry described this as unknown units becoming `0`. Re-reading the control flow, the `or 0` is caught immediately by the `by_right <= 0` guard, so **no false figure ever escaped** — the severity was lower than recorded.

The real defect was the inverse: the two cases were **conflated**. A parcel whose zoning genuinely permits zero units by right was told *"No by-right unit count could be determined"* — reporting a determined answer as missing data. §8.4 forbids turning missing into zero; reporting zero as missing is the same failure pointed the other way, and it invites a user to go looking for an answer that already exists.

**Fixed.** `None` and `0` are now separate branches. Unknown keeps the undetermined message and `by_right_units=None`; a determined zero reports `by_right_units=0` with *"Zoning permits no units by right on this parcel."*

### 5. Unknown exemption treated as no abatement — **fixed**

`parcels/abatement.py:2` — `(exempt_building or 0.0) > 0.0`.

Absent exemption values read as "no abatement", and the checklist item is additive, so an unknown simply showed nothing.

**Fixed.** `has_active_exemption` returns `bool | None`: `True` when any reported value is positive, `False` only when **both** are reported and zero, and `None` when either is unreported. The checklist now renders a `not_evaluated` abatement item for the unknown case — *"an active abatement can be neither confirmed nor ruled out. This is not confirmation that none applies."* A parcel with no OPA detail at all is unknown rather than clear.

Note: `test_abatement.py` asserted `has_active_exemption(None, None) is False` — the bug was encoded as expected behaviour, which is why it survived review.

### 6. Unknown land value in the vacancy ratio — **fixed, and re-characterised**

`vacancy/scoring.py:27` — `land_value or 0.0`.

**This was mis-filed as a §8.4 violation.** §8.4 forbids missing data becoming *no risk, clear, or buildable*. Here the coercion runs the other way: an unknown land value makes `improvement >= 2 × 0` trivially true, so the parcel is treated as **having** a substantial structure, which *subtracts* 0.4 from vacancy confidence. Missing data produced more doubt, not false clearance. It could never manufacture a buildable or clear claim.

It was still wrong — the function asserted a definite structural finding from a comparison it could not perform.

**Fixed, with scores deliberately unchanged.** `has_substantial_structure` returns `bool | None`, with `None` when the ratio cannot be evaluated. `vacancy_confidence` applies the penalty unless a structure is positively ruled out, which reproduces the previous arithmetic exactly. The semantics are now honest and **no `recompute:vacancy` run is required**; a test pins the two paths to equal scores so a future change cannot silently make the unknown case optimistic.

---

## Verified correct

- **Verdict composition** — a verdict built from entirely absent inputs reports `unavailable` for every material field, `insufficient_data` as its recommendation, `None` for every money field, and never claims `can_build_by_right`. Tested in `src/lotscope/tests/test_missing_data_audit.py`.
- **`hbg.py:122` and `wlm.py:178`** — `(land or 0) + (building or 0) if (land or building) else None` returns `None` when both are absent and only treats a genuinely-absent component as zero. Correct.
- **Trust contract** — ADR-0065 forbids a `verified` state without an identified source and requires an `unavailable` field to state why, enforced by the type.
- **Checklist statuses** — ADR-0068 separates `not_evaluated` from `pass`, and a market with no feed shows the check rather than omitting it.
- **Underwriting** — financing and time carry `None` rather than an invented default, and `require()` raises rather than returning a number.

---

## Status

**LR-B-003 moves from `Partial` to `Complete`** (2026-07-28).

All six findings are fixed. No known false clearance reaches a user, and no coercion of a missing value into a definite one remains in the audited paths.

Two of the six changed character once traced properly rather than pattern-matched: finding 4 was a conflation rather than a leak, and finding 6 ran in the conservative direction and was never a §8.4 violation at all. Both are recorded as re-characterised above rather than quietly restated, because a missing-data audit that edits away its own wrong readings is worth less than one that keeps them visible.

Finding 6's fix is behaviour-preserving by construction, so no recompute is required. Findings 1–5 affect on-demand surfaces (checklist, scenarios) or newly-ingested rows, not stored verdicts — `VERDICT_VERSION` is unaffected and stays `v8`.
