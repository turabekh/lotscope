# Feature ledger

Signals and capabilities that are *available* but deliberately unbuilt. An entry here is a recorded decision not to build, with the evidence that would change it — not a backlog item awaiting capacity.

**Promotion rule:** an entry is built when **three named ICP requests** ask for it. Named, not inferred from usage. Until then the data may be ingested and displayed, but nothing scores on it.

> **Resolved 2026-08-20.** The promotion rule is now Golden Rule 10 in `CLAUDE.md`, so it governs beyond this ledger.

---

## Case-level L&I pressure as a distress input

**Filed:** 2026-08-16 · **Status:** available, unbuilt · **Requests:** 0 of 3

`case_status` is ingested as of Slice 0 and nothing reads it.

**The signal.** 14,017 upstream rows read `COMPLIED` on `violationstatus` while `casestatus` is `IN VIOLATION` — the individual line item was fixed but the enforcement case stayed live. A further 16,325 read `IN VIOLATION - COURT`, and 451 `UNDER INVESTIGATION`.

**Why it is plausibly distress.** A live enforcement case is financial pressure on an owner even when the specific violation has been remedied — court dates, counsel, the risk of escalation. The current distress model sees none of it, because v11's `is_open_violation` requires `violationstatus = 'OPEN'` and those rows fail at the first test.

**Why it is not built now.** v11 already moves distress substantially (68,750 parcels lose +5, ~29,001 gain +10, prior-owner debt leaves the score). Adding a third movement in the same version would make the delta impossible to attribute, and the case-level reading is a judgement about what constitutes owner stress rather than a defect being corrected. This batch fixes what is wrong; it does not extend what is measured.

**What would change the decision.** Three named ICP requests, or evidence that owners with live cases and complied line items convert at a materially different rate than the general distress population.

**What it would cost.** Small — the column is already ingested, the predicate is one shared function, and it would ride a future distress profile version. The expensive part is the recompute, not the code.

**Recorded against:** `docs/v11-delta-ledger.md` (Slice 2, the 14,017-row judgement call).


---

## Reach the live sheriff-sale calendar from search

**Filed:** 2026-08-20 · **Status:** available, unbuilt · **Requests:** 0 of 3

`AreaSearchRequest.sheriff_sale_only` and the CivilView scraper are two disconnected populations wearing the same name.

**The gap, measured on production 2026-08-20.** The filter resolves to `coalesce(ts.in_sheriff_sale, false)`, the Revenue delinquency dataset's flag — 989 parcels. The scraper's upcoming calendar holds 867 rows across 10 sale dates, covering 866 distinct parcels. Parcels in both: **0**.

**Why it matters.** A buyer who sources exclusively at sheriff sales will reach for exactly this filter, and it returns a set that has nothing to do with what is going to auction. The scraper's data is good — parcel linkage is near-complete (62/62, 56/56, 357/357 on the major dates), opening bids are largely present, and the vacant subset runs 11–36 lots per sale date, which is precisely the size a buyer wants.

**Why it is not built now.** One named request, from the first trial user, who has not yet asked for it in her own words. The workaround costs an admin five minutes: read the sheriff-sale calendar for a date, filter to `parcel.is_vacant`, seed the parcel numbers into a saved list.

**What it would cost.** Small — a join from the search predicate to `sheriff_sale` on upcoming `sale_date`, plus a decision about whether "sheriff sale" in search means *scheduled for auction* or *flagged by Revenue*. Those are different questions and the filter should probably ask which.

---

## Split multi-party grantor lists in the delinquency attribution join

**Filed:** 2026-08-20 · **Status:** defect, queued behind a version bump — see `docs/verdict-bump-queue.md` · **Requests:** n/a

Not a feature; recorded here only as a pointer. `normalize_party_key` does not split grantor lists on `;`, so a sheriff-sale buyer's own grantor can fail to match and the debt is narrated as unexplained rather than discharged. 297 Philadelphia parcels (201 vacant) flip from `verify` to `likely_discharged` when the list is split. It moves risk severity and therefore `opportunity_score`, so it must ride a verdict bump. Evidence in `docs/preflight/trial-user-preflight-2026-08-20.md` §1.4.


---

## Flag city-owned parcels in Philadelphia

**Filed:** 2026-08-20 · **Status:** available, unbuilt · **Requests:** 0 of 3

`parcel.is_city_owned` is populated by loaders for `pgh`, `hbg` and `wlm`. There is no `phl` loader that sets it.

**Measured, production 2026-08-20:** **1** of 588,591 phl parcels carries `is_city_owned = true`; 588,586 are NULL. Meanwhile **11,956** phl parcels have an owner string reading `CITY OF PHILA`, Land Bank, or PHDC.

**What it costs today.** The assemblage panel reports `acquirability: "vacant"` and `has_city_owned_neighbor: false` for City-held lots — `1935 N MARSHALL ST`, owner `CITY OF PHILA`, is presented as an ordinary private vacant lot. For a buyer those are different worlds: a private negotiation versus a Land Bank / PHDC disposition with its own queue, pricing and eligibility rules. The domain glossary already promises "Land Bank / PHDC — flags city-owned lots"; for the flagship market it is not delivered.

**Why it is not built now.** No named request yet, and the honest version is not a string match on `owner`: PHDC, the Land Bank, the Redevelopment Authority and the City hold parcels under several names and dispose of them under different rules. A derivation that conflates them would be worse than the current NULL, which at least does not assert.

**What it would cost.** Small if it is a name-based derivation over `owner` at merge time; larger if it means ingesting the Land Bank / PHDC inventory as its own dataset, which is the version worth having.

---

## Fuzzy name matching for delinquency attribution

**Filed:** 2026-08-20 · **Status:** available, unbuilt · **Requests:** 0 of 3

Upstream records the same person more than once with different misspellings, and exact-per-party matching cannot see through it.

**The signal.** Two parcels are known: `phl:232331100` (`TANGHE CECELIA` against `TANGHE CECLIA MARY;TANGUE CECELIA MARY;…`) and `phl:221167100` (`JINKS GLORIA` against `JINKS PAUL;JENKS GLORIA C;…`). In both, the debtor is almost certainly the grantor, and in both the recorded spellings differ by one or two characters across duplicate party entries. They currently read `verify`/`medium` — the honest "cannot explain this" posture.

**Why it is not built now.** It is a scoring-rule change, not a tokenization repair. Edit-distance matching on party names decides whose debt a parcel carries, and a false positive there tells a buyer that someone else's lien is discharged. The population is two parcels; the blast radius of a loose threshold is the whole delinquent corpus.

**What would change the decision.** Three named ICP requests, or evidence that the duplicate-party-with-typos class is materially larger than two — the measurement is cheap and would come first.

**What it would cost.** Small in code, expensive in judgement: the threshold, whether it applies only within the sheriff-deed class, and whether a fuzzy match may ever reach `likely_discharged` or only `verify` with a softer note. That design is the work, not the matcher.
