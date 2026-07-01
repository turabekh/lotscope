# Information architecture and layout

**Status:** Proposed · **Last updated:** 2026-07-01
**Companion to:** ADR-0029 (the *why*) · `docs/design/wireframes/` (the *picture*)

## Purpose

The target information architecture and screen layout for a multi-market LotScope, on desktop and mobile, staying on Quasar. This is reference material (per §10); the decision and its rationale live in ADR-0029, and the low-fidelity wireframes render the two shells.

## Scope and principles

- **Multi-market-ready, Philadelphia-only today.** The shell assumes a jurisdiction scope from day one; Philadelphia is the only live market. Other PA counties/cities come later (ADR-0004 follow-up).
- **Stays on Quasar / Vue 3.** The component-library question is independent of this change and out of scope here.
- **`css/tokens.css` is the styling contract.** This is a structural change, not a restyle — every surface consumes the existing semantic tokens and introduces no new color values.
- **Re-home and refactor, don't rewrite.** Existing pages move inside the new shell before their internals change; behavior and tests are preserved.

## Information architecture

### Sections (primary navigation)

| Section | Purpose | Today | Target |
|---|---|---|---|
| Home | Per-market daily snapshot (leads, alerts, pipeline value, saved-search hits, market stats) | — | new |
| Explore | Discovery: synced list ⇄ map, search, buy box, area search | `MapPage` (`/app`) | `ExplorePage` |
| Leads | Motivated-seller sourcing, market-scoped | `/leads` | market-scoped |
| Pipeline | Deal Kanban (ADR-0020) | `/pipeline` | market-scoped |
| Lists | Saved parcels + saved searches, merged | `/watchlist` + `/saved-searches` | `ListsPage` (tabs) |
| Settings / Account | Plan, profile | `/account` | footer nav |
| Admin | Operator console (role-gated) | `/admin` | footer nav |

Compare is **not** a section — it becomes a persistent selection tray (reusing the compare store), retiring the `/compare` page.

### Route tree

Market is a first-class URL segment, resolved via the `market` store (default / last-used; `all` reserved for a future cross-market overview).

```
/                         landing (unauthenticated)
/login  /register         auth
/:market                  → redirect to /:market/home
/:market/home             dashboard
/:market/explore          Explore split (search/filter/view in query params)
/:market/leads            leads
/:market/pipeline         deal pipeline
/:market/lists            watchlist + saved searches (tabs)
/parcel/:market/:id       universal parcel dossier (deep-linkable, full page)
/account                  account/settings   (not market-scoped)
/admin                    operator console   (not market-scoped)
```

### Cross-cutting primitives

- **Market scope** — the spine. A `market` store holds the active jurisdiction; every data query is market-scoped; the switcher lives in the sidebar (desktop) and the header (mobile).
- **Global search / command** — address / owner / parcel within the active market (ADR-0005 search), in the top bar.
- **Universal parcel dossier** — one component opened from anywhere (map pin, leads row, list), plus a deep-linkable full-page route for sharing. `ParcelPanel` is decoupled from `MapView`.
- **Compare tray** — a persistent selection basket that reuses the compare store.
- **Data-coverage indicator** — per-market dataset freshness and availability (see graceful degradation below).

## Desktop layout

Reference: `docs/design/wireframes/desktop-app-shell.html`

- **App shell** — persistent left sidebar (logo, market switcher, section nav, footer Settings/Admin) + top bar (global search, coverage chip, user menu) + content region. The sidebar collapses to icons.
- **Explore** — a synced split: results list ⇄ map, with a List / Map / Split toggle. `MapView` is reused unchanged (the MapLibre logic is not touched). Buy-box filters and area search (radius/polygon, ADR-0025) re-home into the Explore rail; drawing on the map still works. Selecting a result opens the dossier as a right-hand slide-over.
- **Dossier** — `VerdictHero` pinned at top; five tabs (Verdict, Deal, Land, Risk, Docs) grouping the existing sub-panels. Renders as a right slide-over in context, or full-page when deep-linked.

