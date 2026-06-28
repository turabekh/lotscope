# 23. Deal signal in the Parcel Verdict

Date: 2026-06-28

## Status

Accepted (extends ADR-0007, follows ADR-0022)

## Context

ADR-0022 shipped the deal-analysis engine behind a standalone `GET /parcels/{id}/deal` and deliberately left the Parcel Verdict untouched. The Verdict is the product's flagship screen (PRD §6) and the single source of the verdict contract (ADR-0007); "what it's worth" there stopped at the land AVM. Folding the deal signal into the Verdict is what makes it flow into everything that reads the Verdict — the panel headline, lead lists, and the PDF dossier — without each of those calling the deal endpoint separately.

## Decision

**Add a compact deal signal to the verdict contract and bump the verdict version to `v2`.**

- **Six new fields** on `parcel_verdict` / `ComposedVerdict` / `VerdictResult`: `arv`, `est_profit`, `est_margin`, `max_allowable_offer`, `deal_score`, `is_underpriced`. The full pro-forma (cost breakdown, scenario overrides, reasons) stays on the `/deal` endpoint; the Verdict carries only the headline signal.
- **No recomputation of zoning or valuation.** `verdict.service` already computes buildability and valuation; it now passes those into `deal.service.build_deal(...)`, a new entry point that takes pre-computed buildability/valuation and only does the deal-specific I/O (buildable envelope for floors, improved-sale comps for ARV). `analyze_parcel_deal` (the endpoint path) was refactored to delegate to the same `build_deal`, so the endpoint and the Verdict produce identical numbers.
- **`compose_verdict` stays pure** and gains an optional `deal` argument (defaulted to `None`), so existing callers and the contract's composition boundary are unchanged. The opportunity score formula is intentionally left as-is (buildability + inverse-risk); the deal signal is surfaced alongside it, not blended in, to avoid silently redefining the established score.
- **Version bump to `v2`** marks the contract change for reproducibility/audit (ADR-0007). The summary line now appends `MAO $X` (with `(underpriced)` when flagged).

## Consequences

- **Backfill is on-demand.** The migration adds nullable columns; existing `v1` rows keep `NULL` deal fields until recomputed. New and refreshed verdicts are `v2` with the deal signal, and the `/deal`-backed deal panel shows full deal math regardless. A full citywide backfill is a heavy batch (`make recompute-verdicts` over ~550k parcels, several spatial queries each) and is left to run out-of-band rather than on this change.
- **Per-parcel verdict cost rises** by one envelope computation and one improved-comps query. Acceptable for the batch/on-demand model; if the citywide recompute becomes a bottleneck, the envelope's floor estimate could be derived from buildability instead of a separate spatial call.
- **Downstream reads get the deal signal for free** once a verdict is `v2`. Enriching the PDF dossier and lead lists to display it is a small follow-up.
