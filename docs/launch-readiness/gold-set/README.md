# Philadelphia gold set — schema and review workflow

**Requirement:** Amendment 03 §16 (LR-Q001–LR-Q004) · **Backlog:** LR-B-007 (framework), LR-B-008 (review)
**Status:** framework built; the real set is unpopulated and unreviewed.

This is the machinery for checking LotScope's Philadelphia output against reality. It does not, and cannot, produce a professional conclusion — §16 is explicit that automated tests do not replace this review.

---

## What the framework does and does not claim

The evaluator compares expected facts against current verdict output and classifies each mismatch. That is all.

**It cannot mark a case reviewed.** `review_status` defaults to `unreviewed`, and the schema rejects `reviewed` unless a named reviewer and a review date are both recorded. A run of `make gold-set` on a hundred green cases proves the product agrees with what someone wrote down — not that what they wrote down is right, and not that a professional has looked.

That distinction is the whole point of the gate. `reviewed_cases` is reported separately from `evaluated` for exactly this reason.

---

## Where cases live

| Path | Contents | In git |
|---|---|---|
| `backend/data/goldset/phl-sample.jsonl` | Three synthetic cases demonstrating the format | **Yes** |
| `backend/data/goldset/phl.jsonl` | The real set | **No — gitignored** |

Gold-set evidence may be licensed, owner-confidential, or contain owner names, so the real file stays out of the repository (CLAUDE.md §13). The synthetic sample carries no real parcel and no PII.

Note that `/backend/data/*` already excludes the parent, so `.gitignore` re-includes the directory before the file; removing either line silently re-hides the sample.

---

## Case schema

One JSON object per line. Blank lines and `#` comments are skipped.

```json
{
  "parcel_number": "phl:123456789",
  "categories": ["standard_rsa_rowhouse", "historic"],
  "expected": {
    "district_code": "RSA-5",
    "can_build_by_right": true,
    "by_right_units": 1,
    "requires_master_plan": false,
    "street_access": true,
    "expected_risk_flags": ["historic_district"]
  },
  "evidence_refs": ["https://atlas.phila.gov/", "ZBA calendar 2025-04-16"],
  "reviewer": "A. Zoning RA",
  "reviewed_on": "2026-07-28",
  "review_status": "reviewed",
  "notes": "Corner lot; frontage measured from the deed, not the parcel layer."
}
```

**Every field in `expected` is optional.** An omitted field is not compared — record only what the reviewer actually established. Asserting a value nobody checked manufactures a discrepancy or, worse, a false pass.

`review_status` is `unreviewed` (default), `reviewed`, or `disputed`. Use `disputed` when the reviewer and the product disagree and the correct answer is not yet settled; it keeps the case in the set without pretending it is resolved.

---

## The 17 required categories

`standard_rsa_rowhouse` · `undersized_lot` · `oversized_or_double_lot` · `corner_or_irregular` · `assemblage_candidate` · `mixed_use_district` · `multifamily_district` · `industrial` · `special_purpose_district` · `historic` · `flood_exposure` · `public_ownership` · `tax_delinquency` · `access_problem` · `developed_appearing_vacant` · `known_permit` · `zoning_appeal`

A case may carry several. The report shows coverage per category so gaps are visible before the set is declared complete.

---

## Severity, per LR-Q003

Severity is derived from **which field** disagrees, not from the reviewer's mood:

| Severity | Fields | Why |
|---|---|---|
| **Critical** | `district_code`, `can_build_by_right`, `by_right_units`, `requires_master_plan`, `street_access` | Could cause a user to pursue or buy on a false premise |
| **Material** | risk flags, everything else compared | Changes underwriting or diligence but is likely caught later |
| **Minor** | recorded in notes | Presentation and labelling |

`make gold-set` **exits non-zero when any critical discrepancy exists.** Material and minor do not fail the run — they are the profile the owner accepts or rejects under LR-Q004.

---

## Running it

```bash
make gold-set                                  # data/goldset/phl.jsonl
make gold-set FILE=data/goldset/phl-sample.jsonl
cd backend && uv run python -m lotscope.goldset.cli data/goldset/phl.jsonl --json
```

The evaluator reads **stored verdicts**; it does not recompute. Recompute first when validating a change:

```bash
cd backend && uv run python -m lotscope.verdict.jobs --market philadelphia
make gold-set
```

The report names the `verdict_version` it ran against, so a version change can be rerun and compared.

---

## The review workflow

1. **Select** parcels covering all 17 categories. Aim past 100 — cases get discarded when the underlying record turns out ambiguous.
2. **Record expected facts** from official sources only: the zoning map and code, issued permits, ZBA decisions, recorded sales, authoritative parcel and tax records. Cite each in `evidence_refs`. Leave unknowns out.
3. **Leave `review_status` as `unreviewed`** until a qualified person — architect, zoning consultant, or expediter — has actually looked. Setting it otherwise is the one thing this framework is built to prevent.
4. **Run** `make gold-set` and triage the discrepancies.
5. **Resolve every critical** discrepancy before Philadelphia can be called commercially verified. Either the product is wrong and gets fixed, or the expected fact is wrong and gets corrected — with the evidence updated.
6. **Record acceptance.** LR-Q004 requires the owner to accept the residual material-error profile explicitly. That acceptance belongs in `docs/launch-readiness/gates.md` under G4, dated.

---

## Exporting

`--json` emits the full report with no owner names, addresses, or contact data — only parcel numbers, field names, and expected-versus-actual values. Safe to share with a reviewer or attach to a gate review.