## Mobile layout

Reference: `docs/design/wireframes/mobile-states.html`

- **App shell** — `q-header` (market-switcher pill + search + avatar) + `q-page-container` + a `q-footer` bottom tab bar (Home, Explore, Leads, More). Overflow sections (Pipeline, Lists, Settings, Admin) sit behind **More**, which opens the `q-drawer` in overlay mode.
- **Market switcher** — the header pill opens a bottom sheet (`q-dialog position="bottom"`); stays globally reachable because it scopes every screen.
- **Explore** — a List / Map toggle (`q-btn-toggle`). Map mode carries a draggable results peek-sheet (polish pass; the toggle is the baseline). Filters and area search move into a bottom sheet / full-screen `q-dialog` triggered by the filter chip.
- **Dossier** — a full-screen pushed route (`/parcel/:market/:id`); a back chevron replaces the tab bar. `VerdictHero` pins; the five tabs become a scrollable `q-tabs` strip; panels scroll underneath.
- **Hygiene** — pad the tab bar for `env(safe-area-inset-bottom)`; keep ~44px tap targets. MapLibre touch (pan/pinch, terra-draw polygon) already works.

## Responsive behavior (breakpoints)

Driven by the same `$q.screen` mechanism already used to toggle the drawer on `MapPage`.

| Concern | `< md` (mobile shell) | `≥ md` (desktop shell) |
|---|---|---|
| Navigation | bottom tab bar + More → drawer overlay | fixed sidebar (collapsible to icons) |
| Market switcher | header pill → bottom sheet | sidebar control |
| Explore | single pane + List/Map toggle | synced list ⇄ map split |
| Filters / area search | bottom sheet / full-screen dialog | Explore rail |
| Dossier | full-screen route | right slide-over |
| Dossier tabs | scrollable `q-tabs` strip | full tab row |

## Component mapping (reuse / refactor / new)

| Current | Target | Disposition |
|---|---|---|
| `AppHeader.vue` | `AppShell` / `AppSidebar` / `AppTopBar` | refactor |
| `MapView.vue` | (inside Explore split) | reuse unchanged |
| `FilterPanel`, `AreaSearchPanel` | Explore rail / mobile sheet | reuse, re-home |
| `ParcelPanel.vue` (+ `VerdictHero`, `VerdictPanel`, `Checklist`, dossier sub-panels) | `ParcelDossier` (panel + route) | decouple; panels reused |
| `MapPage` | `ExplorePage` | refactor |
| Watchlist + Saved-searches pages | `ListsPage` (tabs) | merge |
| Compare page | `CompareTray` | retire page, reuse store |
| — | `HomeDashboard` | new |
| stores: `auth`, `parcel`, `filters`, `areaSearch`, `watchlist`, `compare`, `savedSearches`, `push`, `theme` | same | reuse (`theme` unchanged) |
| — | `market` store | new (load-bearing) |
| — | `MarketSwitcher`, `GlobalSearch`, `DataCoverageChip` | new |

## Graceful per-market degradation & provenance

- Where a dataset is absent for a market (e.g., no vacancy model or open L&I data outside Philadelphia), panels render "not available in this market" rather than erroring.
- The data-coverage chip surfaces per-market `dataset_freshness`, turning coverage into a visible trust signal that sets honest expectations.
- Preserves the "informational, cited, provenance on every datum" framing (§13; ADR-0007, ADR-0008).

## Non-goals (this change)

- Not a component-library swap (stay on Quasar).
- Not a visual restyle (`css/tokens.css` unchanged).
- No new backend data sources or new-market ingestion (separate track; ADR-0004 follow-up).
- No new analytical features; existing panels are reused as-is.

## Open questions

- Which four sections belong in the mobile bottom bar — is Pipeline or Lists the fourth, with the other behind More?
- Carry the `:market` segment in the URL always, or only once more than one market is live? (Recommendation: always, from day one.)
- Home dashboard v1 contents and priority.
- Draggable results peek-sheet in v1, or ship the List/Map toggle first and add the sheet after?
