# 17. Watchlist change-alerts

Date: 2026-06-28

## Status

Accepted

## Context

PRD §5.16 lists **watchlist change-alerts** (Differentiator) — tell a user when a saved lot materially changes (tax, L&I, price, status). Watchlists (ADR-0016) gave us the saved set; the question is how to detect "what changed since the user last looked" without standing up an email/push pipeline yet.

## Decision

**Snapshot-on-save, diff-on-read, acknowledge-to-clear — an in-app alert with no background job.**

- When a parcel is saved, store a `snapshot` (JSONB) of its comparable state on `saved_parcel`: vacancy, assessment value, tax (delinquent / amount owed / sheriff sale), L&I (violation count, unsafe flag), opportunity score, and the precomputed distress score.
- On every watchlist read, recompute the parcel's current state from the live tables and **diff it against the snapshot** with a pure, tested `compute_changes(snapshot, current)`. It emits typed changes with severity (e.g. "Now flagged for sheriff sale" = high, "Tax owed +$5,000" = medium, "Opportunity 60 → 72" = info). Decreases in distress are intentionally not flagged.
- `POST /watchlist/{id}/seen` **re-snapshots** the current state, clearing that item's alerts. The list response carries an `alerts` count (items with changes); the UI badges the avatar/menu and shows per-item change chips with a "Mark seen" action.
- Re-saving an already-saved parcel does **not** reset the snapshot (only an explicit "seen" does), so alerts survive a re-save.

## Consequences

- **No notification infrastructure required.** Alerts are computed at read time against the user's small saved set (correlated L&I subqueries, ≤ the tier cap of rows) — cheap and always fresh against current data (which the daily ingestion/recompute jobs move).
- **In-app only.** Email / SMS / push digests (§5.16) are a deferred follow-up; this provides the change-detection core they would reuse. A future job could fan these same diffs out to email.
- The snapshot is a point-in-time baseline, not a full history; we surface *that something changed*, not a timeline. A per-parcel change log is a separate feature.
- The diff logic is the single source of truth for "what counts as an alert," unit-tested independently of the DB.
