# 15. Motivated-seller distress index

Date: 2026-06-28

## Status

Accepted

## Context

PRD personas (land flipper / wholesaler) and the owner-side revenue lines depend on identifying **distressed owners likely to sell** — the "distress supply" the PRD calls out (tax delinquency, sheriff sale, liens). Wholesalers pay for ranked lead lists. We have the signals (`tax_status`, `li_event`, `parcel`) but nothing scored or surfaced them.

## Decision

**A new `distress` engine** producing a 0–100 motivated-seller index, plus a tier-gated ranked **lead list**.

- **Signals & weights** (pure, tested `score_distress`): sheriff sale 30; tax delinquency 15, +15 if severe (≥$10k or ≥3 yrs); liens 10; L&I unsafe/dangerous 15 (else open violations 5); demolition 5; vacant 10; absentee owner 10. Capped at 100. **City/Land Bank-owned parcels score 0** (not a private seller). Tiers: high ≥60, medium ≥30, low >0.
- **Absentee owner** is a heuristic: the property address string is not contained in the mailing address. Modest weight, labeled as a heuristic.
- **Two surfaces, one scoring definition:**
  - Per-parcel `GET /parcels/{id}/distress` runs the pure Python scorer (full, explainable factor list).
  - `GET /leads` ranks parcels with a **SQL expression that mirrors the same weights** (imported as constants, interpolated into the query — our own integers, never user input). A PostGIS integration test asserts the SQL score equals the Python score for the same parcel, guarding against drift.
- **Lead list is tier-gated** (`accounts.tiers.lead_list_limit`: free 8, pro 200, enterprise 1000) and filterable (min score, vacant-only, ZIP). It only scores parcels that already carry a distress signal, which also bounds the scan.

## Consequences

- **PII & compliance (§13).** The lead list exposes owner names + distress — sensitive. It is auth-required and tier-gated, owner data is never logged, and we expose **no contact details or skip-trace** (a separate, deferred concern). Scoring uses only property/financial distress — **no protected characteristics** — so list-based targeting stays Fair-Housing-safe. The UI states the informational framing and the TCPA/CAN-SPAM/Fair-Housing obligations for any outreach.
- **Dual scoring** (Python + SQL) is duplicated logic; the shared weight constants and the equality test keep them in sync. If the weighting grows more complex, precomputing a `distress_score` column via a job (like the verdict) becomes the better path.
- **On-the-fly ranking.** The lead query aggregates `li_event` and scores the candidate set per request. Fine at single-city scale with the distress pre-filter; precompute is the scaling follow-up.
- **Absentee accuracy** is approximate (string containment, no address normalization); over/under-counts are possible and weighted modestly.
- Scores are not precomputed, so they are always fresh against current tax/L&I/vacancy data.
