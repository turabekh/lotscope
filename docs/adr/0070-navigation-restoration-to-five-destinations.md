# ADR-0070 — Navigation restoration to five primary destinations

Status: accepted (2026-07-28)

Required by `docs/PRD-amendment-03-launch-readiness.md` §12.1 (Slice LR-7, sub-slice **LR-7A** — navigation only). Backlog ticket LR-B-035. Extends ADR-0029; does not supersede it.

## Context

LR-7 asks for a reconciliation between Amendment 03 §12.1 and ADR-0029, on the assumption that the two documents disagree about primary navigation.

**They do not disagree.** ADR-0029 specifies five sidebar sections — Home, Explore, Leads, Pipeline, Lists — with Settings/Admin in the footer. Amendment 03 §12.1 targets five primary destinations. Both documents describe the same shape.

What actually happened is drift in the implementation. `AppSidebar.vue` shipped **ten** primary destinations:

| Destination | In ADR-0029 |
|---|---|
| Home, Explore, Leads, Pipeline, Lists | yes |
| Feed, Sheriff sales, Top plays, Cash buyers, Market | **no** |

Each of the five additions was a reasonable local decision when its feature landed — a new surface needs a way in, and the sidebar was the obvious place. No single one was wrong. Cumulatively they doubled the primary navigation and left a first-time user with ten equally-weighted choices and no indication of which produces an acquisition result.

There is therefore no conflict to reconcile and no ADR to supersede. The accepted contract was never revised; it was outgrown without being revisited.

## Decision

**Restore primary navigation to the five destinations ADR-0029 specifies, and give the five drifted surfaces an explicit home rather than deleting or hiding them.**

### 1. Five primary destinations, in plainer words

`Home · Find lots · Leads · Pipeline · Lists`, with Account and Admin remaining in the footer per ADR-0029.

The only label change is **Explore → Find lots**. "Explore" describes an interaction; "Find lots" describes an outcome, and Amendment 03's plain-language framing is the better of the two for a user in their first session. The route name and path (`explore`, `/:market/explore`) are unchanged, so nothing outside the label moves.

Amendment 03's literal set — `Home, Find Lots, Pipeline, Saved, Account` — was considered and **not adopted**. It drops Leads from primary navigation and promotes Account out of the footer, contradicting ADR-0029 on both points, and neither change was argued for in the amendment. Adopting the naming without the structural changes takes the improvement and leaves the regression.

### 2. Research group for the analytical surfaces

Cash buyers and Market re-home into a collapsible **Research** group in the sidebar. They are reference surfaces consulted during a decision, not steps in one, so they do not compete for a primary slot — but they are also not discovery entry points, so they do not belong in Find lots either.

The group auto-opens when one of its routes is active, so a user who navigates there does not lose their place in the tree.

### 3. Discovery sources consolidate under Find lots

Feed, Sheriff sales, and Top plays are three answers to one question: *which lots should I look at?* They now appear as entry points inside the Find lots rail (`DiscoverySources.vue`) and in the Research group, giving one discovery mental model without making any surface harder to reach.

Their market-scoped visibility rules are preserved — a market that hides `sheriff_sales` hides it in both places — and the per-market forced-sale label (`forced_sale_surface_label`, e.g. Harrisburg's "Tax sales") continues to drive the wording.

### 4. No routes change

Every route keeps its name and path. No redirects are introduced, because nothing moves. A bookmark, a shared deep link, or an external reference to `/philadelphia/top-plays` behaves exactly as before.

This is deliberate: route churn is the expensive, user-visible part of a navigation change, and none of it is necessary to meet the five-destination target. Amendment 03's "preserve route compatibility" requirement is met by not breaking compatibility in the first place.

## Consequences

- **No user loses access to anything.** Ten destinations become five primary plus five reachable in one additional click, and the three discovery surfaces gain a second, more contextual entry point.
- The mobile tab bar already carried a focused three-tab set and needed only the Explore → Find lots rename; mobile and desktop stay consistent without a separate mobile product.
- `AppSidebar.spec.ts` gains a test pinning primary navigation to exactly five. **This is the point of the change** — the drift happened because nothing failed when an eleventh item was added, and a count assertion is the cheapest guard against it recurring.
- **Deferred to LR-7B:** buy-box onboarding, immediate matching parcels, the guided first verdict, progressive profile setup, and the Playwright first-session and mobile-viewport flows. This ADR covers navigation structure only.
- **Risk:** "Research" is a new grouping label appearing in neither governing document. It is a container for two existing surfaces, not a new concept, and is cheap to rename if the owner prefers different wording.
