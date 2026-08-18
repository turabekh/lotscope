# Verdict bump queue

Methodology changes that alter verdict outputs are **batched** into the next `VERDICT_VERSION` bump rather than shipped piecemeal (per the invariant). Data corrections (field mappings, new facts) recompute without a bump. This file collects queued items until the next batched bump.

Current `VERDICT_VERSION`: **v11**.

**Shipped since this file was last accurate.** It read `v8` while `v9` was already live, and described a "v9 batch" that is not what v9 became — recorded here so the drift is not repeated:

- **v9** — overlay-aware effective zoning standards (ADR-0080). Not the batch proposed below.
- **v10** — two changes batched behind one bump:
  - market-only comparable sales: sheriff's and nominal-transfer deeds excluded, soft lot-size similarity band (ADR-0081). Philadelphia only; other markets' selection unchanged.
  - `opportunity_score` scaled by deal economics, so it can no longer rank an `economics_unattractive` parcel above one recommended for investigation (ADR-0082).

- **v11** — the data-integrity batch (ADR-0083), accepted 2026-08-18: delinquency attributed to the owner who actually owes it, `case_status` read alongside `violationstatus` so a complied violation stops counting as open, recovered keyless deeds in `sale`, and the mailing column OPA actually publishes feeding `is_absentee`. Bumps the Philadelphia distress profile to `philly-distress-v2` in the same batch, so **v11 is the first bump requiring a distress sweep as well as a verdict sweep**.

**The v10 sweep was deliberately abandoned at 10.3% and discarded**; v11 overwrites every stored row in one pass, so nothing is owed from it. Verdict reads recompute lazily on version mismatch, so any parcel a user opens carries a current verdict while the sweep runs.

Distress splits: `assess_parcel_distress` scores **live** from raw signals on every read, so the parcel detail surface is current the moment the code deploys. The stored `parcel_distress` table has no such path, and it is what leads, saved-search matching, feed and spatial search filter on (`pd.score >= :min_score`). Those surfaces carry v1 scores — a prior owner's debt still admitting parcels to lead lists — until the distress sweep runs. **Distress is therefore swept before verdicts, and it is the sweep that actually changes who gets contacted.**

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
