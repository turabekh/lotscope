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
- **One scoring definition, precomputed.** The pure Python `score_distress` is the single source of truth. A batched job (`recompute_distress` / `distress.jobs`, mirroring the verdict precompute) scores every parcel and upserts into a `parcel_distress` table (indexed on `score DESC`), wired to a daily ARQ cron. Both surfaces use that scorer:
  - Per-parcel `GET /parcels/{id}/distress` runs it live (always fresh, full explainable factor list).
  - `GET /leads` reads the **precomputed `parcel_distress.score`** via an indexed join — fast top-N, no per-request scoring. A PostGIS test asserts the precomputed lead score equals the live per-parcel score.
- **Lead list is tier-gated** (`accounts.tiers.lead_list_limit`: free 8, pro 200, enterprise 1000) and filterable (min score, vacant-only, ZIP). It only scores parcels that already carry a distress signal, which also bounds the scan.

## Consequences

- **PII & compliance (§13).** The lead list exposes owner names + distress — sensitive. It is auth-required and tier-gated, owner data is never logged, and we expose **no contact details or skip-trace** (a separate, deferred concern). Scoring uses only property/financial distress — **no protected characteristics** — so list-based targeting stays Fair-Housing-safe. The UI states the informational framing and the TCPA/CAN-SPAM/Fair-Housing obligations for any outreach.
- **Precompute means the lead list is eventually consistent** with current data (refreshed by the daily cron / `make recompute-distress`), like the verdict. The per-parcel card is live, so a freshly-changed parcel can briefly differ from its lead-list row — acceptable, and the equality test guards the scorer itself.
- Precomputing replaced the earlier Python+SQL dual-scoring; there is now a single scorer, removing that drift risk entirely.
- **Absentee accuracy** is approximate (string containment, no address normalization); over/under-counts are possible and weighted modestly.
- Scores are not precomputed, so they are always fresh against current tax/L&I/vacancy data.
