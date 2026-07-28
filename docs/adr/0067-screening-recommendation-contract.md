# ADR-0067 — Screening recommendation contract

Status: proposed (2026-07-28)

Required by `docs/PRD-amendment-03-launch-readiness.md` §LR-V001–V005 and §10 (Slice LR-4). Backlog tickets LR-B-009 through LR-B-014. Depends on ADR-0065.

## Context

The dossier leads with `opportunity_score` — a single 0–100 blend of buildability and inverse risk — plus a `summary` string assembled from fragments. Neither answers the customer's actual first question, which JTBD-2 states as a useful pursue/investigate/pass result in about thirty seconds.

Two constraints bound the design tightly:

- **§10.3 forbids a new customer-facing composite score** until its inputs are defined, its distribution is tested, gold-set behaviour is reviewed, and at least five paid-beta users assess its usefulness. None of that has happened.
- **§LR-4 forbids bumping the verdict version solely for frontend composition**, but requires assessing a bump if persisted verdict logic changes.

ADR-0065 now supplies what makes this tractable: every material field declares `verified`, `calculated`, `estimated`, or `unavailable`. "Critical unknown" stops being a judgement call and becomes a query over field state.

## Decision

### 1. A categorical recommendation, not a score

The six §LR-V001 labels — `strong_candidate`, `worth_investigating`, `high_entitlement_risk`, `economics_unattractive`, `insufficient_data`, `likely_pass` — are a **categorical screening result**, not a number.

This is not the composite score §10.3 prohibits. It ranks nothing, blends nothing, and hides nothing: each label is reachable by an explicitly stated rule, and the rule that fired is shown as the one-sentence reason. `opportunity_score` remains for sorting and compatibility but stops being the headline.

### 2. Persisted, with its own version axis

The recommendation is computed in `verdict` composition and **persisted**, carrying a `DECISION_VERSION` independent of `VERDICT_VERSION`.

Two axes, following the precedent ADR-0057 set for distress (`DISTRESS_VERSION` versions the logic, `profile_id` versions the numbers):

- `VERDICT_VERSION` versions **what the verdict computes** — the fields and how they are derived.
- `DECISION_VERSION` versions **how those fields become a recommendation**.

Changing a decision threshold bumps `DECISION_VERSION` alone and does not invalidate stored verdicts. Changing a computed field bumps `VERDICT_VERSION` as it always has. A bump on one axis never implies the other.

Persisting rather than deriving at read time is a direct lesson from ADR-0065 Amendment 1: a derived-only contract was invisible on the cached path. Here the failure would be worse — a label could silently change under a user between views, and a correction (ADR-0066) disputing "Likely pass" could not name what it disputed.

**`VERDICT_VERSION` stays `v8`.** No existing computed field changes. The goldens must remain byte-unchanged for existing fields; if any moves, this ADR is wrong.

### 3. Critical unknowns force `insufficient_data`

A parcel whose district is unresolved, whose geometry is missing, or whose buildability is `unavailable` cannot present as a strong candidate regardless of how attractive the remaining figures look.

The rule reads ADR-0065 field states directly: if any field in the critical set is `unavailable`, the recommendation is `insufficient_data` and no other label can be reached. This is the §LR-4 definition of done — *a parcel with critical unknowns cannot show a confident positive result* — expressed as a precondition rather than a hope.

### 4. Deal killers are ranked, not re-scored

`risk_flags` already carry `severity: high | medium | low | info`. The top three are selected by severity then by a fixed decision-impact ordering of flag codes, both deterministic. Nothing is dropped: the remainder stays in the risk section.

Ordering is **derived, not stored** — it is a pure function of stored flags, so it needs no column and no version.

### 5. Four dimensions are presented, not merged

Buildability, economics, acquisition access, and risk appear as separate readings. Three already exist on the verdict (`buildability_score`, `deal_score`, `risk_score`). The fourth — acquisition access / seller motivation — is `distress`, which the dossier already loads from its own endpoint.

**Distress is not folded into the verdict contract.** Doing so would add a write-time dependency from `verdict` onto `distress` for a value the dossier already has, and §10.2 asks for the dimensions to be *visible*, not co-persisted. They are composed at presentation.

### 6. Required next checks extend the existing checklist

`checklist/` already produces a due-diligence list end to end. LR-V005 asks that it be driven by the gaps and flags actually present. It is extended, not rebuilt — and now has ADR-0065 states to drive it.

## Rejected alternatives

- **Derive the label at read time.** No migration, no version axis. Rejected for the ADR-0065 Amendment 1 reason: the label would change under users when the rule changed, and corrections could not reference it.
- **Fold the recommendation into `opportunity_score`.** Simplest, and precisely the §24 anti-pattern of hiding uncertainty behind a score.
- **Let the AI layer produce the recommendation.** §LR-4 forbids AI as the decision source. AI may explain a deterministic result when grounded; it may not be the result.

## Consequences

- One additive migration: the recommendation, its reason, and `decision_version` on `parcel_verdict`. No backfill; existing rows carry `NULL` until recomputed, as ADR-0057 and ADR-0065 both did.
- Existing verdicts show no recommendation until recomputed. Market-scopable, so Philadelphia can be refreshed alone.
- **Risk:** the thresholds separating `worth_investigating` from `likely_pass` are the least evidenced part of this design. They are a starting hypothesis to be corrected by the gold set (LR-3) and paid-beta feedback, and `DECISION_VERSION` exists precisely so correcting them is cheap.
- The label is a screening opinion, not advice. Product wording must keep it that way, and §6.3 governs.

## Open question for the owner

**The threshold values themselves.** The rule shapes are determined by the requirement; the specific cut-offs — what margin makes economics unattractive, what risk level makes entitlement risk the headline — are commercial judgement. I will propose defaults with the implementation and flag every one as a hypothesis rather than an established number.
