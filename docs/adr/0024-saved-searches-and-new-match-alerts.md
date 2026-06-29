# 24. Saved searches and new-match alerts

Date: 2026-06-29

## Status

Accepted

## Context

PRD §5.1 lists **saved searches + alerts** and §5.16 lists **new-match alerts** (both Differentiator): a user saves filter criteria and is told when *new* lots start matching. Watchlists (ADR-0016/0017) cover saved *parcels* and change-detection on them, but not criteria-based discovery. We already have the delivery rails — the email digest (ADR-0018), web push (ADR-0019), and the tiered-limit pattern (lead lists, watchlists) — so the open questions are (a) the criteria contract, (b) how to detect "new" matches without a reliable per-parcel "became-matching-at" timestamp, and (c) where matching runs.

## Decision

**A `savedsearch` module that persists validated criteria, materializes matched parcels into a child table, and diffs against that table to find what is new — delivered through the existing notification rails.**

- **Criteria** are a validated Pydantic `SearchCriteria` (stored as JSONB on `saved_search`). v1 is deliberately restricted to columns already proven in existing read queries: `vacant_only`, `exclude_city_owned`, `zoning_codes`, `zip_code`, `min/max_market_value`, `min/max_lot_area_sqft`, `min_opportunity_score`, `min_distress_score`, `is_delinquent`, `in_sheriff_sale`. The WHERE builder (`matching.build_where`) is pure, fully parametrized (no string interpolation of user input — §7), and unit-tested.
- **Matched parcels are materialized** into `saved_search_match (saved_search_id, parcel_number, first_seen_at, notified)`. "New" = current query result minus rows already in this table — a pure `new_match_numbers` diff. This mirrors watchlist's snapshot-on-save baseline rather than relying on a parcel-level timestamp the city data does not give us.
- **Baseline on create/criteria-change:** running a match with `baseline=True` inserts current matches as `notified=True`, so the user sees results immediately and is *not* alerted for the pre-existing set. Editing criteria clears the match set and re-baselines.
- **Alerts:** a daily worker job (`send_saved_search_match_alerts`) re-runs each alerting user's searches, inserts genuinely new matches as `notified=False`, emails the batch via the existing `EmailSender`, then flips them to `notified=True`. The `is_new` flag the UI badges is exactly `not notified`.
- **Tiering:** `saved_search_limit(tier)` (free 1, pro 50, enterprise unlimited) gates creation, raising `QuotaExceededError` like the other limits. Matches per search are capped at `MAX_MATCHES_PER_SEARCH` to bound storage and the citywide scan.

## Consequences

- **Correct "new" semantics without upstream timestamps.** The match table is the durable baseline; diffing against it is deterministic and survives ingestion churn.
- **Reuses the moat's existing rails** — no new delivery infrastructure; the alert is an informational, unsubscribe-bearing email consistent with the digest (§13 framing).
- **Matching runs in the alert job and on explicit refresh, not on every read.** A `GET` returns the stored match set (cheap); `POST /saved-searches/{id}/run` forces a re-scan. This keeps the citywide query off the hot path.
- **v1 criteria are a subset of the PRD filter set.** Lot dimensions beyond area, by-right units, flood, council district, and neighborhood/RCO are deferred until their columns/joins are confirmed; the JSONB criteria column absorbs new fields without a migration.
- The verdict contract is untouched; this module only reads parcel/verdict/distress/tax state.
