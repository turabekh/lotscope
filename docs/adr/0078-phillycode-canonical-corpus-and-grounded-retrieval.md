# ADR-0078 — The Philadelphia Code as a canonical corpus, with retrieval derived from it

Status: accepted (2026-08-08) — with deviations recorded below from Slice 1 recon

Amends **ADR-0008** (AI, RAG, and grounded answers). Applies the raw→canonical doctrine of **ADR-0036** to legal text. Partially addresses the unverified-parking-tables item carried in handoffs 0039–0040.

## Context

"Ask the Parcel" is grounded in a corpus called `title14` that is not Title 14. It is a transcription of the **Base Districts Quick Guide** (February 2026) — the same summary document behind `zoning_standard` — chunked at 1,500 characters with 150 overlap and embedded. It covers dimensional tables and use permissions well, and it is what the citation contract was tuned against. But it is a summary citing itself: the assistant attributes answers to "14-701 (RSA-5)" on the authority of a transcription, not the code.

A parsed primary source now exists. The **phillyruleparser** project extracts the entire Philadelphia Code from the city's published PDF (`source_version` May 25, 2026) into **29,297 provisions across 24 titles**, each carrying:

- a canonical citation (`14-303(12)(e)(.1)`) and a globally unique `id` (68 cites repeat in the source; ids are suffixed)
- hierarchy (`parent`, `path`, `order` — parents always precede children)
- normalised `text` and verbatim `raw_text`
- structured tables (`{caption, header_rows, rows}`, continuations merged)
- cross-references (`refs`), history notes, footnote marks, page provenance, and `source_version`

23 of 24 titles pass the parser's QA gates 1–3 (coverage 99.89–100% against a 99.5% threshold). **Title 9 fails**, due to a defect in the source document itself.

Three deficiencies in the current arrangement motivate this decision:

1. **The grounding is secondary-source.** Answers about the code cite a summary of the code. For a product whose contract is "a headline claim never outranks the evidence beneath it" (ADR-0076), this is the same defect shape we have been sweeping out of the UI, one layer down.
2. **Character chunking destroys legal structure.** A provision is an atomic unit with a citation; a 1,500-character window is not. Chunk boundaries fall mid-provision, and the retrieved text carries no lineage, no siblings, no cross-references.
3. **Nothing is queryable.** There is no way to fetch §14-502 deterministically, walk a chapter, or follow a cross-reference. The district lookup in `ai/retrieval.py` regex-scrapes district codes out of the `section` string — a sniff, not a lookup.

## Decision

**Adopt the parsed Philadelphia Code as a canonical corpus in LotScope, and derive the embedding layer from it.** Two layers, one direction of derivation.

### 1. Artifact contract: the parser produces, LotScope consumes

