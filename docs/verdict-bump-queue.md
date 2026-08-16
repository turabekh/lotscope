# Verdict bump queue

Methodology changes that alter verdict outputs are **batched** into the next `VERDICT_VERSION` bump rather than shipped piecemeal (per the invariant). Data corrections (field mappings, new facts) recompute without a bump. This file collects queued items until the next batched bump.

Current `VERDICT_VERSION`: **v10**.

**Shipped since this file was last accurate.** It read `v8` while `v9` was already live, and described a "v9 batch" that is not what v9 became — recorded here so the drift is not repeated:

- **v9** — overlay-aware effective zoning standards (ADR-0080). Not the batch proposed below.
- **v10** — market-only comparable sales: sheriff's and nominal-transfer deeds excluded, soft lot-size similarity band (ADR-0081). Philadelphia only; other markets' selection unchanged.

**The v10 recompute is owed and unrun** by owner instruction. Reads recompute lazily on version mismatch; stored rows stay v9 until the batch runs, so leads and saved-search filters are mixed-version in the meantime.

## Queued

### Condemned / Demolished → risk scoring
- **Source:** Harrisburg field-test batch (2026-07-06), repository list carries `hbg_city_status` (Demolished / Condemned) per the City Codes Administrator.
- **Now (no bump):** stored + displayed as an **unscored parcel fact** with provenance (Slice 3).
- **Queued (needs bump):** feeding `hbg_city_status` into `risk_score` as an additive flag. Additive risk/scoring changes have always taken an ADR + a version bump (ADR-0015 distress index, ADR-0027 access flag, ADR-0039 distress v2) — this follows that precedent.
- **Note:** status is known only for repository-listed parcels; it is not citywide code-enforcement coverage. Any scoring must carry that coverage caveat.

### Pittsburgh (Wave 1) — condemned severity + dead-end distress factor
- **Source:** Wave-1 recon (2026-07-06). PLI condemned status + the "dead-end" flag (PLI cannot locate the owner).
- **Now (no bump, Slice 4):** condemned + dead-end stored + displayed as **unscored parcel facts** with provenance; a condemned `pgh` parcel's `risk_score` stays unchanged at v8.
- **Queued (needs bump):** (a) `pgh` condemned → an **unsafe-structure severity class** in risk scoring; (b) `pgh` **dead-end** (owner unlocatable) → a **new high-value distress factor** (an owner who can't be found by the city is a strong motivated-seller / opportunity signal).

## The next batch (proposed — separately gated on explicit approval)
Named "the v9 batch" when written; v9 and v10 both shipped other work, so these three remain
queued for whichever bump takes them. One ADR, one version bump, one coordinated recompute. Contents:
1. **hbg condemned scoring** (from the field-test batch).
2. **pgh condemned → unsafe-structure severity**.
3. **pgh dead-end → new distress factor**.
4. Anything else queued at bump time.

**Recompute bill** (batched behind one version, per ADR-0028): Philadelphia citywide ~4–5h (out-of-band), Harrisburg ~12 min, Pittsburgh ~1.2h. Golden parcels re-baselined at v9 only after the sweeps are confirmed complete. Leads / saved-search filters noted as mixed-version until sweeps finish.

## Not queued (verified as non-defects during recon)
- **Bug-1 zoning split** — the buildability scorer correctly sets `needs_variance=None` on unknown conformance (`buildability.py:203`); composition correctly yields "buildability uncertain". No methodology change; the fix is reader-side only.
