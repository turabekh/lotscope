# 46. Outreach tier — direct-mail letter generation (first slice)

Date: 2026-07-04

## Status

Accepted

Opens the **Growth / outreach** tier (PRD §5.7). The wholesaler persona already gets the lead engine (distress index, deal signal), contactability (skip-trace, ADR-era A1), and raw egress (CSV export, A3). What's missing is the *doing* of outreach. This ADR starts that tier with the lowest-risk, highest-use piece and defines the boundary the rest of the tier will grow into.

## Context

A land wholesaler's core loop is: pull a distressed-owner list → mail every owner a personalized "I want to buy your lot" letter → field responses. We already produce the list and the mailing addresses (`parcel.owner`, `parcel.mailing_address`); the CSV export hands them a spreadsheet. But the actual artifact they pay PropStream/BatchLeads to avoid assembling by hand is the **print-ready, personalized letter set** — a mail merge. Today they'd have to take our CSV into Word themselves.

The compliance surface (§13) splits sharply by channel:
- **Physical direct mail** to property owners is standard and legal; it is **not** TCPA/DNC (those govern calls/texts) and not CAN-SPAM (email). Fair Housing still applies to *how a list is targeted* — but our filters are property-signal-based (distress score, vacancy, tax status, ZIP), never protected-class attributes, so a distress list is compliant by construction.
- **SMS/email sequences and autodialing** carry live-sending obligations (TCPA/DNC scrubbing, CAN-SPAM headers/opt-out, consent). Those are real and are **deferred** — this slice never sends anything; it renders a document the user prints and mails themselves.

That split is the decision: **ship the document-generation half of outreach now (no live sending), and gate the sending half behind its own future ADR when the compliance rails exist.**

## Decision

**Add a `POST /outreach/letters` endpoint that renders a print-ready PDF of personalized purchase-interest letters for a distress lead list — one letter per property, merged from the owner/mailing-address/property-address we already store.**

- **New `outreach` module** (`schemas`, `service`, `tests`) — the tier's permanent home; slice 1 is letter campaigns, later slices add sequences/tracking. It **composes** existing services, owning no domain truth: `distress.service` selects recipients, `reports.mailer` renders. New `distress.service.list_mail_recipients(...)` returns structured `{parcel_number, property_address, owner, mailing_address}` for leads **that have a mailing address** (unmailable rows are dropped), reusing the exact lead filters (`min_score`, `vacant_only`, `zip_code`) as `/leads` and `/leads/export` so the letter set matches the list the user is looking at.
- **Renderer in `reports/mailer.py`** (beside `dossier.py`/`appeal_packet.py`, reusing their FPDF helpers): one letter per page — sender block, date, owner + mailing address, a merged body (`{owner}`, `{property_address}`, `{parcel_number}` placeholders) with a sensible default template the user can override, signature, and a standardized compliance footer.
- **Request** (`MailMergeRequest`): `from_name`, `from_contact` (return/signature block, required — a letter needs a real sender), optional `message` template, and the lead filters. Validated via Pydantic; the body length and placeholder set are bounded.
- **Gating & metering:** outreach is a **paid** feature. Letter generation is workflow egress, so it reuses the export rails — `_reserve_export` (monthly quota) and `export_row_limit(tier)` caps the recipient count — rather than inventing a parallel quota. Free tier is blocked with the existing upgrade message.
- **Compliance (§13):** every letter carries the footer — informational, sender-responsible, Fair-Housing/direct-mail reminder — and the endpoint targets only by property signals. No owner PII is logged; the PDF streams and is not persisted server-side.

## Consequences

- **A real outreach deliverable ships without any live-sending risk.** The user gets the artifact that converts a list into mail; we take on zero TCPA/CAN-SPAM sending liability because we don't send.
- **The module boundary is set correctly on day one:** `outreach` composes `distress` + `reports` through service interfaces and holds the tier's future (sequences, DNC scrub, response tracking) without those being built speculatively now.
- **Reuses export metering**, so billing/quotas stay coherent (one egress budget) instead of a second, divergent counter. If outreach later needs its own economics, that's a deliberate follow-up.
- **Test-first:** recipient selection (filters, mailing-address-required, cap), template merge (placeholder substitution, default vs. custom, escaping), a valid-PDF render, and the tier/quota gate matrix. Owner PII handling is asserted (not logged).
- **Per-owner dedup (added):** a `one_per_owner` request flag (default on) collapses an owner (matched case-insensitively on owner + mailing address) to a single letter referencing their top-distress property, so an owner holding many parcels isn't mailed repeatedly. Off restores one-letter-per-property.
- **Watchlist source (added):** `POST /outreach/letters/watchlist` mails the user's saved parcels instead of the distress filter, so wholesalers can work a curated list. `watchlist.service.list_mail_recipients` selects recipients (mailing-address-required, dedup, ordered by opportunity score so dedup keeps the best parcel); `outreach.service` shares one `_render` path across both sources via a `LetterFields` base schema. Surfaced as "Mail letters" on the saved-lots list.
- **Deferred:** SMS/email sequences and any live sending (own ADR + compliance rails), response/skip-trace enrichment inside the letter, and campaign persistence/tracking.
