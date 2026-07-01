# 29. App shell and market scope

Date: 2026-07-01

## Status

Accepted

## Context

Today's frontend is **map-first**: `MapPage` is the home, the map fills the screen, and everything hangs off a left `q-drawer`; the other surfaces (watchlist, pipeline, compare, leads, saved searches) are top-nav links in `AppHeader`. This fits a single contiguous city.

Two forces break that model:

- **Multi-market.** The roadmap adds other PA counties/cities (ADR-0004 follow-up). Geographically disjoint markets — e.g., Philadelphia and Harrisburg, ~100 mi apart — cannot share one "home map" at a useful zoom, and nothing in the UI expresses a jurisdiction scope. The parcel key and much of the schema are Philadelphia-specific, so scope has to become explicit before a second market lands.
- **Surface growth.** The app now has 8+ pages and a 15-panel dossier. A horizontal top-nav (already carrying alert and compare badges) and a narrow map drawer do not scale, and most of the actual work — leads, pipeline, lists, compare — is tabular, not spatial.

Two existing properties make a structural change cheap rather than a rewrite: the design language is already in framework-agnostic tokens (`css/tokens.css`), and business logic lives in Pinia stores + `lib/`, not in components. So this is an **information-architecture** change, not a restyle and not a rewrite. It is also independent of the separate question of the component library, which stays Quasar per §2.

## Decision

**Adopt a market-scoped app shell: a persistent nav, jurisdiction as a first-class scope, the map demoted to one pane of an Explore workspace, and the parcel dossier decoupled into a universal, deep-linkable surface.** The full target is in `docs/design/ia-and-layout.md`; the two shells are wireframed in `docs/design/wireframes/`.

- **Market scope is a first-class primitive.** A `market` store holds the active jurisdiction, every data query is market-scoped, and routes carry a `/:market/...` segment. Philadelphia is the only live market; the scope is introduced **now, while single-market**, so downstream surfaces assume it and the second market is not a retrofit. This is the load-bearing decision.
- **Persistent sidebar replaces the top-nav.** Sections: Home, Explore, Leads, Pipeline, Lists; Settings/Admin in the footer. It collapses to icons and becomes a bottom tab bar on mobile.
- **Map demoted to one pane of Explore.** Explore is a synced list ⇄ map split with a List / Map / Split toggle. `MapView` is reused unchanged (the MapLibre logic is not touched); buy-box filters and area search (ADR-0025) re-home into the Explore rail.
- **Universal parcel dossier.** `ParcelPanel` — with `VerdictHero` and the existing sub-panels — is decoupled from `MapView` into a dossier that opens from anywhere (map pin, leads row, list) and also has a deep-linkable full-page route `/parcel/:market/:id` for sharing.
- **Consolidation.** Watchlist + Saved searches (ADR-0016, ADR-0024) merge into a `Lists` section; Compare (a page today) becomes a persistent selection tray reusing the compare store; a new Home dashboard gives a per-market snapshot built from data already computed.
- **Mobile is a responsive adaptation, not a second UI.** Bottom tab bar (`q-footer`/`q-tabs`) + More → drawer overlay; header market switcher → bottom sheet; Explore List/Map toggle; filters in a bottom sheet; full-screen dossier route; scrollable dossier tabs. All driven by the same `$q.screen` breakpoints already used to toggle the drawer.
- **Styling contract unchanged.** Every surface consumes `css/tokens.css`; no new color values. Existing tests stay green; component tests update selectors rather than rewriting behavior.

## Consequences

- **A one-time market-scope refactor now** — a `market` store, the `/:market` routing convention, and market-scoping the `lib/api` layer — paid while only Philadelphia exists. Far cheaper now than after a second market and several more surfaces.
- **Re-home before rewrite.** Existing pages move inside the new shell before their internals change, keeping each slice reviewable and tests green. The sequence is in `docs/design/redesign-roadmap.md`.
- **`MapView` and the dossier sub-panels are reused unchanged** — the change is structural (where things live, how they are scoped), not behavioral.
- **Enables graceful per-market degradation.** With a scope in place, panels can show "not available in this market" instead of erroring where a dataset is absent (e.g., no vacancy model or open L&I outside Philadelphia), and per-market `dataset_freshness` becomes a visible coverage signal — consistent with the informational/provenance framing (§13; ADR-0007, ADR-0008).
- **Independent of the component library.** Settling this IA neither commits to nor rules out a future PrimeVue move; it makes that decision easier by isolating which surfaces (the dense tables) would actually benefit.
- **Deferred:** the cross-market ("all markets") overview and small-multiples; the draggable mobile results peek-sheet (the List/Map toggle is the v1 baseline); Home dashboard contents beyond v1; a **public per-market dataset-freshness surface** — until it exists the `DataCoverageChip` ships as a static, market-scoped provenance label (freshness is currently admin-only via `/admin/datasets`). This is the natural companion to the graceful per-market degradation described above.
- **Follow-ups:** update `CLAUDE.md` §3 (repository layout) and §10 (module boundaries) to point at `docs/design/ia-and-layout.md` in the implementing PR, per the rule that a convention change updates `CLAUDE.md` in the same PR.
