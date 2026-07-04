# 47. Outreach sending — email campaigns (bring-your-own-provider)

Date: 2026-07-04

## Status

Proposed

The next step in the outreach tier (PRD §5.7) after direct-mail letters (ADR-0046). ADR-0046 deliberately stopped at *document generation* — the user prints and mails the PDF themselves — precisely to avoid the liability of live sending. This ADR scopes the first live-sending capability and, just as importantly, draws the line around what stays deferred.

## Context

Letters (ADR-0046) carry near-zero sending liability because LotScope never transmits anything: it renders a PDF the user mails. Email and SMS are categorically different — a system that *sends* enters the compliance chain (CAN-SPAM for email, TCPA/DNC for SMS, Fair Housing for targeting) and, if it sends from its own infrastructure, also stakes its **deliverability reputation** on every user's list quality. One careless blaster can torch shared sending reputation for everyone.

Two architectural models:

1. **LotScope-as-sender (managed):** LotScope owns the ESP/SMS accounts and sends on users' behalf. Turnkey, but LotScope becomes sender-of-record, absorbs TCPA/CAN-SPAM exposure, shares one reputation pool across all tenants, and must itself hold SMS 10DLC registration.
2. **Bring-your-own-provider (BYO):** the user connects their own ESP (e.g. Postmark/SendGrid/Mailgun) via API key; LotScope orchestrates — builds the list, personalizes, injects compliance, schedules — and calls the *user's* provider. The user is sender-of-record with their own domain/DKIM, reputation, and compliance posture. This mirrors the existing **skip-trace BYO-provider adapter** (`SkipTraceProvider` Protocol + `Null` impl + settings-gated factory that returns `None` when unconfigured).

The channels also split sharply by risk:

- **Email / CAN-SPAM (tractable):** cold email to US property owners is permissible without prior consent, provided accurate headers, a real physical postal address, a functional opt-out honored within 10 days, and non-deceptive subjects. This is enforceable in software.
- **SMS / TCPA (minefield):** marketing texts to wireless numbers generally require prior express written consent; the National DNC Registry, 10DLC brand+campaign registration, STOP/HELP handling, 8am–9pm-local quiet hours, and state mini-TCPA statutes (FL/OK/WA) all apply. Cold-texting owners is common among wholesalers but carries class-action exposure that one-click blasting would amplify.

Email/SMS also *need contact info* (addresses/phones) that letters don't — those come from **skip-trace** (ADR-A1), so sending is gated on a recipient having traced contacts, not merely a mailing address.

## Decision

**Ship email-only, bring-your-own-provider, single-send first; make LotScope the orchestrator and the user the sender-of-record; enforce suppression + CAN-SPAM in software; defer SMS and drip sequences.**

- **BYO email provider.** A settings/credentials-gated `EmailProvider` adapter (Protocol + `Null` impl + factory), exactly like `SkipTraceProvider`. The user stores their own ESP API key (encrypted at rest, never logged, §13) and a verified sender identity (from-domain with DKIM). Dormant until configured.
- **LotScope orchestrates, does not originate.** It reuses the ADR-0046 recipient selection (the three `list_mail_recipients` sources) and `merge_message`, resolves each recipient's **skip-traced email**, injects the CAN-SPAM apparatus, and hands the send to the user's provider. LotScope never sends from its own domain on a user's behalf.
- **Mandatory compliance apparatus, enforced not optional:**
  - A per-account **suppression list** (`outreach_suppression`: email, reason, created_at) covering unsubscribes, hard bounces, and spam complaints (fed by provider webhooks) plus manual DNC. Checked before **every** send; a suppressed address is never contacted again.
  - Every email carries a **one-click unsubscribe** (List-Unsubscribe header + link) whose opt-out is honored immediately (well under the 10-day rule), the sender's **physical postal address** (collected once, attested), and a non-deceptive subject.
  - **Targeting stays property-signal-based** (distress/vacancy/tax/ZIP), never protected classes (Fair Housing) — unchanged from ADR-0046.
- **Sending runs async** through the existing ARQ worker (per-message rows in `outreach_message` with status: queued/sent/delivered/bounced/opted_out), so a large campaign is throttled and restartable, and provider webhooks reconcile delivery + opt-out back to status + suppression.
- **Gated + metered** like the rest of the tier (paid; reuse the export/credit rails as the send budget rather than inventing a parallel counter).
- **One-time attestation** before the first send: the user confirms they will comply, supplies their CAN-SPAM postal address, and confirms their verified sender domain. Recorded with provenance.

## Consequences

- **A real send capability without LotScope becoming sender-of-record.** Liability, deliverability, reputation, and (later) 10DLC registration sit with the user's own provider account — LotScope is tooling, consistent with its informational-only posture (§13) and the skip-trace precedent.
- **New module + model surface (when built):** an `outreach` extension with `outreach_campaign` / `outreach_message` / `outreach_suppression` tables (Alembic migration), an `EmailProvider` adapter, provider webhooks, and ARQ send jobs. Owner PII (emails) is sensitive — encrypted, never logged, minimized retention (§13).
- **Coupled to skip-trace:** a recipient is emailable only if it has a traced email, so send campaigns surface "N of M recipients have an email" and the rest fall back to the letters path.
- **Test-first, per §12:** suppression is checked before send (unit); unsubscribe/bounce webhooks suppress (integration); CAN-SPAM apparatus present on every message; provider adapter mocked (`Null` provider for tests); merge/targeting reuse ADR-0046 coverage. No live provider in tests.
- **Explicitly deferred to their own ADRs / slices:**
  - **SMS entirely** — TCPA consent model, DNC scrubbing, 10DLC registration, STOP/HELP, quiet hours. Its own ADR before any code.
  - **Multi-step drip sequences** (day-offset steps, stop-on-reply) — slice 2 after single-send email is proven; scheduled via ARQ.
  - **Reply/inbound handling and a CRM/inbox** — out of scope (the amendment's non-goals bar CRM/dialer functionality).
  - **Non-US recipients** (CASL/GDPR consent regimes) — the model assumes US/Philadelphia owners; flag if that assumption ever breaks.
- **If BYO friction proves too high**, a managed-sending option could be revisited later — but only behind per-tenant subdomains/IPs and its own reputation controls, as a deliberate, separate decision.
