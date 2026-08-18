# Feature ledger

Signals and capabilities that are *available* but deliberately unbuilt. An entry here is a recorded decision not to build, with the evidence that would change it — not a backlog item awaiting capacity.

**Promotion rule:** an entry is built when **three named ICP requests** ask for it. Named, not inferred from usage. Until then the data may be ingested and displayed, but nothing scores on it.

> The promotion rule is recorded here as stated by the owner; it is not written into `CLAUDE.md` or `docs/PRD.md`. If it is meant to govern beyond this ledger it should live in one of those.

---

## Case-level L&I pressure as a distress input

**Filed:** 2026-08-16 · **Status:** available, unbuilt · **Requests:** 0 of 3

`case_status` is ingested as of Slice 0 and nothing reads it.

**The signal.** 14,017 upstream rows read `COMPLIED` on `violationstatus` while `casestatus` is `IN VIOLATION` — the individual line item was fixed but the enforcement case stayed live. A further 16,325 read `IN VIOLATION - COURT`, and 451 `UNDER INVESTIGATION`.

**Why it is plausibly distress.** A live enforcement case is financial pressure on an owner even when the specific violation has been remedied — court dates, counsel, the risk of escalation. The current distress model sees none of it, because v11's `is_open_violation` requires `violationstatus = 'OPEN'` and those rows fail at the first test.

**Why it is not built now.** v11 already moves distress substantially (68,750 parcels lose +5, ~29,001 gain +10, prior-owner debt leaves the score). Adding a third movement in the same version would make the delta impossible to attribute, and the case-level reading is a judgement about what constitutes owner stress rather than a defect being corrected. This batch fixes what is wrong; it does not extend what is measured.

**What would change the decision.** Three named ICP requests, or evidence that owners with live cases and complied line items convert at a materially different rate than the general distress population.

**What it would cost.** Small — the column is already ingested, the predicate is one shared function, and it would ride a future distress profile version. The expensive part is the recompute, not the code.

**Recorded against:** `docs/v11-delta-ledger.md` (Slice 2, the 14,017-row judgement call).
