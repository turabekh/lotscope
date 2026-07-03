# Frontend redesign roadmap

**Status:** Proposed · **Last updated:** 2026-07-01
**Related:** ADR-0029 · `docs/design/ia-and-layout.md` · `docs/design/wireframes/`

## How to run this

- **Sequenced vertical slices**, each its own branch + PR + green tests + review, per §5/§11 (modular vertical slices) and §6 (git & versioning).
- **For each slice**, point the agent at ADR-0029, `ia-and-layout.md`, and the wireframes; have it read the current code; **plan before writing** (§4); reuse existing components/stores; consume `css/tokens.css` (no new colors); keep tests green (§12).
- In the slice that lands the shell, **update `CLAUDE.md` §3 and §10** to reference `ia-and-layout.md`.

## Slices

- [x] **Slice 1 — Market-scope foundation.** *(shipped: 1a rename, 1b routing, 1c search)*
  Goal: make jurisdiction explicit end-to-end. Touches: new `market` store, the `/:market/...` routing convention, market-scoping `lib/api`. Reuse: everything else unchanged. No visual change.
  Acceptance: existing flows work under a Philadelphia market segment; tests green.
  Delivered: `market` store (URL > localStorage > default precedence); flattened `/:market/...` routes with `/ → /:market/home → /:market/explore` (home is a temporary redirect until slice 5); URL-authoritative guard that resolves/validates the market before the auth redirect; full link sweep (`map`→`explore` + all hardcoded `/app` literals); `GET /search` market param (unknown → 422, response echoes scope) with `search()` requiring `market`. Split as an isolated rename commit first so the clean `market` name was free.

- [x] **Slice 2 — App shell.** *(shipped: 2a shell+re-home, 2b primitives, 2c docs)*
  Goal: replace the top-nav with the persistent shell, re-homing existing pages unchanged. Touches: `AppShell`/`AppSidebar`/`AppTopBar` (refactor `AppHeader`), `MarketSwitcher`, `GlobalSearch`, `DataCoverageChip`. Reuse: all current pages, mounted inside the shell.
  Acceptance: every page reachable from the sidebar; top-nav removed; visuals unchanged (tokens); tests green.
  Delivered: `AppShell` mounts once in `App.vue` (gated on `meta.requiresAuth`, not route nesting) around all authed routes; `AppHeader` deleted and all 8 pages re-homed (`MapPage` keeps its drawer via a nested `container` layout); sidebar nav (existing pages only) + footer Account/Admin; `MarketSwitcher` (URL-driven), `GlobalSearch` (SearchBox reuse → explore), static market-driven `DataCoverageChip`. `CLAUDE.md` §3/§10 point at `ia-and-layout.md`; ADR-0029 Accepted. **Follow-up:** a public per-market dataset-freshness surface (the coverage chip is a static label until then).

- [x] **Slice 3 — Explore.** *(shipped: 3a scaffold, split fix, viewport list, 3b-1 list+sync, 3b-2a controls, 3b-2b query params)*
  Goal: turn the map-first page into the synced discovery workspace. Touches: `MapPage` → `ExplorePage` with a list ⇄ map split + List/Map/Split toggle; re-home `FilterPanel`/`AreaSearchPanel`. Reuse: `MapView` unchanged.
  Acceptance: list and map stay in sync; buy box + area search (ADR-0025) work; parity with today's map behavior.
  Delivered: `MapPage` → `ExplorePage`; List/Map/Split split with a fixed 360px list rail + elastic map (no overflow), rail collapses when empty; the list is **viewport-driven** (updates on pan/zoom, zoom-gated) with two-way row⇄pin sync through `parcelStore.detail`; controls decomposed into a **Buy box** toolbar popover + one compact **MapControlsOverlay** (display + draw), with `FilterPanel`/`AreaSearchPanel` deleted; view + buy box + area shape persisted in query params. **`MapView` deviation from "unchanged":** it gained exactly one pure output — a `boundschange` emit (bounds + zoom) — with no MapLibre/terra-draw logic touched; all viewport policy lives in `ExplorePage`.

