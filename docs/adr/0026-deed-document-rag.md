# 26. Deed-document RAG ("Ask the Parcel" over recorded deeds)

Date: 2026-06-29

## Status

Accepted. Decisions (signed off): deed source = **DOR portal harvest** (staged last; needs ToS review + live access in the deploy environment); OCR = **PaddleOCR** behind an `OcrEngine` protocol, lazy-imported and an optional/worker-only dependency so core install/CI/tests don't pull `paddlepaddle`; blob storage = **local/MinIO for dev** behind a `BlobStore` interface (S3 in prod, same boto3/S3 API); restriction extraction = **LLM structured-output pass**.

### Phased plan

- **Phase 1 (build now — fully testable, no heavy deps at test time):** deed model + `DeedRestriction` table; `BlobStore`/`OcrEngine`/`DeedSource` protocols with a `LocalBlobStore`; LLM `extract_restrictions` (structured, validated); a `process_deed` pipeline (text → extract → persist restrictions + chunk/embed into `document` as `source='deed'`, parcel-scoped via `doc_metadata`); parcel-scoped deed retrieval wired into `ask_the_parcel`; `GET /parcels/{id}/deed-restrictions` + a dossier panel. All seams mocked in tests (fake OCR/source/embedder/generator + real PostGIS).
- **Phase 2 (needs your env):** real `PaddleOcrEngine` (optional dep + model download) and MinIO/S3 `BlobStore` wired end-to-end; a worker job + CLI to process a deed file.
- **Phase 3 (needs ToS + live access):** DOR-portal `DeedSource` harvester with idempotent per-document fetch.

## Context

PRD §5.6 lists **deed / restriction extraction** and §5.15 a **document store + OCR** (both Differentiator): surface recorded-deed restrictions (e.g. "no multi-family", easements, conditions) and let "Ask the Parcel" answer from them with citations. This is the second pillar of the flagship AI feature; today the RAG grounds only on Title 14.

What already exists (ADR-0008) and is **reused unchanged**:
- A `document` table with `source`, `section`, `title`, `content`, `doc_metadata` (JSONB), and a `vector(1024)` embedding under an HNSW cosine index.
- Voyage embeddings behind an `Embedder` protocol; grounded, cited, schema-validated generation via the centralized `ai/` client; citation enforcement (`UngroundedAnswerError`).
- `ask_the_parcel` retrieves Title-14 docs by `source` filter and assembles a cited prompt.

So the RAG/embedding/grounding layer is **done**. The unbuilt pieces are: (1) a source of deed text, (2) OCR, (3) blob storage, (4) restriction extraction, (5) parcel-scoped deed retrieval wired into `ask_the_parcel`.

**The real blocker is (1) — acquiring deed text.** `rtt_summary` (already ingested) gives transfer *metadata* (parties, type, consideration, recording date) but **not** the deed body where restrictions/easements live. The deed bodies are scanned images in the City's DOR recording system (PhilaDox/records portal), which has **no documented bulk API**; pulling them implies portal access/scraping with ToS and legal/UPL considerations. Everything else is tractable; this is the part that needs a decision and carries risk.

## Decision (proposed)

Extend ADR-0008 rather than introduce a new datastore. A new `documents` ingestion path: **fetch deed → store raw in S3 → OCR → LLM restriction-extraction → chunk + embed into `document` (`source='deed'`) keyed to the parcel via `doc_metadata` → `ask_the_parcel` additionally retrieves parcel-scoped deed chunks and cites them.** A small structured `deed_restriction` table surfaces extracted flags on the dossier. Parcel linkage uses `doc_metadata->>'parcel_number'` (+ a parcel-scoped retrieval query) — **no schema migration to `document`**. All deed answers stay informational, cited, confidence-scored (§9/§13), with an explicit "confirm with title/counsel" disclaimer given UPL exposure.

### Open decisions (need your sign-off)

1. **Deed-text source** *(the blocker)* —
   - **A. Sample-first (recommended):** build and prove the full pipeline on a small set of real deed PDFs (hand-collected), `source='deed'`, deferring bulk acquisition. Ships a working, demoable feature without committing to a scraping/legal path.
   - **B. DOR portal harvest:** automate pulling deed images from the City records portal. Highest coverage, but ToS/legal review required and brittle.
   - **C. Third-party/licensed data** (title provider / Regrid add-on): cleanest legally, has a cost/contract.
2. **OCR provider** — **AWS Textract (recommended; AWS-native per §2, strong on scanned legal docs)** vs Google Document AI vs open-source `ocrmypdf`/Tesseract (no cloud dep/cost, weaker on poor scans). Behind an `OcrEngine` protocol so it's swappable and mockable.
3. **Blob storage** — **S3** (per CLAUDE.md), adds `boto3` + bucket config; or local/MinIO for dev. Confirm the dependency + bucket.
4. **Restriction extraction** — an LLM pass (Claude, structured output) producing typed restrictions (kind, text, citation span, confidence); validated like every other LLM output. Confirm this vs. regex/rules-only.

## Consequences

- Reuses the embedding/vector/grounding stack; new surface area is the OCR + extraction pipeline and S3 — all behind protocols and mockable, tested with fixtures (no network in tests), consistent with §9/§12.
- New external dependencies depending on the choices above (Textract/`boto3`, possibly a data provider) — each recorded here once chosen.
- **Legal/UPL is first-class:** deed interpretation is informational, cited to the document/span, confidence-scored, never presented as a title determination; disclaimer surfaced. Data licensing/ToS for the chosen source must be honored.
- Option A ships value quickly and de-risks the pipeline; bulk coverage (B/C) becomes a follow-up decision once the pipeline is proven.
- OCR cost scales with document volume; the pipeline is idempotent per document id and runs as an ARQ job, so re-runs are cheap and bounded.

## Update (2026-06-30) — Phase 3 deed-text source resolved

Open decision 1 (deed-text source) is settled after validating the actual City source. The DOR system is **PhilaDox/iCris**: a paid-subscription web portal ($15/day–$750/yr), watermarked PDFs, **no API or bulk export**, free access limited to name/address search, indexed by name/address/book-page (not OPA parcel). The "OpenDataPhilly PhilaDox" entry only points back to the same paid portal. Bulk harvesting (option B) would require a paid session and almost certainly breaches the City of Philadelphia License / portal ToS, so it is **rejected**.

**Decision: compliant, lazy, per-parcel design.**
- We already hold **parcel → recorded-document-ID** for free via RTT (`sale.document_id`, ~172k deeds across ~140k parcels). The deed feature surfaces this as a per-parcel **recorded-document index** with grantor/grantee/type/date and a **deep-link to the official PhilaDox record** (`InstrumentID={document_id}&Guest=true`, base URL in `Settings`). We redistribute nothing paywalled; the user retrieves the instrument from the official source themselves.
- Actual deed **text** (for OCR→extract→embed RAG) is fetched **lazily, per parcel, only on demand**, and only through a **credential- and ToS-gated** `DeedSource` adapter that is **off by default** — or from user-supplied PDFs. A recorded deed is marked `analyzed` once its text has been processed (`deed_document.external_id == sale.document_id`).
- This keeps citywide coverage for the *index* (compliant, now) while gating the *text* behind a licensed feed, honoring §13. Bulk text acquisition remains blocked on a licensed source; sample/user-provided deeds (option A) exercise the real pipeline in the meantime.
