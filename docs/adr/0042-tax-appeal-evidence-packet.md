# 42. Tax-appeal evidence packet

Date: 2026-07-04

## Status

Proposed

Gates PRD-amendment-01 feature **A5** (Phase 6) — the last amendment feature. Extends §5.10 (reports) and the owner-side revenue lines. Reuses the `assessment` engine, the fpdf2 renderer (ADR-0021), the Stripe one-time-checkout + webhook fulfillment (ADR-0030), the credit ledger (ADR-0035), and email (ADR-0018).

## Context

We already give away the expensive half of this feature for free: the `assessment` engine computes over-assessment status, the assessed-vs-market gap, and estimated annual tax savings at the Philadelphia 1.3998% rate, with real recorded comps behind the market estimate. What we don't yet do is **package that into a filable evidence document and sell it**. A5 is a transactional SKU — a **$79 one-time "Assessment Review Packet"** (homeowner on-ramp, any tier including Free), with **Investor getting one per month included**. The lead magnet ("am I over-assessed?") is already free in-product; A5 monetizes the moment a reassessment wave makes an over-assessed owner want to act.

Every dependency exists and is proven. The map:
- `assessment.analyze_parcel_assessment` → status/gap/`estimated_annual_tax_savings`; comps come from `valuation.value_parcel` (the `AssessmentResult` itself carries no comps, so the packet builder calls both).
- `reports/dossier.py::render_dossier_pdf` is the fpdf2 template (brand header, `_section`/`_kv`/badge helpers, Latin-1 sanitation, `bytes(pdf.output())`).
- Stripe one-time checkout already exists (`mode:"payment"`, credit-pack flow) and the webhook already fulfills one-time purchases (`credit_grant_from_checkout` → `grant_credits`).
- The credit ledger already **stubs `REASON_APPEAL_PACKET_GRANT`** (present, unused) — the intended home for the Investor monthly inclusion.

Three gaps must be filled, and two of them are genuine forks (see Decision): the credit ledger has a **single conflated balance** (`SUM(delta)` over all reasons), the `EmailSender` has **no attachment support**, and `credit_grant_from_checkout` only understands `metadata["credits"]`.

## Decision

**Build an Assessment Review Packet PDF, entitled either by a $79 one-time purchase (parcel in checkout metadata, fulfilled at the webhook) or by spending an Investor monthly packet-credit, delivered as an in-app download and (when SMTP is live) an emailed attachment.**

### Packet content & renderer

A new `render_appeal_packet_pdf` (in `reports/appeal_packet.py`) + `reports/service.py::build_appeal_packet(session, parcel_number) -> bytes | None`, reusing the dossier's fpdf2 helpers: assessed value vs modeled market estimate (low/high), the **comp table** (address, distance, sale date, price, $/sqft — from `value_parcel`), gap and savings math, confidence, appeal-process pointers (OPA First-Level Review / BRT deadlines as static reference text), sources, and the existing `ASSESSMENT_DISCLAIMER` ("informational, not tax or legal advice"; no outcome guarantees).

### Entitlement — packet credits in the ledger, reason-scoped

Reuse `credit_ledger` with packet-specific reasons (`appeal_packet_grant` +1, `appeal_packet_burn` −1) and add a **reason-scoped balance**, `appeal_packet_balance(user_id)` = `SUM(delta) WHERE reason IN (packet reasons)`. To keep the two credit currencies from contaminating each other, the existing skip-trace `credit_balance` is **scoped to skip-trace reasons** in the same change (it currently sums everything). This honors the pre-stubbed reason constant and keeps one ledger, one idempotency index, two independent balances.

- **Investor monthly inclusion:** clone `grant_investor_credits` → `grant_investor_appeal_packets` (grant 1, `reason=appeal_packet_grant`, `ref=<YYYY-MM>` for idempotency), on a monthly worker cron.
- **Redemption:** `POST /parcels/{id}/appeal-packet` checks `appeal_packet_balance ≥ 1`, burns 1 (`appeal_packet_burn`, `ref=parcel_number+month`), records an entitlement, generates + delivers. Insufficient balance → `QuotaExceededError` steering to purchase.

### Purchase — one-time checkout, webhook fulfillment

`POST /billing/appeal-packet/checkout {parcel_number}` opens a `mode:"payment"` session with `metadata={product:"appeal_packet", parcel_number}` against a new `stripe_price_appeal_packet` (config). The webhook gains an `appeal_packet_from_checkout(event)` parser (discriminating on `metadata.product`), tried alongside the existing credit-grant parser; on `checkout.session.completed` it records the entitlement for the buyer + parcel and delivers. Idempotent on the Stripe `payment_intent`/session id.

### Delivery — download now, email attachment when SMTP is live

An `appeal_packet` entitlement table (`id, user_id FK, parcel_number FK, source [purchase|grant], ref, created_at`) records who may download which parcel's packet. `GET /parcels/{id}/appeal-packet.pdf` returns the PDF (regenerated from current data) **only if the caller holds an entitlement**; otherwise 403. The PDF is **regenerated on download, not stored** — packets are deterministic from parcel data, so an entitlement row is enough and we avoid blob storage. `EmailSender.send` is extended with an optional attachment (`filename, content: bytes, mime`); `SmtpEmailSender` adds it via `EmailMessage.add_attachment`. Email delivery is best-effort and **dormant until SMTP is configured** (same posture as the feed digest) — the in-app download is the guaranteed path.

### Rollout (slices, each tested + committed)

1. This ADR.
2. **Renderer** — `render_appeal_packet_pdf` + `build_appeal_packet` (pure-ish; assert PDF magic bytes, comp rows, savings math present). Comps surfaced from `value_parcel`.
3. **Entitlement** — packet-scoped balances (+ scope skip-trace balance), `appeal_packet` table + migration, redemption endpoint, Investor monthly grant job + cron.
4. **Purchase & delivery** — checkout endpoint, webhook parser + fulfillment, `stripe_price_appeal_packet`, download endpoint, `EmailSender` attachment support.
5. **Frontend** — Assessment panel "Get the appeal packet" CTA: buy ($79 checkout) for Free/Pro, redeem (1/mo) for Investor, plus a download link once entitled.

## Consequences

- **The amendment completes.** A5 is the last feature; shipping it closes PRD-amendment-01. It monetizes an already-computed, already-free analysis with near-zero new domain logic.
- **The ledger now carries two currencies, cleanly separated.** Reason-scoping both balances is the correctness-critical change; it is small and directly tested (skip-trace balance unaffected by packet grants and vice-versa). This is the one place A5 could silently corrupt an existing feature, so it is the most-tested unit.
- **No PDF blobs.** Regenerate-on-download keeps storage flat and the packet current; the trade-off is that a packet bought today may reflect slightly newer comps if downloaded next month — acceptable and arguably better for an evidence document, and noted in-product via the generated-at stamp.
- **Email stays optional.** Attachment support lands, but delivery is dormant until SMTP; the download path is the guaranteed fulfillment, so a missing SMTP config never blocks a purchase.
- **Compliance holds.** Informational-only disclaimer, no outcome guarantee, homestead/LOOP/abatement caveats already in `ASSESSMENT_DISCLAIMER`; the packet is evidence a homeowner files themselves, not advice.
- **Deferred:** stored/immutable packet snapshots, bulk/portfolio packets, auto-filled OPA appeal forms, and any refund path beyond Stripe's own.
