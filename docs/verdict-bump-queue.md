# Verdict bump queue

Methodology changes that alter verdict outputs are **batched** into the next `VERDICT_VERSION` bump rather than shipped piecemeal (per the invariant). Data corrections (field mappings, new facts) recompute without a bump. This file collects queued items until the next batched bump.

Current `VERDICT_VERSION`: **v8**.

## Queued

### Condemned / Demolished → risk scoring
- **Source:** Harrisburg field-test batch (2026-07-06), repository list carries `hbg_city_status` (Demolished / Condemned) per the City Codes Administrator.
- **Now (no bump):** stored + displayed as an **unscored parcel fact** with provenance (Slice 3).
- **Queued (needs bump):** feeding `hbg_city_status` into `risk_score` as an additive flag. Additive risk/scoring changes have always taken an ADR + a version bump (ADR-0015 distress index, ADR-0027 access flag, ADR-0039 distress v2) — this follows that precedent.
- **Note:** status is known only for repository-listed parcels; it is not citywide code-enforcement coverage. Any scoring must carry that coverage caveat.

## Not queued (verified as non-defects during recon)
- **Bug-1 zoning split** — the buildability scorer correctly sets `needs_variance=None` on unknown conformance (`buildability.py:203`); composition correctly yields "buildability uncertain". No methodology change; the fix is reader-side only.
