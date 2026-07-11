# Revenue machinery — Slice 0 recon (2026-07-11)

Recon for the Amendment-01 Phase 0/1 pull-forward (pricing, skip-trace credits, sales calendar, mobile
top-3). **Headline: most of this is already built.** Amendment 01 was drafted 2026-07-02 at verdict v5;
prior sessions shipped ADR-0030 (pricing catalog + investor tier) and ADR-0035 (skip-trace credits), so the
net-new surface is much smaller than the prompt assumes. This doc maps spec → reality and re-scopes each
slice to what actually remains. `VERDICT_VERSION` untouched throughout.

---

## 1. Amendment audit — drift map (spec vs. current codebase)

| Item | Amendment spec | Reality today | Net-new remaining |
|---|---|---|---|
| **Pricing → $99/$249** | Pro $29→$99, Investor $249 (§2.1) | **DONE.** `PLAN_CATALOG` pro=9900¢, investor=24900¢ (`tiers.py:150,164`); ADR-0030 | none |
| **Investor tier plumbing** | new `tier` value + limits (§2.2) | **DONE.** `investor` in every limits dict + `FEED_TIERS`; Stripe `stripe_price_investor_*` keys; frontend arrays; checkout flow | none (no migration — tier is a free string, not an enum) |
| **Limits table** | leads 200/1000, exports 10/∞ @ 2000/10000 rows, Ask 200/∞, saved 50 (§2.2) | **DONE.** Matches exactly (`tiers.py:6-55`) | none |
| **Founding-member price** | (this prompt, Slice 0.5) | **MISSING.** No coupon/founding code anywhere | **build** — distinct Stripe price + cap gate |
| **A1 credit ledger** | `credit_ledger`, balance=SUM(delta), monthly grant (§A1) | **DONE.** `credit_ledger` model + `grant_credits`/`credit_balance`/investor cron; migration `b2e5f9a3c74d` | none (table exists) |
| **A1 skip-trace service** | `trace_owner`, cache, reuse window (§A1) | **DONE.** `skiptrace/service.py` `trace_owner` + 90-day cache + reuse window; ADR-0035 | none |
| **A1 real provider** | BatchData/Endato behind protocol (§A1) | **MISSING.** Only `NullSkipTraceProvider`; `get_skiptrace_provider` knows `"null"` only | **build** — real client (this recon §3) |
| **A1 no-hit refund** | refund a credit on zero contacts (§A1, "honest economics") | **MISSING.** `trace_owner` burns unconditionally; `REASON_REFUND` defined, never inserted | **build** |
| **A1 per-market gating** | pgh owner-off ⇒ skip-trace off (invariant #3) | **INCIDENTAL ONLY.** pgh has no `owner`/`owner_key` (loader drops it), so trace raises `ValidationError` by accident; no explicit capability gate; backend doesn't enforce `hidden_surfaces` on owner-portfolio OR skip-trace endpoints | **build** — explicit capability gate |
| **A1 credit packs + checkout** | Stripe one-time packs (§A1) | **DONE.** `packs.py` (25/100/500), `create_credit_checkout_session`, buy-credits UI | none |
| **A1 skip-trace UX** | button + result card + compliance (§A1) | **DONE (dossier).** `OwnerPortfolioPanel.vue` button + result + disclaimer + credits store | **build** — Pipeline-card skip-trace + populate deal contact fields |
| **A3 CSV export** | leads/list export (§A3) | **DONE.** Pro-gated `/pipeline/export` + leads export | **build** — add contact columns for traced parcels (export does NOT join skip-trace today — grep empty) |
| **A4 sheriff calendar** | dated table + calendar API (§A4) | **BACKEND DONE, NO DATA.** `sheriff_sale` table + `list_sheriff_sales` + Pro gate exist; **1 synthetic row (`BW-DEMO-01`) on prod, no real CSV loaded** | **build** — data source + honest states + ICS + digest + page |
| **A4 ICS feed** | (this prompt) | **MISSING.** Zero `.ics`/icalendar code anywhere | **build** (greenfield) |
| **A4 "sales this week" digest** | (this prompt) | **MISSING.** No such digest section | **build** (greenfield, rides staged-rollout) |
| **Mobile top-3** | (this prompt) | Shell/dossier responsive shipped (ADR-0029); never a real device pass | **build** — 3 fixes (§6) |
| A2 Deal Feed, A5 appeal packet, A6 distress v2, A7 assemblage, A8 overlays, A9 abatement, A10/A11 accuracy | later phases | **all shipped** in prior sessions (out of scope here) | — |

**Pipeline-v2 landing pad (A1 target):** `deal.contact_name / contact_phone / contact_email` exist
(`pipeline/models.py:25-27`, migration `c3f9a1d7b4e2`) — skip-trace results populate these.

**Prod state (queried 2026-07-11):** 9 free + 1 enterprise users, **0 Pro subscribers, 0 Stripe-linked
subscriptions**; `credit_ledger` 0 rows, `skiptrace_result` 0 rows (dormant); `sheriff_sale` = 1 demo row.

---

## 2. Tier machinery audit (detail)

- **No enum, no ordinal ranking.** `User.tier` is `String(20)`, no CHECK (`accounts/models.py:18`). Gating is
  per-tier dict lookup + `FEED_TIERS` frozenset membership — never `tier >= X`. So inserting a tier needs no
  migration and breaks no comparison. `investor` is already a first-class value everywhere.
- **Limits** in `accounts/tiers.py` (dicts at `:6-55`, `FEED_TIERS` at `:95`, `PLAN_CATALOG` at `:132`),
  enforced as HTTP 429 `QuotaExceededError` at the call sites (leads/watchlist/pipeline/saved/exports/parcel-
  view/ask). Monthly export counters in Redis.
- **Stripe:** price IDs from `config.py:68-76` (`stripe_price_pro_*`, `stripe_price_investor_*`,
  `stripe_price_pro_legacy` for grandfather, `stripe_price_credits_*`, `stripe_price_appeal_packet`).
  Resolution in `accounts/billing.py` (`pro_price_ids`/`investor_price_ids`/`granting_price_ids`,
  `price_id_for_cadence`). **Tier writes are webhook-only** (`apply_subscription_state`,
  `service.py:65-68`), events `checkout.session.completed` + `customer.subscription.*`.
- **Gate sites to touch for founding price:** add the founding price ID into `pro_price_ids`
  (`billing.py:32`) so it maps to `tier=pro`; frontend duplicated tier arrays
  (`FeedPage/TopPlaysPage/MarketPage/ReportPanel`) don't need changing (founding = pro).
- **Upsell UI:** full-page gates on Feed/TopPlays/SheriffSales/Market/Report; 429 cap handling in
  `ParcelDossier` (parcel-view), `SavedSearchesList` (saved-search), leads/export gated buttons. No
  centralized 429 interceptor — each component checks `status===429` locally. **This is the inconsistency
  the amendment's "upsell at every pressure point" wants smoothed** — a shared upgrade affordance.

---

## 3. Skip-trace provider evaluation → HANDOFF (owner picks + accepts terms)

Non-FCRA real-estate marketing use; owner name + mailing address in → phones/emails out.

| Criteria | **BatchData** (rec.) | Enformion/EnformionGO | REISkip |
|---|---|---|---|
| API & signup | Developer-first REST, self-serve keys, no minimum | Self-serve GO tier, free trial 100/mo, instant key | API secondary to web app |
| Per-hit price | ~$0.02–0.08 pay-as-you-go (verify dashboard rate) | Free 100/mo; ~$0.25→$0.01 at volume (confirm skip-trace rate) | ~$0.15/match, min 50 |
| Match rate | ~76% right-party (claimed) | not published for RE — trial it | 85–90% ≥1 phone |
| Permissible use | **Yes** — RE outreach explicitly permitted, FCRA uses prohibited | Yes, non-FCRA; some GLBA/DPPA-gated fields | Non-FCRA, RE-investor focused; terms not public |
| Caching/retention | **Store OK but must refresh ≤30 days**, no public repo/resale | not public — confirm | not public — confirm |
| DNC/litigator scrub | **Yes** — national DNC + TCPA-litigator scrub as API endpoints | Yes — DNC + state + litigator | National DNC only; litigator unclear |

**Recommendation: BatchData primary** — meets all three hard targets (≤$0.15/hit, JSON REST, storable
results) and uniquely ships DNC + TCPA-litigator scrub as first-class endpoints (needed for §13 anyway).
**Critical architecture caveat:** BatchData terms require **cache refresh ≤ 30 days** — our current
`skiptrace_result` TTL is **90 days** (`service.py:CACHE_TTL_DAYS=90`). If we pick BatchData, the reuse
window must drop to ≤30 days (config change) and the ADR must cite the clause. Keep the provider behind the
existing protocol (already done) so a bake-off vs Enformion is a config swap.

**Confirm at signup (owner):** actual self-serve per-hit rate; storage/reuse clause verbatim; non-FCRA +
GLBA/DPPA field gating in writing; match rate on a real Philadelphia sample; DNC+litigator included vs
add-on; deletion/suppression obligations; no-hit billing behavior. Pricing/terms shift — none of the numbers
above are contractual until the dashboard confirms them.

**→ HANDOFF: owner picks the provider, creates the account, accepts terms, provides `SKIPTRACE_PROVIDER` +
`SKIPTRACE_API_KEY`. No paid commitment until written approval (invariant #4).**

---

## 4. Calendar data audit — what each market can honestly render now

The dated backend is fully built (`sheriff_sale.sale_date`, `list_sheriff_sales`, `/sheriff-sales` Pro-gated,
`next-sheriff-sale` + dossier countdown). **The gap is data, not code.**

- **phl:** full dated pipeline, **empty.** CSV-fed (`SHERIFF_SALE_CSV_PATH`), no CSV loaded; 1 synthetic dev
  row `BW-DEMO-01` (2026-07-22). The Philadelphia Sheriff / CivilView live scraper is deferred
  (`data-sources.md`). → **To render real phl dates, a source must be wired** (CivilView scrape or a periodic
  CSV). Otherwise the calendar honestly shows "no upcoming sales loaded."
- **pgh:** **no sale dates.** Only `tax_status.in_sheriff_sale` boolean + `as_of_date` = court *filing* date
  (not an auction date); `sheriff_sales` surface is hidden for pgh (capabilities). → calendar renders the
  honest "not a scheduled-sale calendar for this market" state.
- **hbg:** **no sale dates.** Repository list is live but dateless; the upset/judicial loader is armed but
  unregistered/empty, expected to flow with the **seasonal August/September Dauphin list**. → calendar
  renders the seasonal window note ("2026 upset sale expected September; list publishes August — armed"),
  populating with no new code when the list lands.
- **Naming** via capabilities `forced_sale_surface_label()` — phl "Sheriff sales", hbg "Tax sales", pgh
  "Treasurer's sale". **ICS: greenfield** (nothing exists). **Filters:** `savedsearch/matching.build_where`
  is market-aware and already has `in_sheriff_sale`/`is_delinquent` predicates — reusable.

**Honest verdict:** the calendar ships mostly as a *presentation + honest-state* layer over existing backend;
the one thing that makes it "render real phl dates" is wiring a live phl sheriff source (its own sub-task/
risk — CivilView scrape stability is an open question, A4 ADR §9.2).

---

## 5. Founding-member mechanics proposal → owner confirms parameters

**Context that simplifies everything: there are 0 paying subscribers.** Grandfathering (invariant #5) is
moot today — nobody's plan changes. The `stripe_price_pro_legacy` mechanism already handles any future
legacy price. So this is purely about the founding offer.

**Two options:**

| | A. Distinct Stripe price (**recommended**) | B. Forever-coupon on $99 |
|---|---|---|
| "Locked for life" | Subscription sits on the founding price ID forever; Stripe never auto-migrates it | A 100%-through-$50-off coupon applied to the $99 price |
| Provenance | The price ID *is* the founding flag — visible in dashboard + webhooks (`granting_price_ids` maps it to `tier=pro`) | Coupon can be detached/expired by accident; muddier in webhooks |
| Proration/annual | Clean | Coupons complicate proration + annual math |
| Build | Add `stripe_price_pro_founding` env; include in `pro_price_ids`; a cap gate on checkout | Coupon plumbing + validation |

**Recommendation: A (distinct Stripe price).** Cleaner, self-documenting, rides the existing webhook→tier
path with one new env var. Founding subscribers are `tier=pro` (full Pro), just on a locked $49 price.

**Cap mechanism:** first **N=50** founding customers **OR** a sprint-end date, whichever comes first.
Enforced app-side: count active subs whose price ID = founding price; when count ≥ N **or** `now > cutoff`,
the checkout hides the founding option and shows $99. Config: `FOUNDING_PRICE_ID`, `FOUNDING_CAP=50`,
`FOUNDING_CUTOFF=<date>`. Checkout rejects a founding session past the cap → falls back to $99. Labeled
"Founding rate — locked for life" in checkout + on the pricing page; honest, dismissible, no dark patterns.

**→ Owner confirms: N (proposed 50), cutoff date, price (proposed $49/mo; annual $490/yr or monthly-only?).**

---

## 6. Mobile top-3 (from the audit; ADR-0029 = "responsive adaptation, not a second UI")

Ranked by live-phone-demo impact:

1. **Pipeline board — the only visibly *broken* surface.** `PipelinePage.vue` default tab = `board`; board
   is ~6×250px horizontal-scroll columns (~1500px on a 375px screen) and drag-to-move is HTML5
   `draggable` (dead on touch). Fix (scoped, CSS + one conditional): on `$q.screen.lt.md` default to the
   `today` tab and/or stack the board vertically (full-width collapsible stages); stage changes already have
   a touch-friendly `more_vert → Move to` menu, so no drag rewrite.
2. **Parcel dossier — the money screen, but explanations vanish on touch.** LotScope's cited/explained hints
   are delivered via hover-only `q-tooltip` (chips + verdict pillars in `ParcelDossier.vue`/`VerdictHero.vue`);
   they never open on touch, so the differentiator is invisible on a phone. Fix: tap-to-reveal
   (`q-menu`/`q-popup-proxy`) or inline captions on mobile for the 3 verdict pillars + key chips; icon-only
   the header "Pipeline" button to de-crowd.
3. **Explore map — controls below touch target.** Home button ~30px + MapLibre zoom ~29px (design doc sets
   ~44px); hover popup (`mousemove`) never fires on touch (tap already navigates to the dossier). Fix
   (presentational): upsize the home button + CSS-scale `NavigationControl`; optionally a light tap-preview.

Caveat: no automated mobile e2e exists (Playwright mobile deferred) — these are code-level findings at 375px;
each fix verified at phone width in its PR (Slice 5 timebox).

---

## 7. Re-scoped plan

Because pricing/investor/ledger/skip-trace-core/calendar-backend are **already built**, the slices shrink to
net-new work. Proposed (each branch from fresh main; my approval per merge):

| Slice | Branch | Net-new scope | Migration? | Handoff? | Risk |
|---|---|---|---|---|---|
| **1** Founding + upsell | `feat/pricing-founding` | founding Stripe price + cap gate; consistent upgrade affordance at the cap-hit points | **no** (tier already a string; founding is a price ID) | Stripe: create founding price (test+live) → env | low |
| **2** Skip-trace provider + refund + gate | `feat/skiptrace-provider` | real BatchData client behind existing protocol; no-hit refund; **explicit** per-market capability gate (add `skip_trace` to `_HIDDEN_SURFACES` + backend enforcement on owner-portfolio & skip-trace endpoints); drop TTL 90→≤30 if BatchData; ADR-0060 (addendum to 0035) | **no** (tables exist; refund is a `reason` string) | provider pick + keys (§3) | med (external API) |
| **3** Skip-trace egress | `feat/skiptrace-egress` | Pipeline-card skip-trace → populate `deal.contact_*`; export contact columns for traced parcels (state "not traced" otherwise); credit balance + reset-date display | no | — | low |
| **4** Sales calendar | `feat/sales-calendar` | calendar page (Pro+) over existing `list_sheriff_sales`; honest per-market/seasonal states; **ICS feed** (greenfield); "sales this week" digest section (rides allowlist); **phl live source** (CivilView scrape or CSV — own risk) | maybe (none for table; source loader only) | phl source acquisition (A4 ADR open Q) | med (source stability) |
| **5** Mobile top-3 | `fix/mobile-demo-blockers` | the 3 fixes above, timeboxed | no | — | low |

**Invariant checks:** v8 untouched (calendar reads existing data); no shared-scoring changes → goldens
unaffected; migrations only if a genuinely new column appears (none foreseen except possibly a calendar
source-tracking field). **The prompt's assumed migrations (tier enum in S1, ledger+trace tables in S2) are
NOT needed — already done.**

---

## Decisions needed to proceed (the PAUSE)

1. **Acknowledge the drift** — most of Phase 0/1 is built; confirm the re-scoped plan (§7) or redirect.
2. **Skip-trace provider** — pick (rec. BatchData), create account/keys, accept terms (§3). Note the 30-day
   cache constraint if BatchData.
3. **Founding parameters** — price (rec. $49/mo), cap N (rec. 50), cutoff date, annual or monthly-only (§5).
4. **Mobile top-3** — confirm the three (§6) or reprioritize.
5. **phl calendar source** — is wiring a live Philadelphia Sheriff source (CivilView scrape / periodic CSV)
   in scope for Slice 4, or does the calendar ship honest-empty for phl until a source is provided? (This is
   the one thing standing between "renders real phl dates" and "renders honest states".)
