# 7. Verdict composition and contract

Date: 2026-06-27

## Status

Accepted

## Context

The Parcel Verdict is the product's soul (PRD §6): one row that answers what can be built, what it's worth, and what's wrong, with reasoning and sources. The `verdict` module composes the zoning, valuation, and risk engines into the `parcel_verdict` table and is the **single source of the verdict contract** (§10); changes here are ADR-level.

## Decision

**Composition is pure; persistence is at the edge.** `compose_verdict(buildability, valuation, risk, assessed_market_value, verdict_version)` is a deterministic function over the three engines' result schemas, returning a `ComposedVerdict`. `compute_verdict` (the service) runs the three engine services for a parcel, loads the OPA assessed market value, composes, and **upserts** `parcel_verdict`.

**Contract fields.**
- **Headline:** `opportunity_score` = `0.6 × buildability_score + 0.4 × (100 − risk_score)` (clamped 0–100), plus the raw `buildability_score`, plus a one-line plain-English `summary`.
- **Build:** `can_build_by_right`, `by_right_units`, `max_height_ft`, `needs_variance`, `buildable_area_sqft` (from zoning).
- **Value:** `value_estimate_low`/`high` range, `value_confidence` (high/medium/low mapped to 0.9/0.6/0.3), and `assessment_market_gap` = AVM estimate − OPA assessed value (positive ⇒ market above assessment).
- **Risk:** `risk_score` and the itemized `risk_flags` (jsonb).
- **Provenance:** per-dimension `sources`, `computed_at`, and `verdict_version` on every row (§0.6).

**Honest degradation.** A missing dimension yields null fields and a summary that says so; `opportunity_score` is always computable (absent inputs contribute 0 buildability / 0 risk). No false precision — confidence signals from each engine ride along.

**Versioning & reproducibility.** Every row stamps `verdict_version` (currently `v1`); a methodology change bumps it, enabling staleness detection and reproducible audits. Given the same inputs the composition is deterministic (apart from `computed_at`).

**Batch + on-demand.** `compute_verdict` computes one parcel; `recompute_verdicts` batches a set. Both are units of work over a caller-provided session — the transaction (and scheduling/retry) belong to the caller or an ARQ job, consistent with the ingestion pattern. Upsert-by-`parcel_number` makes recompute idempotent.

## Consequences

- One owner for the contract: API, reports, and the frontend read these fields; altering them is an ADR-level change that bumps `verdict_version`.
- `opportunity_score` is a heuristic blend, not a regulatory or appraisal determination — framed informational (§13).
- Verdict quality is bounded by engine data quality (provisional Title 14 standards, comp sparsity); the embedded confidence signals and per-dimension provenance surface that to users rather than hiding it.
- A scheduled batch-recompute job and an on-demand refresh endpoint are follow-ups that wrap `compute_verdict`/`recompute_verdicts` (build-order steps 7–8).