- [x] **Slice 4 — Universal dossier.** *(shipped: 4a extract + route + GlobalSearch, 4b Leads/Watchlist)*
  Goal: decouple the dossier from the map. Touches: `ParcelPanel` → `ParcelDossier` (panel + `/parcel/:market/:id` route); open from map, leads, lists. Reuse: `VerdictHero` and all sub-panels unchanged.
  Acceptance: same panels/tabs; dossier opens from ≥2 surfaces; the deep-link URL renders standalone.
  Delivered: `ParcelPanel` → `ParcelDossier` (renamed, internals unchanged — already fully store-driven); one body, two wrappers — Explore's right `q-drawer` (overlay, unchanged) and the full-page `ParcelDossierPage` at `/parcel/:market/:id` (fetches on mount, bounded centered frame, not-found via the dossier's own error state). `:market` validated by the Slice-1b guard; lookup by `id` only. Opens from Explore (pin/row overlay), GlobalSearch, Leads, and Watchlist. **Follow-up:** Compare/Pipeline/SavedSearches still open into the Explore overlay — a trivial one-line repoint each onto the dossier route.

- [x] **Slice 5 — Home + consolidation.** *(shipped: 5a Lists, 5b Compare tray, 5c Home dashboard)*
  Goal: add the daily-driver landing and tidy the section list. Touches: `HomeDashboard` (per-market snapshot from existing data); `ListsPage` (merge Watchlist + Saved searches, ADR-0016/0024); `CompareTray` (retire `/compare`). Reuse: watchlist/savedSearches/compare stores.
  Acceptance: dashboard reads existing data; Lists tabs work; compare via the tray.
  Delivered: **5a** — `ListsPage` at `/:market/lists` merging Saved lots / Saved searches tabs (`?tab=`), old routes name-preserving redirects, sidebar two items → one Lists. **5b** — `/compare` route retired to a name-preserving redirect to explore; a persistent bottom-center `CompareTray` (visible when the compare store is non-empty) reuses the store, shows chips + count, and expands the extracted `CompareTable` in a dialog; parcel-open now targets the dossier route; the redundant user-menu Compare item removed. **5c** — `HomePage` at `/:market/home` (replacing the temp home→explore redirect): four read-only snapshot cards (what-changed, pipeline value + stage counts, top leads, market coverage/totals) from existing stores + the leads endpoint, every card empty-stating into Explore/Leads and every row deep-linking to the dossier; `PipelinePage` parcel-open repointed to the dossier route (last explore-bounce retired). Sidebar reached its final shape in Slice 2 already (Home, Explore, Leads, Pipeline, Lists; Account/Admin footer).

- [ ] **Slice 6 — Mobile layer.**
  Goal: the responsive adaptation across all of the above. Touches: bottom tab bar (`q-footer`/`q-tabs`) + More drawer; header market switcher → bottom sheet; Explore List/Map toggle; filters bottom sheet; full-screen dossier route; scrollable dossier tabs; `env(safe-area-inset-bottom)`. Driven by `$q.screen`.
  Acceptance: each state matches `mobile-states.html` on a phone viewport; the Playwright mobile flow is green.

## After each slice

- Screenshot the result (Playwright can capture these states) and diff it against the matching wireframe.
- Resolve and prune the open questions in `ia-and-layout.md` as decisions land.

## Open questions / follow-ups (do NOT build during the redesign)

- **Explore list ordering (fast-follow).** The viewport/area list orders by `opportunity_score DESC` and caps at 200 — i.e. it shows the *top slice by score*, not a representative sample of what's in view. The honest-count fix (Slice 3 follow-up) surfaces the true total and a "showing top N by score" label, but that label must not become a permanent cover for only-ever-showing-the-top: queue **representative ordering or paging** so the list reflects the viewport, not just its highest-scored parcels.
- **Saved-search true match count (honest-count follow-up).** Saved-search matches are capped at storage (`MAX_MATCHES_PER_SEARCH = 500`) and `match_count` counts the *stored* rows, so a search matching more than 500 lots shows `500` as if it were the total. Unlike the viewport list (fixed in slice 3), there is no cheap true total — it needs an uncapped `COUNT` over the criteria (a `build_match_count_sql` variant threaded through `SavedSearchDetail`/`Item` + the frontend "showing top 500 of N"). Deferred: the cap is high and the common case is exact, so this is lower priority than the viewport case.
- **Opportunity-score quantization (verdict-model investigation, post-redesign).** 71% of parcels sit at exactly `62` (42%) or `92` (29%); the model under-discriminates and the score chip can't differentiate dense-area lots. Investigate the score distribution/binning in the verdict engine (ADR-0007 contract) — an ADR-level change, not a UI fix, and out of scope for the redesign.
