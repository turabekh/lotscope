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

## Shipped

### Screening eligibility outranks economics — `DECISION_VERSION` d2 → d3

- **Source:** review sweep 2026-08-31. Measured on the local production copy.
- **Change:** in `decide()`, the `can_build_by_right is not True` branch now runs **before** the two economics branches.
- **Why it was wrong:** a parcel that is not dimensionally eligible with no variance path is blocked structurally, but the margin branches ran first, so it was given an economics reason whenever its margin happened to be weak. The same parcel returned `likely_pass` on a healthy margin and `economics_unattractive` on a weak one — the stated blocker flipped on a number irrelevant to why it fails, and "under current assumptions" invited the reader to retune inputs that can never make it eligible. This is the ordering defect #183 fixed for vacancy on the assessment surface, in a second module.
- **Scale:** **462 Philadelphia parcels** carried the wrong reason (`can_build_by_right IS FALSE AND needs_variance IS DISTINCT FROM TRUE AND recommendation = 'economics_unattractive'`). No other market is affected. The fix cannot move `opportunity_score` — that is computed before `decide()` is called and never reads its result. **A recompute will still move a few scores anyway**, from ordinary input drift since each row was last computed: the local 462 moved 6, three of them because the deal no longer yields an `est_margin` at all, so the neutral economics factor replaced a negative one. Do not attribute that movement to this change.
- **Why it takes a version, not a silent recompute:** this is decision-engine logic, not an input correction, so rows produced by the old ordering must not keep claiming the current engine produced them. `DECISION_VERSION` exists for exactly this and is checked alongside `VERDICT_VERSION` by `get_or_compute_current_verdict`, so reads self-heal on mismatch.
- **Sweep posture — deliberately NOT a full sweep.** `_STALE_ONLY_PREDICATE` matches on both versions, so `--only-stale` after a decision bump selects *every* parcel in *every* market: ~11.5h for `phl` alone, to correct 462 rows. The affected set is exactly enumerable by the predicate above, so **recompute those 462 and let everything else heal lazily on read.** Stored rows will carry mixed `d2`/`d3` for a while; that is a label lag, not a value disagreement, and no surface filters on `recommendation`.
- **Test note:** `test_an_ineligible_parcel_without_a_variance_path_is_a_likely_pass` already encoded the correct intent and passed the whole time, because the `_decide` helper defaults `est_margin` to a healthy value. The defect lived in the one dimension the test did not vary. Same family as handoff 0048 §3.

### Absentee owner mis-flagged on punctuation drift — no bump, distress sweep required

- **Source:** review sweep 2026-08-31. Measured on the local production copy.
- **Change:** `is_absentee` strips non-alphanumerics from both addresses before comparing. Previously a raw substring test, so any spacing or punctuation difference read as a different address.
- **Why it is a correction, not a methodology change:** the distress weights, tiers and factors are untouched; an input derivation was simply wrong. Same posture as ADR-0085 — **no `VERDICT_VERSION` or profile bump**, but the stored table must be swept.
- **Why it mattered:** OPA writes the location field joined and the mailing street split, so the drift is systematic rather than incidental — every Philadelphia `Mc` street mismatched (`2620 MCKEAN ST` against `2620 MC KEAN ST`), plus double-spaced and hyphenated variants. Affected parcels carried a visible "Absentee owner (out-of-area mailing address)" factor and 10 distress points while the owner lives at the property, and they feed outreach lists.
- **Measured over a full sweep** (baseline `pre_absentee_distress`, 777,703 rows):

| market | effect |
|---|---|
| `phl` | 2,537 parcels lost the false factor — 2,303 at −10, 234 at −15 (they also held `long_tenure`, which requires absentee). Exactly the predicted set. Leads ≥30: 38,559 → **38,552**. |
| `hbg` | **31** parcels, −10 each — the same class (`20TH`/`20 TH`, `1209A`/`1209 A`). Not predicted beforehand, because the pre-measurement was scoped to `phl`. |
| `pgh`, `wlm` | 0 changed. |

- **One movement is NOT from this change.** 88 `phl` parcels went **+5**, all with `years_since_last_sale` between 15.001 and 15.023 — they crossed the 15-year `long_tenure` threshold in the 9 days since the baseline was taken. `years_since_last_sale` is `CURRENT_DATE`-relative, so any sweep drifts against its own baseline. Expect this on every future sweep and do not attribute it to the code.
- **Cache purge is part of the job.** `ai/service.py` names distress factors in the summary payload, so cached artifacts for affected parcels assert the false absentee signal. Their keys carry `verdict_version`, which a distress correction does not move, so nothing invalidates them — purge `summary:*` / `report:*` for the affected parcels explicitly, per `CLAUDE.md` §12.

## Queued