phillyruleparser remains a standalone tool and learns nothing about LotScope. Its emitted artifacts — `title_N.jsonl`, `qa_title_N.json`, `qa_summary.json` — are **copied** (never moved; the parser's outputs remain regenerable in place) into `backend/data/phillycode/`, gitignored and mirrored to GCS alongside other data assets, keyed by `source_version`. LotScope's loader owns the mapping from the parser's `Provision` shape; the parser does not emit a LotScope-shaped export.

**Accepted risk, revised 2026-08-08.** This decision originally named "the parser repository is pushed" a prerequisite before its output became a production input. That prerequisite was not met and the consumer shipped anyway (Slice 1, PR #126). Put to the owner explicitly, the answer was to keep the parser local-only — its own `CLAUDE.md` carries a standing "local commits only, never push" rule — so the condition is recorded here as an accepted risk rather than left standing as an unmet requirement, which would misrepresent the state of the system.

What that means concretely: the code producing a production input exists on one machine with no off-machine copy, as do the 36 MB source PDF and every artifact — the parser gitignores `data/` in full, so even a push would protect the code and not the data. LotScope's own copy under `backend/data/phillycode/` is gitignored too and lives on the same disk. Revisit if the machine changes or a second person joins.

### 2. Canonical layer: `code_provision`

A new table holding the parsed code as domain truth, adopting the parser's schema with a `market_code` column:

| column | notes |
|---|---|
| `id` | primary key — the parser's globally unique id, **not** `cite` |
| `market_code` | `phl` now; the shape generalises if another market's code is ever parsed |
| `cite` | indexed, not unique (68 legitimate repeats in the source) |
| `kind` | title · chapter · section · subsection · table · figure · note |
| `title_number`, `parent`, `order`, `path` | hierarchy; indexed `(market_code, title_number, order)` and `parent` |
| `heading`, `text`, `raw_text`, `history` | normalised body, verbatim body, history notes |
| `refs`, `note_refs` | JSONB; `refs` enables cross-reference joins |
| `table_data` | JSONB `{caption, header_rows, rows, pages, continuation_of}` on table nodes |
| `page_start`, `page_end`, `source_file`, `source_version`, `loaded_at` | provenance |

The loader is idempotent per title (upsert on `id`, prune rows absent from the artifact) and **QA-gated**: a title loads only if its `qa_title_N.json` passes gates 1–3. **Title 9 is therefore hard-excluded** — recorded in the load report as an explicit exclusion, not silently absent — and admits itself automatically the day the parser passes it. A citation-enforcing assistant must not carry text its own producer failed; a "degraded but citable" middle state was considered and rejected as a permission slip.

This layer is what makes the corpus a capability rather than a bigger vector store: deterministic cite lookup, chapter walks, refs joins, and independent cross-checks against seeded reference data.

### 3. Embedding layer: derived, provision-linked, structure-preserving

`document` rows for the new corpus are **derived from `code_provision`**, never loaded independently, under a new source `phillycode`. Every row carries `doc_metadata.provision_id`, plus `title_number`, `kind`, `cite`, `path`, and `source_version`. Re-embedding (model change, chunking change) re-derives without re-ingesting canonical text; a new `source_version` re-derives from a fresh canonical load.

Chunking follows the provision, not the character count:

- **One document per provision**, at leaf granularity. The existing 1,500-character splitter is not used for this source.
- **Ancestor context is prepended to the embedded text** — chapter and section headings drawn from `path` — because a bare leaf ("(.a) Corner lots.") embeds meaninglessly without lineage. The prefix is part of the embedded content; the canonical text remains clean in `code_provision`.
- **Table nodes embed a linearised rendering**; the generation layer receives the structured JSON via the provision link, so rows are presented faithfully rather than re-parsed from prose.
- Degenerate leaves below a minimum useful length may be folded into their parent's document at derivation time; the rule, if adopted, is deterministic and recorded in the deriver, and the provision link always points at the most specific canonical node.

### 4. Retrieval: scoped by default, expanded by structure

- **Default scope for parcel-anchored questions is Title 14 only.** A `titles` filter is plumbed through the retrieval path from the start, so widening to Titles 4 (building/construction) and 19 (taxes/abatement) — the plausibly ICP-relevant neighbours — is a configuration decision gated on eval evidence, not an engineering change. Depth lives in storage; precision governs retrieval. 29,000 provisions competing unscoped in every query is how a deeper corpus produces worse answers.
- **Hybrid lookup replaces the district regex.** When a query names a cite or a district, exact-match retrieval against `code_provision` runs alongside vector search; the sniff in `fetch_district_documents` is retired.
- **Small-to-big expansion at answer time.** Vector hits match at leaf granularity; before generation, hits expand to their section window — ancestor chain plus siblings — so the model reasons over coherent legal units, not fragments.
- **Cross-reference expansion.** A retrieved provision's `refs` are one join away; the retrieval service may include first-degree references, bounded and attributed, enabling answers that follow the code's own structure.

### 5. Cutover is an eval decision, not a deploy

The `title14` (Quick Guide) and `phillycode` sources coexist; nothing about the schema prevents it. A golden question set — district dimensional standards, use permissions, overlay and master-plan cases, parking, and cross-reference questions — runs against both. The Quick Guide source is retired only when the new corpus matches or beats it on citation correctness and answer quality. This is the golden-equivalence discipline applied to a corpus swap: the incumbent corpus, whatever its provenance, is the behaviour users have.

### 6. First-slice validation: the parking cross-check

`zoning/parking.py` holds 24 machine-read constants no human has verified (handoff 0040 §4). The parser's structured table nodes for Chapter 14-802 are an **independent extraction of the same pages by a different pipeline**. Slice 1 compares the two and records the result as a validation artifact. Agreement between independent machine reads is not human verification, but it is materially stronger evidence than one read — and disagreement, if found, is a defect caught before a user underwrites against it.

## Deviations recorded during Slice 1 recon

Measured against the real artifacts in `backend/data/phillycode/` before any code was written. The decision above survives all of them; these are corrections of detail.

- **`title_number` is not a field on provision records.** It is derived from `qa_title_N.json.title_number`, cross-checked against `path[0]` on every record, and the title fails loudly on disagreement. It is typed as a **string**, not an integer — the domain includes `4.1` and `4.2`.
- **The `order` field is stored as `ordinal`.** `order` is a SQL reserved word, and this repository hand-writes a great deal of SQL.
- **The standalone `kind` index is dropped.** Seven distinct values over 29,297 rows will not be used by the planner.
- **The primary key is `(market_code, id)`, not `id` alone.** The parser's `id` is unique within one run's output, not across markets. The `parent` index is correspondingly `(market_code, parent)`.
- **67 cites repeat in the source, not 68**, and 86 rows carry `~N` id suffixes because one cite repeats up to five times.
- **`source_file` reads `philadelphiahomerulecharter.pdf` on every Code provision**, because the city publishes the Charter and the Code as a single PDF (provisions span pages 113–1318 of 1,318; `doc` is `code` on all 29,297 records and `charter` on none). The value is stored verbatim — upstream provenance is never rewritten — and this note exists so it is not later misread as a mis-load.
- **Title 9's exclusion costs 7,226 provisions, 24.7% of the corpus**, caused by a single gate-1 TOC failure: 518 sections emitted against 519 listed, missing §9-3010. Gates 2 and 3 pass. The fix belongs to phillyruleparser and is that project's highest-leverage open item.
- **Titles 5, 8, 4.1 and 4.2 are repealed stubs** holding two records each — a title root and an orphan history node. They pass the gates and load harmlessly.

### Addendum, 2026-08-08 — Title 9 admitted under an evidenced exception

Title 9 was excluded at Slice 1 because its QA gate 1 failed, and the deviation above records that as costing 7,226 provisions. The cause has since been established from the source itself and the title now loads.

**§ 9-3010 does not exist in current Philadelphia law.** Bill No. 210740-A (approved July 27, 2022) deleted the former § 9-3007 and renumbered the sections after it; footnotes 1247, 1248 and 1249 on page 493 record the deletion and both renumberings, and the body prints the post-2022 numbering. Title 9's own table of contents, on page 328, was never regenerated and still lists the pre-2022 sequence ending at a § 9-3010 with no body. The deleted section's caption appears exactly once in Title 9 — in that table of contents — and nowhere in the body.

The parser was correct and the gate was correctly reporting that the two sets differ. phillyruleparser now carries a conditional, evidence-carrying exception record: an entry excuses a cite only while the table of contents still lists it **and** the body still lacks it, and fails the gate as *stale* the moment either stops being true. The exception is therefore a re-checked claim about the source, not a suppression. It surfaces in `qa_title_9.json` as an `exceptions_applied` block, which this repository's loader parses and reports on the title's load line.

The corpus history reads honestly as a result: excluded at Slice 1 for a stale source table of contents, admitted once a mechanism existed to record *why* — not by lowering the gate. Corpus total is now **29,297 provisions across 24 titles**, and the deviation above stands as the record of the interim state.

## Consequences

- The assistant's zoning answers can cite the code itself, at provision granularity, with page-level provenance and a stated `source_version` — a claim no incumbent land-intelligence product makes for Philadelphia.
- A new module owns `code_provision` and its loader/deriver; `ai/` consumes it through a service interface. The `document` table gains no schema changes — only a new source and richer metadata.
- Corpus updates become a pipeline: new PDF → parser run → QA gates → artifact copy → canonical load → derivation → eval. Each stage is idempotent and independently re-runnable.
- Title 9 is visibly absent until the parser passes it. Questions touching it are answered as out of corpus — honest degradation over silent gaps.
- Embedding volume rises from a few hundred chunks to tens of thousands of provisions. Voyage cost is negligible; HNSW index build time and table size are the practical considerations and are well within Postgres comfort at this scale.
- The Quick Guide corpus remains authoritative until the eval says otherwise. Two grounding sources exist in the interim; the assistant's source attribution disambiguates them.

### Addendum, 2026-08-08 — first retrieval measurement, and why §5's caution was right

Title 14 is derived: **4,096 documents from 5,935 provisions**, 83 table nodes embedded, reconciliation exact. Corpus total 4,389 documents across Titles 1, 13 and 14.

**The partial per-source HNSW indexes work.** With 4,389 `phillycode` rows sitting beside 39 `title14` rows, the incumbent corpus's top-5 for three fixed queries is **byte-identical** to the pre-derivation baseline. Without them, a `source`-filtered search over one global graph would have degraded silently.

**Vector-only retrieval over the new corpus is currently worse than the incumbent**, and the numbers say so plainly. Rank of the provision that actually answers the question, out of 4,389:

| question | correct provision | rank |
|---|---|---|
| dimensional standards for RSA-5 | `14-401(1)(a)(.1)#table1` (Table 14-401-1) | **37** |
| maximum building height in CMX-3 | `14-701` Dimensional Standards | **12** |
| off-street parking for multi-family | `14-802` Motor Vehicle Parking Ratios | 2 |

Two of three fall outside any sane top-5 window. The incumbent Quick Guide corpus answers all three correctly at rank 1, because it holds one small hand-written document per district while the code holds the same facts in large tables.

**This is a retrieval problem, not a coverage problem** — 27 documents mention RSA-5 and 60 mention CMX-3, including the correct tables. Two causes, both structural:

1. **Linearised tables embed poorly against natural-language questions.** A 4,000-character wall of pipe-separated cells produces a vector about tables in general; no single district inside it is salient.
2. **Chapter 14-500 (overlay districts) crowds out the base districts.** It is large, and its prose repeats district names and dimensional language, so overlay provisions dominate the top of every dimensional query.

Consequences for the remaining slices, which this measurement makes concrete rather than theoretical:

- **§4's hybrid cite/district lookup is a prerequisite, not an enhancement.** Vector search alone does not put the answer in reach on this corpus.
- **§4's small-to-big expansion matters for the same reason** — a leaf that matches is not the unit that answers.
- **§5's discipline is vindicated.** Run today, the golden-equivalence eval would say keep the Quick Guide, and it would be right. Nothing about this corpus's depth entitles it to replace a corpus that answers the question.

### Slice 2 preconditions, established by Slice 1 recon

- ~~**The Table 14-802-3 caption orphan must be fixed upstream first, and it is larger than one table.**~~ **RESOLVED 2026-08-08** — fixed in phillyruleparser and the artifacts regenerated and re-copied. `ExtractedTable` now carries its fragment's column edges; continuation detection decides identity on geometry alone and re-lays the smaller fragment's cells onto the larger fragment's grid at merge time, because the larger fragment resolved more ruling lines. All four orphans merge with **uniform** grids — `14-802(4)(a)[1]#table1` 47 × 4, `F-105#table3` 52 × 3, `14-904(2)(a)(.4)#table1` 13 × 4, `14-904(2)(a)(.4)#table13` 14 × 4 — with zero cell text lost or gained. The parser gained a gate 5 (no orphaned page-break continuation, no table with mixed row widths) which is green on all 24 titles, so the property is enforced rather than merely achieved. **Table nodes are now safe for Slice 2b to embed.** The original text is struck rather than deleted so the corpus's history stays legible: `14-802(4)(a)[1]#table1` carries the caption and three header rows; its 44 data rows sit in `14-802(4)(a)[1]#table2` with `caption` and `continuation_of` both null. Investigated in phillyruleparser on 2026-08-08 (its `HANDOFF.md` §7): the root cause is that pdfplumber gave the 3-row header stub five column boundaries where the table has four, so the continuation detector's column-equality test failed — and there are **four** such orphans across Titles 4 and 14, not one. Merging them as-is yields *ragged* tables (3 rows × 5 then 44 × 4), where the correctly-linked Table 14-802-2 yields a uniform 41 × 4. A five-column header band over four-column parking data would mis-associate districts with their ratios, so the fix belongs in the parser's extract stage and was deliberately not shipped as a quick predicate change. LotScope does not patch around upstream defects, and it does not consume a half-fixed one either.
- ~~**Table nodes embed a linearised rendering of the structured `rows` only, never `raw_text`.**~~ **IMPLEMENTED 2026-08-08 (Slice 2b).** `linearise_table` renders caption, header rows and body rows from `table_data`; `raw_text` is never read. Continuation stubs carry no rows and are skipped with a count, so the 169 table nodes yield **133 documents and 36 skipped continuations**. The structured JSON stays in `code_provision` for the generation layer to read through `doc_metadata.provision_id`.
- **Cross-reference expansion is targeted, not broad.** `refs` is populated on 1,444 of 29,297 rows — 4.93%.

## Non-goals

- **No dossier code-browser UI.** Deterministic cite lookup enables a "view the code section" affordance; it is ledgered, not built, and waits for ICP pull per the feature-ledger rule.
- **No Charter.** The parser has no Charter profile; `doc = charter` remains reserved.
- **No non-Philadelphia codes.** The `market_code` column exists for shape, not as a commitment. Harrisburg/Pittsburgh/Wilmington grounding is unchanged by this ADR.
- **No cross-title product features.** Title 19 abatement intelligence tied to distress, Title 4 buildability enrichment, and similar are explicitly out of scope; they are candidate features that require their own justification.
- **No change to `zoning_standard` or the verdict contract.** The canonical corpus may *check* seeded values (§6); it does not replace them. Any future decision to derive standards from parsed tables is its own ADR.
- **No LLM-facing changes to the citation contract.** The enforcement mechanism in `ai/service.py` is unchanged; only what it cites improves.