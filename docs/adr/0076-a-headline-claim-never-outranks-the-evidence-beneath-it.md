# ADR-0076 — A headline claim never outranks the evidence beneath it

Status: accepted (2026-08-04)

Generalises the single-surface fixes in **ADR-0072** (screening must not outrun its evidence) and **ADR-0074** into a rule that binds every surface, and names the structural cause that let one defect appear four times.

## Context

Three instances of the same defect surfaced within one day, recorded in handoff 0037 §5:

- "Buildable by-right" displayed above a checklist row failing on an unsafe-L&I record.
- A master-plan district reporting "1 by-right unit".
- A non-conforming lot reporting "By-right units: 2".

Two were caught by tests while writing the program statement (#114); the first was caught by the owner looking at a screen. Nothing had swept for the class. A sweep found a fourth, and measured all of them against the local database:

| surface | contradiction | scale |
|---|---|---|
| `VerdictPanel.vue` | "Variance likely" chip; three lines below, "By-right units: 2" whose tooltip said the figure is what the standards allow *without a variance* | 62,066 v8 parcels, **27.2%** |
| `reports/dossier.py` | the same bare "By-right units: N" under a "variance likely" summary band, in the artefact users forward to lenders | same population |
| `checklist/logic.py` | "Zoning conformance could not be determined for this parcel" on every special-purpose lot, while the hero above said "Master plan" and the screening reason said a master plan is required | **1,372 parcels — every master-plan parcel** |
| `VerdictHero.vue`, `VerdictPanel.vue` | master-plan status recovered by string-matching `"master plan"` in the verdict summary | structural |

The common cause is not carelessness in any one component. **The rule that decides a parcel's buildability posture existed in exactly one place — `zoning/program.py`, written for #114 — and four older surfaces each re-derived it independently.** `program.py` got every case right; the surfaces that predated it got them wrong, and no mechanism made the disagreement visible.

The re-derivation was forced. `requires_master_plan` is computed in `buildability.py`, consumed inside `compose_verdict`, and then **discarded**: it is not on `ComposedVerdict`, not on `parcel_verdict`, and not on `VerdictResult`. Two components had no way to recover it except by reading prose. A wording change in `_summary()` would have silently reverted 1,372 parcels to advertising base-district units they cannot use, with every test still green.

The checklist defect also repeats the lesson from #112: the pre-existing test asserted `status == "not_evaluated"` and never read the text, so a false sentence shipped under a passing test.

## Decision

**One rule, one source, consumed everywhere.**

`zoning/posture.py` owns `resolve_posture()`, returning `by_right`, `variance_required`, `master_plan_required`, or `undetermined`, plus `unit_claim()`, which returns the label, value and `FieldState` for a unit count under that posture. `program.py`, `checklist/logic.py`, `reports/dossier.py` and both Vue components consume it. Precedence is fixed: a master-plan requirement outranks every other signal, including a `can_build_by_right` that disagrees.

A unit count is never rendered bare. Its label states the condition attached to it — "By-right units", "Units if a variance is granted", "Units the standards would support" — and a master-plan lot renders `None`, never a number, because no count is available by right in a district whose density is set through the approval.

The posture is resolved **once per checklist response**, from the freshly assessed buildability rather than the stored verdict, and returned on the payload. A stale verdict row disagreeing with a live program statement would reintroduce the same class of defect from the other side.

`byRightQualifier` names flagged checks (`fail`, `potential_issue`), not only unevaluated ones. A by-right headline above a failing check previously said only "Still to check", which is what produced the first instance.

**Every test on a claim-bearing surface asserts the user-visible string.** Status enums and PDF magic bytes do not constitute evidence that a surface tells the truth; the report tests decompress the PDF content streams with stdlib `zlib` and read the rendered text.

## Consequences

The master-plan checklist row is `potential_issue`, not `fail`. `fail` is reserved here for high-severity risk flags and drives "deal-killer(s) to clear"; a master plan is a known entitlement path, not a defect. The row's text carries the claim, and the screening decision already returns `high_entitlement_risk` for it.

**One string sniff survives, deliberately.** The checklist is fetched separately from the verdict and can be absent, so `resolvePosture` falls back to the summary before the checklist resolves. It now lives in one function rather than two components. The durable fix is to put the posture on the verdict contract — a migration, a recompute and a `VERDICT_VERSION` bump — and it should ride with the deferred work to persist buildability confidence (handoff 0037 §6, item 3) rather than being paid for twice.

No migration, no recompute, and no version bump were needed for this change: the posture is computed on read, as the program statement and buildability confidence already are.

**What this ADR does not do.** It fixes the buildability family. Two adjacent surfaces named in the sweep brief were not swept, because the local database could not exercise them: `recommendation` is NULL on 739,216 of 739,510 local verdict rows, so screening-recommendation-versus-risk-flags and program-statement-versus-deal-killers have no meaningful local population to measure. `decide()` reads `risk_score` and a flag count but never reads checklist failures, so a `strong_candidate` above a failing row remains reachable in principle — 1 of 11 local `strong_candidate` rows carries a high-severity flag. That is the next pass, and it needs a database whose decisions are populated.
