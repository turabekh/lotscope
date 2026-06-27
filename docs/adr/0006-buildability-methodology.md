# 6. Buildability / by-right methodology

Date: 2026-06-27

## Status

Accepted

## Context

The zoning engine produces the developability read that feeds the Parcel Verdict — by-right use, conformance, variance likelihood, buildable envelope. These answers drive money decisions, and Title 14 is intricate and amendable. The methodology and its conservative assumptions are recorded here; the engine is deterministic (no LLM — the grounded AI Q&A is a separate layer, build-order step 9).

## Decision

**District resolution.** Resolve a parcel's base district spatially first — its centroid within a `zoning_district` polygon (`ST_Contains` over `geom_2272`) — and fall back to the OPA `base_zoning_code` attribute. The resolution **method is recorded** (`spatial` vs `opa_attribute`) and carried as provenance.

**Standards are data, not code.** Dimensional standards come from the versioned `zoning_standard` table (latest `code_version`), never hardcoded. Populating Title 14 into that table is a **separate task**; until then the engine returns an explicit low-confidence "no standards loaded" result.

**Pure, deterministic assessment.** `assess_buildability(dims, standard)` is a pure function over value objects:
- **Conformance** compares lot area/width to district minimums. A known dimension below a minimum is a definitive non-conformance; missing dimensions yield `None` (unknown), and a definitive failure overrides an unknown.
- **needs_variance** is the negation of conformance (or `None` when unknown).
- **by_right_units** is passed through from the standard (`max_units`); the engine does not invent unit counts.
- **buildable_area** is an estimate — net footprint from setbacks when frontage/depth are known, else lot area × max lot coverage — and is labelled as an estimate in the reasons.
- **score** is an explicit heuristic 0–100 (conformance, permitted uses, buildable area, by-right units), and **confidence** (high/medium/low) is driven by data completeness.

**Honest and auditable.** Every result carries a reason list, a cited section (`CODE (Title 14, version)`), a confidence signal, and provenance (`sources` + `computed_at`). Unknowns are surfaced as unknown, never as false precision.

## Consequences

- Assessments are reproducible and auditable, supporting reproducible verdicts (§0.6) and the "informational, cited, confidence-scored" requirement (§9, §13) — without an LLM in this path.
- The score is a heuristic developability proxy, not a regulatory determination; it must be framed as informational, not advice.
- Real Title 14 nuance — undersized-lot provisions, overlays/NCO/historic, use-specific and density rules — is not yet encoded. As it is added, refine the rules and supersede this ADR; the value-object boundary keeps the pure logic unit-testable as it grows.
- The engine is only as good as the `zoning_standard` data; a Title 14 population task is a prerequisite for production-quality answers.
