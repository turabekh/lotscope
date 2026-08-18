# Decision packet — should a bare name mismatch halve a parcel's risk?

**For:** owner sign-off. **Raised:** 2026-08-18, from the v11 sweep. **Status:** open — v11 ships the current behaviour; this asks whether to keep it.

ADR-0083 D3's stated principle is that **liens run with the land**, so a parcel-level risk flag never silently disappears on an unconfirmed settlement. In the shipped code the flag does not disappear — but `risk/scoring.py` forces `severity = "medium"` on the `verify` posture, which **halves the weight** (40 → 20) of any delinquency that would otherwise score `high`. This was not in the ADR's delta table.

`verify` is reached by two populations. One is uncontroversial: a post-snapshot transfer occurred, so *something* changed hands and "verify" is the honest reading. The other has no deed of any kind — the debt is simply recorded against a name that does not match the current owner.

## The population, measured

Philadelphia parcels that are delinquent, would score `high`, and have **no post-snapshot transfer at all**:

| `match_parties` strength | parcels | share | posture | effect |
|---|---|---|---|---|
| exact | 14,221 | 56.4% | `current_owner` | debt counts, no change |
| partial (≥2 shared tokens) | 7,135 | 28.3% | `current_owner` | debt counts, no change |
| **none** | **3,867** | **15.3%** | **`verify`** | **risk weight halved** |
| total | 25,223 | | | |

**A correction this supersedes.** The delta ledger extrapolated ~6,169 for this class from the sweep's −20 movement. That figure is inflated: the pre-sweep baseline is version-mixed (v8/v9/v10), so some of that movement predates v11. **3,867 is the direct population count and has no such confound.**

The two-shared-token partial rule does more work than expected — it already absorbs `BERRY JOSEPH F` / `JOSEPH F BERRY`, `KEYSTONE PHILADELPHIA PROPERTI` / `KEYSTONE PHILADELPHIA PROPERTIES L P`, and `LANDMARK PROPERTY GROUP LLC` / `LANDMARK PROPERTY GROUP`. Name-order reversal, source truncation and entity suffixes are handled.

## What the residual 3,867 actually contains

Sampled from the top of the cohort by amount owed:

**Genuinely different parties — downgrade is correct.** `SILVERMAN LEON` / `PECO`. `READING CO` / `SEPTA`. `SCHUYLKILL RIVER EASTSIDE RR C` / `CSX TRANSPORTATION, INC`. `ACADEMY OF MUSIC OF PHILA INC` / `MARABELLA PARTNERSHIP`. `K4 PHILADELPHIA LLC` / `SHAPIRO ELIZABETH C`. These read as ownership changes with no transfer in our data, which is exactly what "verify with the Dept. of Revenue" is for.

**Same party, and we are wrong.** `VENUS LP` / `VENUS L P` — differs only in whether the suffix is spaced. `normalize_party_key` strips `.,#` and collapses whitespace but does not join single-letter runs, so the tokens are `{VENUS, LP}` against `{VENUS, L, P}` — one shared token, no match. `MILLER JT JT` / `MILLER J T` is the same failure. `KANYA STEVE` / `KANYA STEPHEN` is a nickname, sharing only the surname.

**Ambiguous, and arguably should stay ambiguous.** `PRICE THOMASINA` / `JOHN M A PRICE`, `GIBSON SARAH` / `ROBERT GIBSON`, `REED STACY M` / `REED SEAN`. Same surname, different given name — an heir, a spouse, or an unrelated party. Labelling these "verify" is defensible.

**Source junk.** `delinquency_owner = 'not available'` on **22 parcels**, currently treated as a person's name that fails to match. Small, but plainly wrong.

## Options

**A — keep it (no change).** The 3,867 keep the flag, keep the vintage, and lose half the weight. Accepts a minority of false downgrades on formatting variance in exchange for not overstating risk against the current owner. **Cost:** a handful of parcels where the debt genuinely is the owner's read as half as risky, on a snapshot frozen in June 2022.

**B — halve only when a transfer explains it.** Restrict the severity downgrade to the transfer-backed `verify` path; a bare name mismatch keeps full weight and gains the "verify" wording only. Most faithful to D3 as written — the lien on the parcel has not changed, and we have no document suggesting it has. **Cost:** ~3,867 parcels keep deal-killer weight on a debt that may be someone else's, though the copy says so.

**C — B, plus close the two normalisation gaps.** Join single-letter runs so `L P` normalises to `LP`, and treat placeholder debtor names as `unknown_debtor` rather than a failed match. Cheap and independently correct. Shrinks the cohort before any policy decision is applied to it.

## Recommendation

**C, then B.** The normalisation gaps are defects regardless of which policy wins — `VENUS LP` and `VENUS L P` are the same party under any reading, and `'not available'` is not a name. Fix those first so the policy question is asked of a clean population.

On the policy itself, B is the better fit for the principle the ADR actually states. A lien runs with the land; a name we cannot match is evidence about *the record*, not about the parcel. Downgrading parcel risk because the city's four-year-old snapshot spells the owner differently asserts more than we know. The `verify` wording already tells the reader to check — that is the honest half — and the weight is the half that should not move without a document behind it.

Neither option is urgent: v11 ships A, and the difference is confined to how ~3,867 parcels rank, not to who appears in lead lists (distress membership is governed separately and already excludes non-attributed debt).

## Sequencing — C must not ship on its own

Correcting the recommendation above: "cheap and independently correct" describes the *change*, not the *release*. Both parts of C alter which parcels resolve to `current_owner` rather than `verify`, and that feeds `counts_toward_distress` and the risk severity — so it moves stored scores.

Shipping it without a version signal reproduces the exact failure this batch spent itself cleaning up. Stored verdicts would remain stamped `v11` while the code computed something different, and because lazy recompute fires only on **version mismatch**, nothing would ever notice. The rows would silently disagree with the engine that claims to have produced them.

So C rides the next `VERDICT_VERSION` bump, or it ships with a full recompute attached. It does not go out as a quiet correctness fix. Queued in `docs/verdict-bump-queue.md`.

**A second reason not to touch it casually.** The single-letter-run fix is tempting to make in `normalize_party_key`, which is the wrong place. That function has a SQL twin in `normalized_name_sql`, and `parcel.owner_key` is a **generated column** built from the same expression; the buyer census joins one against the other. Changing the Python side alone silently desynchronises the mailing-address join in `buyers/service.py`. If this fix is made, it belongs in `party_match` — or in both twins at once, with a test that pins their agreement.
