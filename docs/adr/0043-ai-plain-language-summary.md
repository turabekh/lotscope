# 43. AI plain-language parcel summary

Date: 2026-07-04

## Status

Proposed

Delivers PRD §5.2 "AI plain-language summary" (Differentiator) — the last unbuilt Differentiator in the parcel dossier. Extends the `ai` module (ADR-0009-era Ask-the-Parcel) and reuses the structured-output client; independent of the monetization amendment.

## Context

The dossier already shows a one-line *verdict summary*, but it is **template-generated** ("RSA-5: buildable by-right (1 unit); 2 risk flags; MAO $95,000"). The PRD asks for a genuine **one-paragraph plain-English read** of the parcel — the kind of sentence an investor would say out loud: *"This is a vacant, tax-delinquent RSA-5 rowhouse lot that pencils as a by-right single, modeled ~15% below its assessment, with an open L&I violation as the main snag."* We have all the raw material — the verdict, risk flags, distress, assessment, comps — and the structured-generation plumbing from Ask-the-Parcel. What's missing is the synthesis.

The critical distinction from Ask-the-Parcel: that feature answers open zoning/legal questions and therefore **must** ground in the Title-14 RAG corpus and cite code sections (§9). The summary is different — it **restates the parcel's own already-computed, already-grounded intelligence** in prose. Its job is synthesis, not interpretation. That reframing drives every decision below: no RAG, no code citations, a cheaper model, and aggressive caching.

## Decision

**A `GET /parcels/{id}/summary` endpoint that feeds the parcel's computed intelligence to a cheaper LLM under a strict "only from these facts" prompt, returns a schema-validated one-paragraph summary with a confidence and provenance, and caches it per verdict version.**

### Grounding — computed facts, not the corpus

The prompt context is a formatted digest of what LotScope already computed: parcel basics (address, zoning, area, vacant/city-owned), the verdict (buildability, by-right units, value estimate, MAO, deal score, risk score + top flags), distress (score/tier/top factors), and assessment (over/under, gap, estimated savings). The system prompt restricts the model to **only** those facts and forbids introducing zoning, value, or legal claims not present. Because those facts are themselves grounded (the verdict/risk/assessment engines cite their sources), the summary inherits that grounding without touching the RAG corpus — satisfying §9's "never answer a zoning/value question from parametric memory" while staying a pure synthesis. No embedder, no vector search.

### Structured output & provenance

The LLM returns a validated `ParcelSummary { summary: str, confidence: high|medium|low, is_informational: True }` via the existing `StructuredGenerator` tool pattern; invalid output is rejected (§9). The service wraps it as `ParcelSummaryResult { parcel_number, summary, confidence, is_informational, sources, computed_at }` — provenance (which engines fed it) and a computed-at stamp per Golden Rule 6. Confidence reflects how complete the input facts were (e.g. a parcel with no verdict yet → low).

### Model tier & cost control

Per §9 (cheaper/faster model for summaries), a configurable `anthropic_summary_model` (default **Haiku 4.5**, `claude-haiku-4-5-20251001`) with a small `max_tokens` (~512), injected via a `get_summary_generator` dependency; `AnthropicGenerator` gains a model override. Summaries are **cached in Redis keyed by `summary:{parcel_number}:{verdict_version}`** and regenerate only when the verdict version changes — so a parcel is summarized at most once per verdict version, bounding AI spend to near-zero at steady state.

### Access, framing, dormancy

Informational-only framing is baked into the schema (`is_informational`) and surfaced in the UI (§9/§13). If `anthropic_api_key` is unset the endpoint returns 404 and the dossier panel hides — the feature is **dormant, never blocking**, like the other AI surfaces. Access/gating is the one open product decision (see below).

### Frontend

A compact "Snapshot" panel at the top of the parcel dossier renders the paragraph with a confidence chip and an "informational, not advice" note; it fetches `GET /parcels/{id}/summary` on parcel select and hides on 404.

### Rollout (slices, each tested + committed)

1. This ADR.
2. **Backend** — `ParcelSummary` schema + versioned `SUMMARY_SYSTEM_PROMPT`/`build_summary_prompt` (prompt-version `parcel-summary-v1`) + `summarize_parcel` service + `anthropic_summary_model` config + `get_summary_generator` dep + `GET /parcels/{id}/summary` with Redis caching. Tests: prompt includes the computed facts, schema validation/repair, cache hit path, dormancy when unconfigured (mock the generator; no live API in tests).
3. **Frontend** — dossier Snapshot panel + `api.getParcelSummary` + `ParcelSummaryResult` type.

## Consequences

- **The last dossier Differentiator ships** cheaply — no new domain logic, just synthesis of existing outputs on a proven AI rail.
- **Cost is bounded by design.** Per-verdict-version caching means a stable parcel is summarized once; a citywide verdict bump (e.g. v6) lazily re-summarizes only parcels that are actually viewed. Haiku keeps per-call cost minimal.
- **Grounding is honest.** The summary can only restate computed facts; it cannot invent a zoning or value claim, and it carries confidence + provenance. The risk is the model *rephrasing* a fact misleadingly — mitigated by the strict prompt and covered by an eval set (quality assessed by eval, never exact-string asserts, §12).
- **Dormant without an API key**, so it never blocks the dossier; and it degrades gracefully (low confidence, or hidden) when a parcel lacks a verdict.
- **Deferred:** cross-parcel/portfolio summaries, AI report-section drafting (§5.6 Growth), and multi-language output.
