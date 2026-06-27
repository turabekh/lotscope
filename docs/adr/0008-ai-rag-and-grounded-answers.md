# 8. AI layer: RAG, embeddings, and grounded answers

Date: 2026-06-27

## Status

Accepted

## Context

The "Ask the Parcel" feature answers plain-English questions about a parcel. Per `CLAUDE.md` §9 it must be grounded, cited, schema-validated, and confidence-scored — never answered from the model's parametric memory — and all model access must be centralized and mockable. Retrieval-augmented generation needs an embedding model, which Anthropic does not provide.

## Decision

**Embeddings: Voyage AI.** Anthropic's recommended embeddings partner. `VoyageEmbedder` calls the Voyage REST API behind an `Embedder` protocol; the model and key are configured in `Settings`. Adding Voyage is a new external dependency, recorded here.

**Vector store: pgvector.** A `document` table holds the RAG corpus (Title 14 sections, deeds, city rules) with a `vector(1024)` embedding and an HNSW cosine index. Embeddings are written and cosine-searched through safe raw SQL with explicit `::vector` casts, avoiding asyncpg codec registration. Retrieval supports a source filter and top-k.

**Generation: Claude via a centralized client.** `AnthropicGenerator` (behind a `StructuredGenerator` protocol) forces structured output through a tool whose `input_schema` is the Pydantic `ParcelAnswer` JSON schema; the tool-call input is validated back into `ParcelAnswer`. All model access lives in the `ai/` module.

**Grounding and citations are enforced in code, not trusted from the model.** `ask_the_parcel` retrieves the parcel facts (detail + stored verdict) and the top Title 14 documents, assembles them into a versioned prompt (`SYSTEM_PROMPT` + `build_user_prompt`), and instructs the model to answer only from that CONTEXT and cite sources. The returned answer is schema-validated; an answer with **no citations is rejected** (`UngroundedAnswerError`), and the informational framing (`is_informational=True`) is asserted by us, not the model. A `confidence` signal rides along.

**Testability.** The deterministic scaffolding — retrieval ordering/filtering, prompt assembly, schema validation, citation enforcement — is tested with fixtures and fake `Embedder`/`StructuredGenerator` implementations; no network in tests. The real Voyage/Anthropic adapters are thin and exercised only in production.

## Consequences

- Two external providers now: Anthropic (generation) and Voyage (embeddings); both keys are config, never committed.
- Answers are grounded, cited, validated, and confidence-scored; ungrounded or malformed answers are rejected rather than surfaced.
- **The RAG corpus is not yet populated** — production grounding requires ingesting real Title 14 section text (and later deeds/plats) into `document` with embeddings. This is a prerequisite data task; until then retrieval returns nothing and answers will correctly report insufficient context.
- Per-request construction of the Voyage/Anthropic clients in the API is a simplification; pooling/lifecycle management is a follow-up. Embedding/generation retries and answer repair-on-invalid are also follow-ups.
- The embedding dimension (1024) is fixed in the schema and must match the configured Voyage model; changing models is a migration.
