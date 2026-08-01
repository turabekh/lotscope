# ADR-0072 — Screening must not outrun its evidence

Status: accepted (2026-08-01)

Amends **ADR-0067** (screening recommendation contract). Does not supersede it: the recommendation vocabulary, the thresholds, and the ordering of checks are unchanged. Two rules are added.

## Context

A parcel in production surfaced both problems on one screen.

`phl:882917721` rendered **"Strong candidate — appears dimensionally eligible with a projected margin of 55% and no elevated risk signal"**, and directly beneath it: **three risk flags**, **risk 30/100**, **"No comps — not enough recorded comparable sales nearby yet"**, and a **LOW DATA COVERAGE** chip.

Both halves were produced by the rules as written, and both readings were wrong.

### The margin rested on a stand-in

`value_estimate_low`, `value_estimate_high` and `value_confidence` were all null — the AVM produced nothing for this parcel. The deal model therefore fell back to the OPA assessed value (`$527,800`) as the acquisition cost, and the 55% margin is arithmetic on that substitution.

`CRITICAL_FIELDS` in `decide()` covers only `can_build_by_right` and `by_right_units`, so valuation availability never reached the screening result. The product could say "Strong candidate" and "we could not value this land" in the same view without contradiction in code, only in meaning.

A margin is a claim about a deal. When the price side of that claim is an assessment standing in for a market value that could not be produced, the number is still worth showing — it is not worth calling *strong*.

### "No elevated risk signal" was read as "no risk"

`ELEVATED_RISK_SCORE` is 60 and this parcel scored 30, so the clause was true against the threshold. But it appeared immediately above three visible warnings — L&I violations, a zoning overlay, and an RCO. A reader does not hold a threshold in mind; they read "no elevated risk signal" as "nothing to worry about" and the flags below it as noise.

A sentence that is technically true and predictably misread is a defect. §8.4's concern is missing data presented as clear; this is the same failure in a different costume — a threshold presented as an all-clear.

## Decision

### 1. A strong margin built on an assessed land value is `worth_investigating`, not `strong_candidate`

When the margin clears `STRONG_MARGIN` and risk is not elevated, but no modelled land value exists, the result downgrades one step and says why:

> Projected margin of 55% rests on the assessed value — no comparable land sales were available to price the land, so the margin is not yet evidence of a strong deal.

The parcel is not hidden and the margin is not suppressed. Only the confidence claim is withdrawn.

**Downgrade rather than `insufficient_data`.** Routing these to `insufficient_data` was rejected: buildability *is* established, the deal *is* computable, and a user searching for opportunities is better served by "look closer" than by silence. `insufficient_data` remains reserved for the case where core buildability cannot be established at all.

### 2. The risk clause states the flags it is standing next to

Where flags exist, the reason names them rather than reporting only the threshold:

> Appears dimensionally eligible with a projected margin of 55%. Risk score 30/100 is below the elevated threshold, but 3 flags are recorded — review them before committing.

Where none exist, the wording becomes affirmative and specific: *"no risk flags recorded"* rather than *"no elevated risk signal"*.

## Consequences

**Fewer strong candidates, and they mean more.** Any parcel whose acquisition price came from the assessed fallback loses the label. That is the intended cost.

**`decision_version` stays `d1`.** The vocabulary and thresholds are unchanged; only reason text and one branch move. Verdicts do not need recomputing for correctness, though the stored `recommendation_reason` on existing rows will read in the old wording until the next recompute.

**No new inputs are plumbed.** `decide()` gains two arguments the composition layer already holds — whether a modelled land value exists, and how many risk flags there are. Nothing is re-derived downstream, so the reason cannot drift from the figures it describes.

**This does not fix the underlying data gap.** A parcel with no land comps still has no land comps. The change stops the product from sounding confident about it.
