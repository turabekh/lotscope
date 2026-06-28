# 18. Email digest alerts

Date: 2026-06-28

## Status

Accepted

## Context

ADR-0017 gave in-app watchlist change-alerts. PRD §5.16 also wants **digest emails / push** so users hear about changes without opening the app. Email is an external-service + compliance decision (CAN-SPAM, §13), so it is ADR-gated and must stay dormant until configured.

## Decision

**SMTP-based, vendor-agnostic email digests, dormant without config; web-push deferred.**

- **Transport:** stdlib `smtplib` (run in a thread from the async worker) — no new dependency, works with any provider's SMTP (SES, SendGrid, Postmark, Mailgun, …). `get_email_sender(settings)` returns `None` when `SMTP_HOST` is unset, so the digest job logs-and-skips; nothing sends until configured.
- **Default:** new and existing users default to a **weekly** digest (`app_user.digest_frequency`, values `off`/`weekly`/`daily`) — opt-out, because the digest is relationship-based (it covers lots the user chose to save). A per-user `PATCH /auth/digest` and one-click unsubscribe make opting out trivial.
- **Compliance (§13):** every email carries a one-click **unsubscribe** link (a signed JWT with `purpose=digest_unsubscribe`, verified at a public `GET /digests/unsubscribe` — no stored token) and a configurable **postal address**. Content is framed informational, not advice.
- **Rendering is pure and tested** (`digest.py`): subject, HTML (inline styles for email clients, severity-colored change chips, escaped addresses, CTA + unsubscribe + address) and a plain-text alternative.
- **Scheduling:** ARQ crons — daily (`hour=13`) and weekly (`Mon 13:30`) — call `send_digests(frequency=…)`, which emails only users on that cadence who have watchlist alerts.
- **Sending acknowledges.** After a successful send, the digest **re-snapshots** the alerted parcels (same `acknowledge` as the in-app "mark seen"), so a change is emailed once rather than every cycle.

## Consequences

- **Sending clears in-app alerts too.** Because the email re-snapshots, a user who gets the digest then opens the app sees those alerts cleared — the email *is* the notification. Acceptable and simplest; separating "emailed" from "in-app seen" would need a second baseline.
- **At-least-once-ish, fail-isolated:** a send error for one user is logged and skipped without re-snapshotting (so it retries next cycle) and doesn't abort the batch.
- **Weekly opt-out default** is a deliberate, documented choice; the unsubscribe + account toggle are the controls.
- **Deferred:** web-push (service worker + VAPID + subscription storage is a separate slice), per-change email vs digest, send-time/timezone preferences, and HTML-template theming. Deliverability/SPF/DKIM is the configured provider's responsibility.
