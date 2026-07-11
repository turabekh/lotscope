# 60. BatchData skip-trace provider, no-hit refund, per-market gate

Date: 2026-07-12

## Status

Accepted

Extends ADR-0035 (skip-trace credits). Activates the dormant provider slot with a real client and finalizes
the reuse window, refund policy, and per-market gating for PRD-amendment-01 feature **A1**.

## Context

ADR-0035 shipped the credit ledger, the `skiptrace/` service (`trace_owner`, 90-day cache/reuse window), and
the provider **Protocol** with only a `NullSkipTraceProvider`. Three things were left open: which real
provider, whether a no-hit trace is charged, and how the pgh owner-suppression (Ordinance 3478-07) applies to
skip-trace. A session-26 evaluation compared BatchData, Enformion/EnformionGO, and REISkip.

## Decision

1. **Provider = BatchData.** Best fit for a bootstrapped single-city builder: developer-first REST API,
   self-serve keys, per-hit ≈ $0.02–0.08 (≤ the $0.15 target), non-FCRA real-estate-marketing permissible
   use, and DNC + TCPA-litigator scrub as first-class endpoints. Implemented as
   `BatchDataSkipTraceProvider` behind the existing Protocol; `get_skiptrace_provider(settings)` returns it
   when `SKIPTRACE_PROVIDER=batchdata` and `SKIPTRACE_API_KEY` is set, else the null provider or `None`
   (dormant-until-configured, unchanged). The response parser (`parse_batchdata_contacts`) is pure and
   tested; provider failures raise `UpstreamError` → **the credit is not spent** (no ledger burn happens
   before a successful `trace()`).

2. **Reuse window dropped 90 → 30 days.** BatchData's terms require refreshing cached contact data **at
   least every 30 days** and forbid public exposure/resale. `CACHE_TTL_DAYS = 30` (overridable via
   `SKIPTRACE_CACHE_TTL_DAYS`). This satisfies the clause and doubles as TCPA/DNC-suppression hygiene (stale
   contacts are re-verified). It also narrows the free-reuse benefit — an acceptable trade for compliance.

3. **No-hit refund.** A fresh trace that returns zero phones and zero emails burns one credit and then
   refunds it (`reason='refund'`, `ref='nohit:<burn_id>'`), netting zero — reported as `credits_spent=0`.
   The refund ref is keyed to the burn's row id, not the owner key, so each no-hit trace refunds exactly once
   and the partial-unique idempotency index never suppresses a legitimate refund. The ledger keeps both rows
   for auditability. Honest economics: users pay only for contacts actually returned.

4. **Explicit per-market gate.** `skip_trace` is added to pgh's `_HIDDEN_SURFACES`, and `trace_owner` now
   raises `ForbiddenError` when the parcel's market hides the surface — a real capability check rather than
   the previous incidental block (pgh parcels happened to carry no `owner_key`). Lifting pgh's owner gate
   (pending the 3478-07 legal read) is a separate, deliberate decision.

## Consequences

- The feature still builds, tests, and merges with **no live provider** — all tests run on a fake/null
  provider; the BatchData HTTP path is exercised only through the pure parser. Going live is env-only
  (`SKIPTRACE_PROVIDER`, `SKIPTRACE_API_KEY`), no deploy of new code.
- The 30-day window means a heavier re-skip cadence and cost than 90 days; monitor credit gross margin
  against the amendment's ≥60% target.
- The BatchData API request/response shape (`SKIPTRACE_API_URL`, the parser field mapping) is coded to the
  documented shape and **must be confirmed against the live dashboard** at integration — pricing and terms
  are not contractual until then (invariant #4: no paid commitment without written approval).
- pgh skip-trace is now off by explicit capability, so re-enabling it after the 3478-07 read is a one-line
  capability change, not a data quirk.