### Party-name normalisation (from the v11 verify-posture packet)
- **Source:** `docs/decisions/verify-posture-name-mismatch.md`, measured 2026-08-18.
- **Change:** join single-letter runs so `VENUS L P` normalises to `VENUS LP`, and treat placeholder debtor names (`'not available'`, 22 parcels) as `unknown_debtor` rather than a failed match.
- **Why it needs a bump:** both move parcels from `verify` to `current_owner`, which changes `counts_toward_distress` and risk severity. Stored verdicts would stay stamped `v11` while the engine computed something else, and lazy recompute fires only on version mismatch — so nothing would ever detect the disagreement.
- **Trap:** the fix belongs in `party_match`, **not** `normalize_party_key`. The latter has a SQL twin (`normalized_name_sql`) and `parcel.owner_key` is a generated column built from it; the buyer census joins one against the other. Changing the Python side alone desynchronises the mailing join.

### Condemned / Demolished → risk scoring
- **Source:** Harrisburg field-test batch (2026-07-06), repository list carries `hbg_city_status` (Demolished / Condemned) per the City Codes Administrator.
- **Now (no bump):** stored + displayed as an **unscored parcel fact** with provenance (Slice 3).
- **Queued (needs bump):** feeding `hbg_city_status` into `risk_score` as an additive flag. Additive risk/scoring changes have always taken an ADR + a version bump (ADR-0015 distress index, ADR-0027 access flag, ADR-0039 distress v2) — this follows that precedent.
- **Note:** status is known only for repository-listed parcels; it is not citywide code-enforcement coverage. Any scoring must carry that coverage caveat.

