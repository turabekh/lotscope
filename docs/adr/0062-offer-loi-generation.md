# 62. Offer / Letter-of-Intent generation

Date: 2026-07-12

## Status

Proposed

Delivers deal-closing batch feature **F2** — one click from a pipeline deal to a print-ready, non-binding LOI at
the verdict MAO with a cited comp-evidence appendix. Pulls forward the **deterministic core** of Amendment-01
CW-3 **without any AI dependency**. Depends on ADR-0021 (fpdf2 dossier scaffold), ADR-0046 (letter rendering),
ADR-0049 (comp exclusions rendered into the appendix). Tier-gated Pro+ per ADR-0030.

## Context

The flipper loop is find → contact → **offer** → exit. We compute the Maximum Allowable Offer on every verdict
but give the user no way to act on it. CW-3 in Amendment 01 imagines an AI-drafted negotiation letter; the
**deterministic 80%** — a correctly-populated, non-binding LOI at the stored MAO with the comp evidence that
justifies the number — needs no model and can ship now, honestly and cheaply.

Recon confirms the pieces exist:

- **Renderer scaffold is reusable.** `reports/dossier.py` exposes a shared `_Dossier(FPDF)` base + helpers
  (`_s` Latin-1 sanitizer, `_section`, `_kv`, `_tag`, `_money`, `_num`, brand colors); `reports/appeal_packet.py`
  already imports the whole scaffold and has a `_comp_table(...)` that renders the comp evidence rows. Endpoints
  return `Response(content=pdf, media_type="application/pdf", ...)`.
- **Economics are stored.** `parcel_verdict` persists `max_allowable_offer`, `arv`, `est_profit`, `est_margin`;
  `pipeline.service.get_deal()` already returns them for a deal.
- **Comps carry their exclusions.** `find_comps` returns `CompResult{address, sale_date, sale_price,
  distance_ft, price_per_sqft}` plus corpus-level `reasons` (related-party count) and
  `sources[0].package_deeds_excluded` — the transparency the appendix should inherit verbatim.
- **`deal_activity`** (`kind String(20)`) is the natural persistence home; `"offer_generated"` fits.
- **`app_user` is autogenerate-managed** — signer-profile fields are a clean additive migration; `deal`/
  `deal_activity` are **not** autogenerate-managed (hand-write any migration there — established gotcha).

## Decision

**Generate the LOI as a deterministic pure function → document model → fpdf2 render on the existing scaffold,
triggered per pipeline deal, Pro+-gated, persisted as a `deal_activity` entry. No AI, no new offer table.**

### 1. Scope — deterministic only

Explicitly **not** CW-3's AI drafting. The LOI is a fixed, non-binding template populated from verdict
economics, parcel facts, offer terms, and comps. No free-form generated prose in a code path.

### 2. Renderer + orchestration (boundary-clean)

`render_loi_pdf(...)` in `reports/` importing the `reports/dossier.py` scaffold (as `appeal_packet.py` does) and
reusing its comp table for the appendix; the orchestrator `build_loi(...)` lives in `pipeline/service.py` (an LOI
is per-deal) and reads economics via `pipeline.service.get_deal` + comps via `valuation.service`. Content:

- non-binding LOI body (informational / not-legal-advice / verify-before-relying disclaimer block, always present);
- property identification — address + **canonical key** and local-key display (ADR-0051/0052);
- offer terms — price + cash/as-is toggle, EMD, close-in days, inspection days, expiration date, each a **named
  constant default**;
- signer block from the D5 profile fields, per-generation overridable;
- **comp-evidence appendix** — the `find_comps` set (address, sale date, recorded price, distance,
  `price_per_sqft`) with the existing exclusion notes (related-party count, package-deeds-excluded) rendered
  **verbatim**, so the appendix inherits valuation transparency.

### 3. Endpoint + tier gate

`POST /pipeline/{parcel}/offer` (Pro+ via `FEED_TIERS` → new `offer_generation_access`); request = offer price
(defaults to stored `max_allowable_offer`, override allowed), terms, signer block; response = the streamed PDF
(the dossier `Response(...)` pattern). Gate over-limit through the existing 429/`QuotaExceededError` machinery.

### 4. Missing-economics honest state

No stored verdict, or a null/negative `max_allowable_offer` → **409** with a typed error the frontend maps to
"compute the verdict first, or enter a manual price." The manual-price path renders the LOI **without** the
MAO-derived framing and stamps a **"user-supplied price"** provenance line — never a fabricated MAO.

### 5. Persistence (D3 — no new table)

Write a `deal_activity` entry `kind="offer_generated"` whose `body` carries the full parameter payload (price,
terms, signer, and a **comp-set fingerprint** — a hash of the comp `document_id`s + `computed_at`) as the
provenance record. If the parcel isn't yet in the user's pipeline, add it at the default stage first (smallest
coherent behavior). If offer history later needs to be a first-class surface, a dedicated table is the follow-up.

### 6. Signer profile (D5 — additive `app_user` migration)

Add nullable `entity_name, signer_name, signer_phone, signer_email` to `app_user` (autogenerate-managed,
additive), captured in Settings, defaulted onto every LOI and per-generation overridable.

## Consequences

- **The offer step of the loop ships without AI** — deterministic, testable, cheap, and honest; CW-3's model
  layer becomes a later enhancement, not a blocker.
- **The appendix makes the MAO defensible** — the buyer sees the same comps and exclusions the number came from,
  extending our valuation-transparency stance to the negotiation artifact.
- **No fabricated numbers** — the 409 two-path state means a parcel without economics never yields a made-up MAO.
- **Two migrations:** additive `app_user` signer fields (autogenerate); **no** `deal`/`deal_activity` schema
  change (we reuse `kind`/`body`), so the hand-written-migration gotcha is avoided entirely.
- **Legal framing (§13):** the LOI is explicitly non-binding and informational; the disclaimer block is always
  rendered. This is a document generator, not legal advice.
- **`VERDICT_VERSION` unaffected** (reads stored economics; no scoring touch).
- **Deferred:** AI-drafted language (CW-3 proper); offer-history as a first-class surface; sending/delivery.
