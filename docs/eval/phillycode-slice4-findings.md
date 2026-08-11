# Phillycode Slice 4 — findings in progress

Status: partial. Scorecard v2 not yet produced. This file collects findings as they are established so the PAUSE 2 package assembles from evidence rather than memory.

Run artifacts: `run-2026-08-11-a` — 30 cases × 2 arms, 60 generations, zero errors, ~USD 1.80.

---

## F1 — The citation contract cannot express a correct refusal

Both arms were asked what the Home Rule Charter says about council districts. Both **refused correctly in prose**:

> *title14:* "The provided context does not contain any information about the Philadelphia Home Rule Charter or its provisions regarding council districts."
> *phillycode:* "The provided context documents do not contain any information from the Philadelphia Home Rule Charter regarding council districts... I do not have enough information to answer your question."

Both nonetheless attached a citation — `14-701 / 14-602 (RSA-5)` and `14-400` respectively — to provisions that do not support the refusal, because nothing supports a refusal.

**This is structural, not model laxity.** `ParcelAnswer.citations` is described to the model as "never empty" (`ai/schemas.py`), and `ai/service.py` raises `UngroundedAnswerError` when the list is empty. The contract therefore *requires* a citation on every answer, including one whose content is "I cannot answer this". The model satisfies both instructions the only way available: refuse in prose, attach the nearest retrieved provision.

Closest to category (b) — cited retrieved-but-irrelevant provisions — but the cause is that **the schema has no representation for a correct refusal**. At the contract level a refusal and a grounded answer are indistinguishable, and the attached citation is decorative.

Two consequences:

1. **A product finding on the mechanism the architecture leans on.** An answer that refuses while citing a provision looks grounded to any consumer reading citations programmatically. The enforcement prevents *uncited* answers; it does not prevent *decoratively cited* ones.
2. **A metric defect.** `refusal_correct` was defined as "declined in prose AND no citations", which the shipped architecture can never satisfy. Refusal scoring must be redefined as prose-declination, with the decorative citation reported separately.

Recorded, not fixed. Per the slice constraints `ai/service.py` is untouched; the fix is its own change with its own tests, and this eval measures shipped behaviour.

## F2 — RSA-5: correcting my own earlier characterisation

The evidence chain at the printed page stands: `philadelphiahomerulecharter.pdf` p.951, read with pdfplumber independently of the parser's table pipeline, gives RSA-5 (position 8 of 11) as **`960 [2]`** in Table 14-701-1's minimum-lot-area row, with footnote markers cross-checking cell alignment (`[1]` on RSA-4, `[2]` on RSA-5, each matching the note that describes that district). `code_provision.table_data` agrees. **No extraction defect.**

**What I got wrong was the incumbent.** I recorded that it "states 1,440 while citing Table 14-701-1, which does not contain that figure", and framed it as a clean error on the city's most common district. That conclusion came from reading the first 330 characters of its summary, which truncated mid-sentence. The full text says:

> "minimum lot area 1,440 sq ft, **or 960 sq ft in Council Districts 1, 2, 3, 5, and 7**; a lot of at least 1,600 sq ft may be subdivided into lots as small as 800 sq ft under stated conditions."

So the incumbent names all three figures — 1,440, 960, 800 — and conditions them geographically. The code reaches the same shape from the other direction: the base table says 960, and council-district overlays raise it to 1,440 (`14-520` is the Ninth District Overlay, `14-524` the Fourth District Overlay, `14-514` the Far Northeast; seven Title 14 provisions mention council districts).

**The honest finding is narrower than the one I recorded.** The literal claim survives — Table 14-701-1 contains 960, not 1,440, so citing that table for 1,440 is a mis-citation. But the incumbent is not ignorant of 960, and its account is a defensible inversion of the default rather than an invented number. It should not be carried into the findings as "the incumbent is wrong on the most common district".

Ground truth for `dim-rsa5-lot-area` is unaffected: Table 14-701-1 is the provision that answers it.

**A wider consequence worth a ledgered follow-up:** `zoning_standard` is seeded from the same Quick Guide. If its RSA-5 base is 1,440 where the code's base table says 960, every downstream buildability and verdict figure for RSA-5 inherits the inversion. That is a post-eval audit, not this slice.

## F3 — Retrieval works at scale; citation format is what the v1 scorecard actually measured

Valid from run-a: **retrieval presence for phillycode is 0.864** on the 22-case decision base — the expected provision reached the assembled context in 19 of 22 cases. This measurement is internally consistent because context and ground truth share the node-id vocabulary.

The v1 hit rates (0.000 incumbent, 0.273 phillycode) are artifacts of vocabulary mismatch, not performance, and are superseded by the R1/R2 re-scoring.

Latency baseline, both arms measured: incumbent p50 8.4s / p95 13.9s; phillycode p50 13.5s / p95 22.0s. Under the signed thresholds that is a **p50 fail** (13.5 > 12.6) and a p95 pass (22.0 < 27.8).

## F4 — `zoning_standard` carries the inverted RSA-5 minimum, and buildability gates on it

Checked directly: `zoning_standard` for `phl` / `RSA-5` holds `min_lot_area_sqft = 1440.00`, sourced from `title14-quickguide-2026-02`. Table 14-701-1 — verified at the printed page — sets it at **960**.

`zoning/buildability.py` compares `dims.lot_area_sqft < standard.min_lot_area_sqft` and reports the lot as below "the 1440 sqft minimum for RSA-5". So an RSA-5 lot between 960 and 1,440 sqft is told it is not buildable when the code's base table says it meets the minimum. That is a false negative on the product's core question, in the city's most common residential district.

Local measurement understates the reach: only 8 of ~329 local RSA-5 parcels carry a non-null `lot_area_sqft`, and 3 of those 8 fall in the affected band. The production proportion is the number that matters and is not measurable from here.

**The fix is not a single value change, which is why this needs its own slice.** The minimum is geography-dependent: the code's base table says 960, and council-district overlays (`14-520` Ninth, `14-524` Fourth, `14-514` Far Northeast) set 1,440 within their boundaries, while the Quick Guide states the inverse default. A scalar column cannot express a conditional standard, so the options are a corrected scalar plus a documented caveat, an overlay-aware resolution path, or a confidence/qualifier on the field — a decision with verdict-contract consequences.

Recorded here rather than fixed: this slice's constraint is that it measures shipped behaviour, and a change to `zoning_standard` moves stored verdicts.

**Where the fix went (added 2026-08-11).** F4 was briefly fixed on this branch and has been reverted, deliberately. A scalar correction alone converts ~58.5k false negatives into ~54.4k false positives, because six §14-500 overlays — not the three named above — restore the 1,440 minimum over 48% of the affected band. The correction now belongs to **verdict v9**, which pairs it with overlay-aware effective-standard resolution so the in-overlay parcels keep 1,440. See `docs/audit/zoning-standard-vs-title14.md` and `docs/v9-overlay-aware-standards-recon.md`. Do not re-fix it here: this slice measures shipped behaviour.
