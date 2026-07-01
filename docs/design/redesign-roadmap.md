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

- [ ] **Slice 4 — Universal dossier.**
  Goal: decouple the dossier from the map. Touches: `ParcelPanel` → `ParcelDossier` (panel + `/parcel/:market/:id` route); open from map, leads, lists. Reuse: `VerdictHero` and all sub-panels unchanged.
  Acceptance: same panels/tabs; dossier opens from ≥2 surfaces; the deep-link URL renders standalone.

- [ ] **Slice 5 — Home + consolidation.**
  Goal: add the daily-driver landing and tidy the section list. Touches: `HomeDashboard` (per-market snapshot from existing data); `ListsPage` (merge Watchlist + Saved searches, ADR-0016/0024); `CompareTray` (retire `/compare`). Reuse: watchlist/savedSearches/compare stores.
  Acceptance: dashboard reads existing data; Lists tabs work; compare via the tray.

- [ ] **Slice 6 — Mobile layer.**
  Goal: the responsive adaptation across all of the above. Touches: bottom tab bar (`q-footer`/`q-tabs`) + More drawer; header market switcher → bottom sheet; Explore List/Map toggle; filters bottom sheet; full-screen dossier route; scrollable dossier tabs; `env(safe-area-inset-bottom)`. Driven by `$q.screen`.
  Acceptance: each state matches `mobile-states.html` on a phone viewport; the Playwright mobile flow is green.

## After each slice

- Screenshot the result (Playwright can capture these states) and diff it against the matching wireframe.
- Resolve and prune the open questions in `ia-and-layout.md` as decisions land.
