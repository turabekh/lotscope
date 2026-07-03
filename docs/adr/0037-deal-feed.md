# 37. Deal Feed — citywide change detection

Date: 2026-07-03

## Status

Proposed

Gates PRD-amendment-01 feature **A2** (Phase 3). Depends on ADR-0036 (`parcel_event`); extends ADR-0017/0024 (change alerts / saved searches), ADR-0018 (email digests), ADR-0029 (market-scoped IA), ADR-0030 (tiers).

## Context

A2 is the **retention feature**: "since yesterday in your buy box — 14 new sheriff-sale flags, 31 new delinquencies, 6 dangerous-building designations, 4 assessment drops." ADR-0016/0017 already do this for *watched* parcels; A2 widens it to *the whole city, filtered by the user's buy box*. ADR-0036 built the substrate — `parcel_event` rows emitted at merge time with the ADR-0017 taxonomy — so the feed is now a **read model over `parcel_event`**, not new detection logic. What's missing is the query surface, the tier gate, the page, and the Investor email.

The amendment fixes the key reuse: feed filtering **reuses `savedsearch.matching.build_where` verbatim**, so a saved search doubles as a feed filter. The tier matrix (§2.2): Deal Feed is **Pro (in-app)** and **Investor (in-app + daily email)**; Free has none.

## Decision

**A read-only feed API over `parcel_event` joined to parcel context and filtered by `build_where`, a market-scoped Feed page, and an Investor daily email — all reusing existing machinery.**

### Read model & API

- `GET /feed?since=&saved_search_id=&limit=` (auth, **Pro+**):
  - **Filter** joins `parcel_event` to the same base as saved-search matching (`parcel` + `parcel_verdict` + `parcel_distress` + `tax_status`) and applies `build_where(criteria)` **verbatim**. `saved_search_id` (owned) supplies the criteria; omitted → whole active market (capped). This is the amendment's "a saved search doubles as a feed filter."
  - **Window**: `since` defaults to 24h ago; clamped to a max look-back (e.g. 30 days) to bound the scan. `detected_at >= since`.
  - **Response** = a **summary** (count per event code — the "14 sheriff-sale, 31 delinquencies" line) **plus** a capped, most-recent-first **event list** (each row: parcel number + address, code, human label, severity, `detected_at`, old/new value, opportunity score for ranking). Honest count: summary is the true total per code; the list states "showing N of M" (the §no-silent-caps rule, consistent with the Explore/leads honest-count work).
  - Ordered `detected_at DESC, severity`. Indexed by `parcel_event.detected_at` and `code` (added in ADR-0036).
- **Tier gate**: a `feed_access(tier)` predicate in `accounts/tiers.py` — `pro`/`investor`/`enterprise` allowed, `free` → typed upgrade error (like the export gate).
- Event **code→label/severity** mapping is shared with the ADR-0017 watchlist-change labels (one source of truth for the taxonomy's human strings).

### Frontend

- A **Feed** page at `/:market/feed` — a first-class left-sidebar item (slots into the ADR-0029 market-scope primitive, scoped to the active market). Summary chips across the top ("31 new delinquencies" etc.), then the event list; **each row deep-links to the parcel dossier** (`/parcel/:market/:id`). A saved-search picker drives the filter (reusing the Lists saved searches). Free sees an upgrade wall; the sidebar item is visible to all (discovery) but the page gates.

### Email (Investor daily digest)

- Reuses the **ADR-0018 SMTP machinery** and the per-user iteration pattern (`send_saved_search_alerts` shape): a worker cron in the **13:00 digest slot** builds, per active **Investor** with alert-enabled saved searches, a digest of `parcel_event`s since the last send that match the union of their saved-search criteria, and emails it. Dormant when SMTP is unconfigured (returns 0, like existing digests). Per-user "last sent" watermark avoids repeats.

### Retention

`parcel_event` is kept **18 months** (ADR-0036) — also the seed of the longitudinal-history moat — swept by a worker cron. The feed only reads within that window.

### Coverage grows with loader migration

The feed is only as rich as the datasets on the staged path (ADR-0036). Today that's **tax** (`delinquent`, `tax_up`). As loaders migrate — L&I (`li_new`, `danger`, `new_permit`, `new_demo`), OPA (`assessment`), sheriff (`sheriff_sale`), RTT (`new_deed`) — the same feed fills out with no feed-side change. The feed ships useful with tax and deepens as D1 rolls forward; this is called out so the first release isn't mistaken for the final coverage.

## Consequences

- A2 is a **thin read model**, not new detection — the hard part (delta capture) is already done and tested (ADR-0036). Risk is mostly query performance (bounded by the `since` window + `detected_at` index + the capped list) and correct `build_where` reuse (a saved search and its feed filter are guaranteed identical because they share the exact function).
- **Retention/churn payoff** is the goal (feed WAU / paying users ≥ 60%; feed-users churn ≥30% lower). The daily email is the re-engagement hook; the in-app page is the daily driver.
- **Tier discovery vs gate**: the sidebar item is visible to Free (so they see what they're missing) but the page/API gate — a deliberate upgrade surface, same pattern as exports.
- **First-release coverage is tax-only** until more loaders migrate; the summary will look thin until then. Acceptable and honest (the page states its window and counts); it also creates the incentive to keep migrating loaders.
- **Deferred**: web-push for feed events (amendment open Q#4 — stays in-app + email for v1; ADR-0019 infra exists if we revisit); inline buy-box criteria on the feed beyond a saved search (v1 uses a saved search or whole-market); per-event read/dismiss state; feed for non-Philadelphia markets (single-market today).
