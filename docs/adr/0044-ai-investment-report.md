# 44. AI investment report (drafting)

Date: 2026-07-04

## Status

Accepted

Delivers PRD §5.6 "AI report drafting" (Differentiator). Extends the `ai` module (ADR-0009 Ask-the-Parcel, ADR-0043 plain-language summary) and reuses the structured-output client. Independent of the monetization amendment.

## Context

The dossier has two AI reads today: the one-line **template** verdict summary and the one-paragraph **AI Snapshot** (ADR-0043). Neither is a *document*. The PRD asks for a drafted **investment memo** — the multi-section narrative an analyst would hand a partner: overview, buildability, valuation/deal, risks, and a recommendation, each reasoning over the parcel's computed facts. We already compute every input (verdict with cited Title-14 sections, deal math, distress, assessment, comps, risk flags) and have the structured-generation plumbing; what's missing is the long-form synthesis.

The hard constraint (§9, §13): zoning/legal/value claims must be **grounded and cited**, never answered from parametric memory. The report must not re-derive law.

## Decision

**Add `draft_parcel_report` to the `ai` module: a stronger-model, structured, multi-section synthesis of the already-computed engines — grounded by construction because it only re-narrates conclusions that were themselves computed and cited.**

- **Grounds on computed FACTS, not memory.** The report is a *synthesis layer* over `verdict` (which already carries `can_build_by_right` + the cited Title-14 section from grounded zoning), `deal`, `distress`, `assessment`, and `risk_flags`. Those facts — including the verdict's cited sections — are assembled into the prompt; the model is instructed to write **only** from them and to attribute zoning claims to the cited section. It never performs new legal reasoning, so §9 grounding holds without a fresh retrieval pass.
- **Structured output, validated.** `ParcelReport` → `headline`, `sections: [{heading, body}]`, `recommendation`, `confidence` (high/medium/low reflecting FACT completeness), `is_informational: Literal[True]`. Validated into Pydantic; invalid output is a `GenerationError` (reject, per §9). The section headings are model-chosen from a prompted set to keep the memo consistent.
- **Stronger model, by task.** Uses the default `get_generator` (Sonnet) rather than the Snapshot's Haiku — multi-section reasoning is the case §9 reserves the stronger model for.
- **Provenance + framing.** `ParcelReportResult` records `sources` and `computed_at` (Golden Rule 6); every rendering carries the informational-not-advice disclaimer (§13).
- **Endpoint + cost control.** `GET /parcels/{parcel_number}/report` → `ParcelReportResult`, authenticated. Redis-cached keyed by `parcel_number + verdict_version` so a parcel's report is generated once per verdict revision and served free thereafter — the report is a pure function of the computed facts, so the cache is safe and invalidates naturally when the verdict changes.
- **Tested as scaffolding, not prose.** Tests assert the deterministic parts: facts assembly includes the verdict's cited section, the generator is called with the report system prompt + schema, a mocked structured return validates, sections/recommendation/confidence are populated, `is_informational` is true, and provenance is stamped. Answer *quality* is left to the eval set, never asserted as exact wording (§12).

## Consequences

- **A real deliverable emerges from data we already have** — no new ingestion, no new engine, one new AI service function + schema + prompt + endpoint. The moat (Philadelphia depth + reasoning layer) becomes tangible as a shareable memo.
- **Grounding is preserved cheaply.** Because the report only re-narrates already-cited conclusions, it needs no separate Title-14 retrieval; the cost and latency stay close to the Snapshot despite the longer output. The risk — the model embellishing beyond FACTS — is bounded by the "only from FACTS" instruction, the structured schema, and the confidence signal, and is the named eval-set target.
- **Cost is contained by the verdict-scoped cache**; the first view per verdict revision pays generation, the rest are free. Heavier per-call than the Snapshot (stronger model, longer output), so if usage warrants, credit- or tier-gating is the **named follow-up** — v1 ships authenticated + cached to keep the surface simple.
- **Deferred:** PDF rendering of the report (the `reports` module can later fold the drafted sections into `render_dossier_pdf`), a multi-parcel/portfolio report, and any monetization gate.