### Pittsburgh (Wave 1) — condemned severity + dead-end distress factor
- **Source:** Wave-1 recon (2026-07-06). PLI condemned status + the "dead-end" flag (PLI cannot locate the owner).
- **Now (no bump, Slice 4):** condemned + dead-end stored + displayed as **unscored parcel facts** with provenance; a condemned `pgh` parcel's `risk_score` stays unchanged at v8.
- **Queued (needs bump):** (a) `pgh` condemned → an **unsafe-structure severity class** in risk scoring; (b) `pgh` **dead-end** (owner unlocatable) → a **new high-value distress factor** (an owner who can't be found by the city is a strong motivated-seller / opportunity signal).

### Philadelphia public ownership is never flagged — SHIPPED

> **Shipped 2026-08-24 in PR #181, deployed `9534057`, and run on production the same day: 13,426 parcels flagged, 9,175 → **0** publicly-owned parcels in lead range.** Derived from the OPA owner name as an **interim** measure (ADR-0085) because no upstream source exists — see `docs/data-sources.md`. **No version bump was taken:** the `public_ownership` risk flag is existing v11 methodology receiving correct input, and a targeted verdict recompute of all 13,426 kept stored rows honest. The analysis below is kept as the record. The remaining gap is the missing authoritative source, not the flag.
- **Source:** review sweep 2026-08-24. Measured on production.
- **Now:** `is_city_owned` is set by loaders for `pgh` (8.7% of parcels), `hbg` (4.6%) and `wlm` (0.12%). **No loader sets it for `phl`: 1 parcel of 588,606.** Handoff 0047 §5 saw one symptom of this (`1935 N MARSHALL ST` rendering as private in the assemblage panel) and ledgered it at 0-of-3 as a feature; it is a data gap, and it reaches further than that panel.
- **Scale:** 13,434 phl parcels carry a public-owner name (`CITY OF PHILA%` 4,886, `%PHILADELPHIA HOUSING%` 4,582, `%LAND BANK%` 2,490, `%REDEVELOPMENT AUTHORITY%` 1,473, `%PHDC%` 3). An owner-string match is a scoping estimate, not the fix — the fix is a Land Bank / PHDC / RDA parcel source, per §17.
- **What it currently costs, measured:**
  - `score_distress` returns `score=0, tier="none"` immediately for a city-owned parcel (`distress/scoring.py:61`). **13,431 of the 13,434 score above zero today**, and **7,539 clear the default lead threshold of 30** (`api/leads.py:24`) — 45 `high`, 7,494 `medium`. They surface as motivated-seller leads, saved-search matches and export rows as though privately owned. `savedsearch/matching.py:38`, `distress/service.py:158,175` and `watchlist/service.py:52` all exclude city-owned parcels and none of those exclusions fire.
  - `risk/scoring.py:361` never adds the `public_ownership` medium flag ("acquisition is through the public disposition process, not a private sale").
  - `assemblage/logic.py:46,82,99` treats them as private acquisition candidates and as a "clear path".
- **Why it needs a bump:** the `public_ownership` flag moves `risk_score`, so stored verdicts would disagree with the engine while still stamped `v11`, and lazy recompute fires only on version mismatch. It also zeroes distress for thousands of parcels, so it needs the distress sweep in the same batch.
- **Note:** this is the one queued item with an outreach dimension. Until it ships, lead lists can direct contact at the City, PHA and the Land Bank as if they were private sellers.

### Philadelphia vacancy is never derived from OPA land use — SHIPPED

> **Shipped 2026-08-24 in PR #177, deployed `8e4cb2b`, and run on production the same day: 13,752 parcels flagged, phl leads 38,583 → 41,621.** Additive only — the 9,150 VPI-vacant parcels OPA does not call vacant land were preserved and verified (ADR-0084). **No version bump:** `is_vacant` reaches the verdict engine only as batch scope. The analysis below is kept as the record.
- **Source:** review sweep 2026-08-24. Measured on production.
- **Now:** `VACANT_LAND_USES_BY_MARKET` (`vacancy/derivation.py:23`) registers `hbg` and `pgh` only, and `derive_vacancy` is called only from those two loaders. For `phl`, `is_vacant` comes solely from the Vacant Property Indicators loader, with no OPA `land_use` fallback. `_PGH_VACANT_USES` already contains the exact string `VACANT LAND` that phl uses.
- **Scale:** **14,020 of 42,583** phl parcels whose OPA `land_use` starts `VACANT` are unflagged — 32.9%. The suffixed values are far worse: `VACANT LAND - RESIDENTIAL` 1,731 of 2,242 missing (**77%**), `VACANT LAND - NON-RESIDENTIAL` 172 of 212 (**81%**), plain `VACANT LAND` 12,117 of 40,129 (30%). The two sources disagree both ways — 9,150 parcels are flagged vacant that OPA does not call vacant land.
- **What it currently costs:** those parcels miss the `vacant` distress factor (`vacant_weight=10`, `distress/scoring.py:103`), are absent from vacant-only search (`search/spatial.py:51` `coalesce(p.is_vacant, false) = true`), fall outside the vacant-only verdict recompute scope (`verdict/jobs.py:34`), and are not offered as vacant assemblage neighbours (`assemblage/logic.py:100`). Handoff 0047 §5 recorded `2138 N FAIRHILL ST` as a single miss; it is one instance of this class.
- **Why it needs a bump:** +10 distress on ~14,020 parcels changes who appears in lead lists, which is the surface ADR-0028 gates. It does **not** move `risk_score` or `opportunity_score` directly — `is_vacant` feeds verdict only as batch *scope* — so if the batch is ever split, this half is distress-sweep-only.
- **Open question for the packet:** whether an OPA-derived flag should carry the same weight as a VPI-sourced one. `derive_vacancy` already returns a confidence (0.35 single-signal / 0.5 multi-signal) that the phl path would need to respect rather than asserting a bare `true`.
- **Related, not queued:** `parcel.category` is 100% NULL in `phl`, `pgh` and `hbg` (populated only in `wlm`), and `brt_number` and `recorded_at` are 0% populated in **every** market. Dead columns, no scoring impact — noted so the next reader does not mistake them for a signal.

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

---

## Multi-party grantor lists are never split on `;` — SHIPPED

> **Shipped 2026-08-20 in PR #168, deployed `c61181a`. No version bump was taken**: severity moved `info` ↔ `medium` on 299 parcels but `counts_toward_distress` did not change on any of them, so it was accepted as a defect fix inside ADR-0083's methodology rather than a methodology change. Kept below as the record of the analysis. The two normalisation defects above are **not** addressed by it and still ride the next bump.

**Filed:** 2026-08-20 · Third defect in the same family as the two above.

`normalize_party_key` leaves semicolons in place, so `_tokens()` splits on whitespace and emits fused tokens (`WILLIAM;ASBELL`, `OF;MCNAIR`). A delinquency debtor who *is* named on the sheriff's deed can therefore fail `match_parties`, and `attribute_delinquency` falls through to `verify` instead of `likely_discharged`.

```
'ASBELL WILLIAM' vs 'ASBELL WILLIAM;ASBELL DORA'                            -> none
'MCNAIR KENNETH' vs 'CONNOR JOHN J;CONNOR JOHN J ESTATE OF;MCNAIR KENNETH'  -> none
'MATUSOW JOSEPH' vs 'MATUSOW JOSEPH;MUTNSON JOSEPH'                         -> partial
```

The passing cases pass by luck — enough tokens happen to fall clear of a semicolon to reach `_MIN_SHARED_TOKENS`.

**Measured scope (production, 2026-08-20).** 1,077 phl parcels are delinquent with a multi-party-grantor sheriff's deed as their first post-snapshot transfer; **297** (201 vacant) flip `verify` → `likely_discharged` once the list is split.

**Why it rides a bump.** `counts_toward_distress` is `False` on both sides, so distress does not move — but severity moves `info` ↔ `medium`, which moves `risk_score` and `opportunity_score`. Lazy recompute fires only on version mismatch, so shipping it quietly would leave stored verdicts disagreeing with the engine.

**Same trap as the entries above:** the fix belongs in `party_match` (split each side's parties before matching), **not** in `normalize_party_key`, which has a SQL twin backing `parcel.owner_key`.
