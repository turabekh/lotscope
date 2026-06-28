# 16. Watchlists (saved parcels)

Date: 2026-06-28

## Status

Accepted

## Context

PRD §5.9 lists **Watchlists** ("save parcels with tags and notes") as **Core** — the only conspicuously un-built Core user-facing feature. Without a way to save lots, the product is a discovery tool with no retention surface, and the higher-value engagement features that depend on saved lots (watchlist change-alerts §5.16, deal pipeline §5.9) are blocked.

## Decision

**A new `watchlist` module owning a per-user `saved_parcel` table** — the first user-generated-content concern, establishing the pattern the pipeline/CRM features will extend.

- **Model:** `saved_parcel` with composite PK `(user_id, parcel_number)`, both FKs `ON DELETE CASCADE`, plus `tags` (JSONB array) and `note` (text). One row per user-per-parcel; saving an already-saved parcel upserts its tags/note.
- **Tier-capped** via `accounts.tiers.watchlist_limit` (free 25, pro/enterprise unlimited). The cap is enforced in the service on add — re-saving an existing parcel at the cap is allowed; a new save over the cap raises `QuotaExceededError` (429). Consistent with the ask/lead/parcel-view caps.
- **Endpoints** (`/watchlist`, auth): `GET` (list, joined to parcel + verdict for display fields incl. opportunity score), `POST` (add/upsert), `PATCH /{id}` (tags/note), `DELETE /{id}`, and `GET /{id}` (saved-state probe for the panel toggle).
- **Boundaries:** the service owns only `SavedParcel`; it reads `parcel`/`parcel_verdict` via raw SQL for the list join (the established cross-table read pattern), never importing other modules' models.
- **Frontend:** a bookmark toggle on the parcel panel (optimistic via a Pinia store keyed by saved parcel numbers) and a `/watchlist` page with inline tag/note editing; the store resets on logout.

## Consequences

- Establishes the **user-content table pattern** (composite user×entity PK, cascade deletes, tier cap) for the deal pipeline, notes/tasks, and saved searches to follow.
- The list endpoint joins to `parcel_verdict`; a saved parcel with no computed verdict simply shows a null opportunity score — acceptable.
- Watchlists are the trigger source for **change-alerts**, now built on this foundation (ADR-0017).
- **Deferred:** shared/team watchlists and saved-search criteria (vs. saved parcels) — both build on this foundation.
