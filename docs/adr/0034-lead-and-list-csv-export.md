# 34. Lead & list CSV export

Date: 2026-07-03

## Status

Accepted

Gates PRD-amendment-01 feature **A3** (Phase 1). Extends ADR-0010/0030 (tiers/billing), ADR-0015 (leads), ADR-0024 (saved searches), ADR-0021 (reports/output).

## Context

Wholesalers live in dialers and mail-merge tools; CSV export is the egress that justifies the $99+ tiers (amendment §3 A3). Two result sets need export: the **leads** list (`GET /leads`, ranked by distress) and a **saved search**'s matches (ADR-0024). Both already have server-side selection — `distress.service.find_leads` (via `_LEADS_SQL`) and `savedsearch.matching.build_where` + `build_match_sql`. Neither currently emits `parcel.mailing_address`, which is the point of an export (mail-merge). The tier gates for export exist in the amendment §2.2 but not in `accounts/tiers.py`: **Free 0 exports; Pro 10 exports/mo · 2,000 rows each; Investor ∞ exports · 10,000 rows each**.

Usage metering already exists as a Redis pattern (`accounts/usage.py`: `usage:ask:{uid}:{day}` daily keys with TTL; parcel-view sets). Export counts are **monthly**, so this is the same pattern at month granularity. The reports module (ADR-0021) already owns output-artifact generation (PDF); CSV is the same role.

## Decision

**Two streaming CSV endpoints gated by monthly export-count and per-file row caps, reusing each module's existing selection, serialized by a pure CSV writer in `reports`, with a compliance footer on every file.**

- **Endpoints (thin routers):**
  - `GET /leads/export` — same query params as `GET /leads` (`min_score`, `vacant_only`, `zip_code`).
  - `GET /saved-searches/{id}/export` — the owned search's current matches.
  Both return `text/csv` as a `StreamingResponse` with `Content-Disposition: attachment; filename=...`.

- **Selection reuses existing logic, extended to carry `mailing_address`:**
  - Leads: a `distress.service` export query mirroring `_LEADS_SQL`'s filter/order but selecting the export columns incl. `p.mailing_address`, bounded by the tier **row cap** (not the display `lead_list_limit`).
  - Saved search: `build_where(criteria)` + a `MATCH_SELECT` that adds `p.mailing_address`, bounded by the row cap. (Saved-search matches are stored capped at `MAX_MATCHES_PER_SEARCH`; export selects live against criteria so it is not limited to stored rows — but still capped by the tier row cap.)

- **Tier gates (new maps in `accounts/tiers.py`):**
  - `EXPORT_MONTHLY_LIMITS`: `free=0, pro=10, investor=None, enterprise=None`.
  - `EXPORT_ROW_LIMITS`: `free=0, pro=2000, investor=10000, enterprise=10000`.
  Both keep the `_DEFAULT_TIER` fail-safe. Free (limit 0) → the endpoint returns a typed
  `AuthorizationError`/402-style "upgrade to export" error, never a partial file.

- **Metering (Redis, month-granular):** `accounts/usage.py` gains `export_usage_key(uid, month)` = `usage:export:{uid}:{YYYY-MM}` and a `reserve_export(redis, uid, monthly_limit) -> bool` that (a) returns `False` immediately when the limit is 0 or the current count ≥ limit, else (b) `INCR`s (setting a ~40-day TTL on first write) and returns `True`. Reservation happens **before** streaming so a mid-stream disconnect still counts one export (at-most-the-cap, never over). Unlimited tiers (`None`) skip the count entirely.

- **CSV writer is pure and in `reports`:** `reports.csv_export.stream_rows(header, rows, footer_lines) -> Iterator[str]` yields RFC-4180 lines via the stdlib `csv` module. Testable without HTTP. The API wraps it in `StreamingResponse`.

- **Compliance footer on every file (§13):** trailing rows — informational-only + a Fair Housing / TCPA / CAN-SPAM / DNC reminder — mirroring the existing Leads-page disclaimer. This is the same non-advice framing the product uses everywhere.

- **Skip-trace columns are deferred to A1:** the amendment wants traced phones/emails in exports "where the user already traced that owner." Skip-trace (ADR pending, A1) isn't built, so v1 exports owner + mailing address only. The CSV header is shaped so A1 can append phone/email columns without breaking consumers.

- **Frontend:** an Export button on the Leads page and the expanded Saved-search view; for Free (or when the monthly cap is hit) it renders an upgrade prompt instead of downloading. The button hits the endpoint with the current filters and lets the browser download the stream.

## Consequences

- The egress that justifies paid tiers ships without new data: it reuses `find_leads`/`build_where` and only adds a `mailing_address` column + caps. Investor's higher row cap (10k vs 2k) is a concrete upgrade lever, alongside the count cap.
- Row cap is enforced in SQL (`LIMIT`), so a huge saved search exports the top-N by the existing order (opportunity score) — the file states it is capped in the footer, not silently truncated (§ no-silent-caps).
- Metering is eventually-consistent and best-effort like the ask/parcel-view counters: a Redis outage suppresses counting (fail-open on metering, but the tier check still blocks Free), consistent with how ask-usage degrades. Money-adjacent state is not involved (unlike A1 credits, which use a durable ledger).
- Reservation-before-stream can over-count by at most zero and under-deliver by one on a mid-stream failure (counted but not downloaded); acceptable for a generous monthly cap. No partial/short files are billed as "used" beyond that.
- Owner PII (mailing address, later skip-trace) leaves the system in these files: the compliance footer, the informational framing, and the paid-tier gate are the controls (§13). The endpoints are auth-only and per-user metered; PII is never logged.
- **Deferred:** true saved-search match-count vs the storage cap (a separate pre-existing follow-up); skip-trace columns (A1); async/background export for very large files (v1 streams synchronously within the row cap, which bounds file size).
