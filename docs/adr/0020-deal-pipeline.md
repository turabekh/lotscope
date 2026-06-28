# 20. Deal pipeline

Date: 2026-06-28

## Status

Accepted

## Context

PRD §5.9 — a Kanban **deal pipeline** (lead → diligence → offer → under contract → closed) so users can work a parcel from interest to close. It is the next user-content feature after watchlists (ADR-0016) and reuses that pattern.

## Decision

**A `pipeline` module owning a per-user `deal` table, surfaced as a Kanban board.**

- **Model:** `deal` with surrogate `id`, `user_id`+`parcel_number` FKs (cascade), a **unique `(user_id, parcel_number)`** (one deal per parcel per user), `stage`, `note`, `target_price`. Stages are a string `Literal`: `lead`, `diligence`, `offer`, `under_contract`, `closed`, `lost`.
- **Tier-capped** via `accounts.tiers.pipeline_limit` (free 10, paid unlimited), enforced on add — adding an already-tracked parcel returns the existing deal (idempotent), so the parcel-panel "Add to pipeline" is safe to click twice.
- **Ordering** within a stage is by `updated_at desc` — moving or editing a deal floats it to the top. No manual within-column reordering in v1 (keeps the model free of position bookkeeping).
- **Endpoints** (`/pipeline`, auth): `GET` (list, joined to parcel + verdict for address/zoning/opportunity score), `POST` (add/return-existing), `PATCH /{parcel}` (stage/note/target), `DELETE /{parcel}`, `GET /{parcel}` (in-pipeline probe for the parcel panel).
- **Frontend:** a `/pipeline` Kanban with **native HTML5 drag-and-drop** between stage columns (no new dependency) plus a per-card **"Move to" menu** as the accessible/touch fallback; inline note and target-price editing via `q-popup-edit`; cards click through to the map. An "Add to pipeline" control on the parcel panel shows the current stage once tracked. The store resets on logout.

## Consequences

- Reuses and reinforces the **user-content pattern** (user×parcel scoping, cascade, tier cap, optimistic Pinia store) shared with watchlists.
- **One deal per parcel per user** — re-adding is a no-op return; a user can't track the same lot as two separate deals (acceptable; matches how people work a parcel).
- **Native DnD** is desktop-first; the move menu covers touch/keyboard. A drag library (SortableJS) and within-column reordering are a follow-up if needed.
- **Deferred (PRD §5.9/§5.11):** per-deal document management, notes/tasks/reminders, team-shared pipelines, offer/LOI generation, and won/lost analytics — all build on this `deal` foundation.
