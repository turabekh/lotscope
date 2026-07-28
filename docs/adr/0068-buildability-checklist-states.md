# ADR-0068 — Buildability checklist states

Status: accepted (2026-07-28)

Required by `docs/PRD-amendment-03-launch-readiness.md` §LR-B001–B004 (Slice LR-5). Backlog tickets LR-B-015, LR-B-016, LR-B-017. Depends on ADR-0065.

## Context

`checklist/` already produces a due-diligence list end to end. Its status enum is `pass | warn | fail | info`, and availability is tracked on a separate axis (`available | no_data_source | pending_load`) fed by `markets/capabilities.py`.

§LR-B001 requires five states — `Pass`, `Fail`, `Potential issue`, `Not evaluated`, `Not applicable` — and §LR-5 requirement 4 is blunt: **never infer unavailable checks from silence.**

The current enum cannot express two of those. A check that was never evaluated and a check that passed are both representable only as some flavour of "not failing", and `info` is doing duty for several unrelated meanings.

## Decision

### 1. Five states, replacing the overloaded four

`ChecklistStatus = pass | fail | potential_issue | not_evaluated | not_applicable`

Mapping from the existing values:

| Was | Becomes | Why |
|---|---|---|
| `pass` | `pass` | unchanged |
| `fail` | `fail` | unchanged |
| `warn` | `potential_issue` | same meaning, the §LR-B001 name |
| `info` | `not_evaluated` **or** `not_applicable` | `info` conflated "we did not look" with "this does not apply here", which is exactly the distinction the requirement exists to draw |

This is a breaking change to a public enum. It is worth it: the whole point of the slice is that a user can see **which checks LotScope did not perform**, and that is unrepresentable in the old vocabulary.

### 2. Availability maps into state, it does not sit beside it

`ChecklistAvailability` currently duplicates part of the trust question. ADR-0065 already settled the general form of this, so the checklist follows it:

| Capability state | Checklist status |
|---|---|
| `no_data_source` | `not_evaluated`, with the market-specific reason as the detail |
| `pending_load` | `not_evaluated`, with the pending reason as the detail |
| `available` | the check's own derived status |

The availability field remains on the item for now so existing consumers keep working, but the status is authoritative and the two cannot disagree.

### 3. Silence is never a pass

A check with no supporting data returns `not_evaluated` and states why. It may never return `pass`. This is enforced in the construction path rather than left to each call site, because the failure mode — an unevaluated check rendering as a clean tick — is precisely what §8.4 prohibits and is invisible in review.

### 4. Checks are added where data exists, and named where it does not

§LR-B001 lists roughly seventeen checks. Where LotScope has the data, the check reports a real status. Where it does not, the check still **appears**, reporting `not_evaluated` with the reason. An omitted check is indistinguishable from a passed one, so omission is not an option.

### 5. Variance output is context, not prediction

Per §LR-B003 the ZBA output is labelled **Historical approval context**, discloses its sample size, and withholds a percentage when the matched evidence is too thin. A percentage derived from insufficient evidence is worse than no percentage, because it invites reliance it cannot bear.

## Consequences

- Frontend status maps gain two keys; the panel must render `not_evaluated` distinctly from `pass` rather than falling through to a neutral icon.
- The checklist becomes longer, and deliberately so: the unevaluated checks are the product's honest statement of its own limits.
- **`VERDICT_VERSION` unaffected** — the checklist is computed at read time from the stored verdict and is not persisted.
- **Risk:** a longer list of `not_evaluated` rows may read as weakness. It is the opposite — it is the difference between a screening tool and one that pretends to completeness. §6.3 governs the wording.
