# LotScope rebuild — Claude Code implementation plan

One session per step. Each prompt is self-contained: paste it into Claude Code at the repo root, on a fresh branch off `main`. Steps inside a phase run in order; phases 2 and 3 can interleave once 2.1 is merged.

Owner actions (things only you can do — accounts, keys, money) are marked **OWNER** and sit before the step that needs them. Do them first or the session stalls.

---

## Session protocol (paste at the top of every prompt)

```
Read docs/PRODUCT.md first. It replaces every rule that used to live in CLAUDE.md, docs/adr, docs/feature-ledger.md and docs/verdict-bump-queue.md — those are archived history, not instructions.

Working rules for this session:
- Restate the goal in two sentences, list the files you will touch and delete, then start. Do not ask for permission on anything already decided in this prompt.
- Delete means delete: remove the file, its tests, its imports, its routes, its migrations' forward-only dependencies if any, and every reference. `grep` for the name before you declare it gone.
- Every derived fact returned to a user carries `source`, `source_url` (when one exists) and `fetched_at`/`computed_at`. This is the one rule from the old system that survives, because it is a customer feature.
- Gates before commit: `make lint`, `make typecheck`, `make test` (unit), and for anything touching search/verdict/deal, `make test-integration`. Report the exact numbers (passed / skipped / failed). `0 skipped` on integration is the check, not just green.
- Commit in small conventional commits on the branch named in this prompt. Do not merge; I merge.
- End the session by appending ≤10 lines to docs/LOG.md: date, branch, what shipped, what is verified, what you did not do. No other handoff document.
```

---

# Phase 0: stop the bleeding

### OWNER 0.0 (do today, before any session)
- [ ] Revoke the GitHub PAT that was in `mynotes.txt`; generate a new one and store it in your password manager only.
- [ ] Remove the `github-actions-deploy` SSH key from the VM's `authorized_keys` and from the GitHub deploy keys; generate a new pair.
- [ ] Change the `admin@admin.com` password via the DB (`UPDATE app_user SET ...`) or delete that account and create a fresh admin.
- [ ] Fix the GitHub Actions billing/payment method.
- [ ] `git rm mynotes.txt lotscope.txt` (or move them outside the repo), commit, push. If they were ever committed, treat every secret in them as burned regardless.
- [ ] Remove `lotscope_docs.txt` from this Claude project's knowledge and re-upload without those two files.

### Step 0.1 — New operating doc, archive the old governance
Branch: `chore/product-doc`

```
[session protocol]

Goal: replace the governance system with one page and archive the rest as history.

1. Create docs/PRODUCT.md with exactly this content and nothing more:

   # LotScope
   An AI acquisitions analyst that works Philadelphia land for you.

   Who: people who buy vacant lots in Philadelphia — sheriff-sale buyers first, infill developers second.
   What they pay for: (1) a Sale Packet — every vacant lot on a sheriff-sale date screened against their buy box, with MAO, red flags and comps; (2) Lot Diligence — a pre-closing checklist on one parcel; (3) later, a monthly Analyst plan with a nightly brief.
   The product is the Analyst conversation. The Lot page is evidence the Analyst opens. Deals is the pipeline. There are no other screens.
   Market: Philadelphia only.
   One metric: paid packets this week.

   Rules:
   - Every derived fact carries source, source_url and computed_at/fetched_at. A fact the Analyst cannot source is labelled "unverified", never asserted.
   - Anything a buyer will check (owner, last deed, open violations, sale status) is verified live against the primary source at answer time; the nightly ingest is an index, not the truth.
   - Ship behind a flag, measure on real users. No feature gate, no ADR, no version ceremony.
   - Tests cover money math: zoning eligibility, deal/MAO, delinquency attribution, party matching, comp selection, parcel-key reconciliation. Everything else is tested by using it.
   - Provenance on every derived field. That is the whole rulebook.

2. Move CLAUDE.md, docs/adr/, docs/handoff/, docs/feature-ledger.md, docs/verdict-bump-queue.md, docs/v11-delta-ledger.md, docs/v9-overlay-aware-standards-recon.md, docs/launch-readiness/, docs/preflight/, docs/recon/, docs/decisions/, docs/audit/, docs/claude-code-*.md, docs/PRD*.md, docs/expansion-prd-discrepancies.md, docs/revenue-recon.md, docs/opsux-v2-recon.md, docs/wave*.md, docs/hbg-*.md, docs/pgh-*.md into docs/archive/ with a one-line docs/archive/README.md: "Historical. Nothing here is an instruction."
3. Keep in place: docs/data-sources.md (Philadelphia sections only — strip hbg/pgh/wlm), docs/architecture.md (rewrite to ≤40 lines describing the modules that survive after Phase 0.2), docs/runbook.md (strip other markets), docs/email.md, docs/data-licenses.md.
4. Create docs/LOG.md with a header and your first entry.
5. Create a new top-level CLAUDE.md containing only: "Read docs/PRODUCT.md. Follow the session protocol in the prompt you were given."
```

### Step 0.2 — Philadelphia only
Branch: `refactor/philadelphia-only`

```
[session protocol]

Goal: remove Pittsburgh, Harrisburg and Wilmington from the codebase. Philadelphia is the only market. Keep the `market_code` column (it holds "phl") so no data migration is needed; delete every branch that varies on it.

Delete outright (files, tests, fixtures, docs references):
- backend/src/lotscope/ingestion/loaders/{hbg.py, hbg_repository.py, hbg_taxclaim.py, hbg_violations.py, pgh.py, wlm.py, wlm_layers.py}
- backend/src/lotscope/zoning/{seed_pgh.py, seed_wlm.py} and any hbg zoning corpus loader
- backend/scripts/{graduate_hbg_zoning.py, build_hbg_zoning_corpus.py}
- backend/src/lotscope/markets/ — the whole module. Replace with a single constant module backend/src/lotscope/core/market.py: MARKET_CODE = "phl", MARKET_NAME = "Philadelphia", CRS_ANALYSIS = 2272, CRS_TILES = 4326.
- backend/src/lotscope/vacancy/derivation.py's per-market table becomes a single Philadelphia list.
- Any `hidden_surfaces`, `capabilities`, `forced_sale_surface_label`, `for_market(...)` prompt substitution, per-market comp selection switches, per-market distress profiles. One code path.
- Frontend: stores/market.ts, MarketSwitcher.vue, DataCoverageChip.vue's per-market coverage, the `/:market/` route segment (routes become `/explore`, `/parcel/:id` etc. for now — the full route rewrite is Phase 3, just drop the segment cleanly here).
- Alembic: do not delete old migrations. Add one migration that drops market-only tables if any exist purely for hbg/pgh/wlm (e.g. hbg repository/taxclaim tables, wlm layer tables). Leave shared tables alone.

Then:
- grep -riE "pgh|hbg|wlm|harrisburg|pittsburgh|wilmington|treasurer" across backend and frontend and remove every hit except in docs/archive.
- Run the full gate. Integration tests must run with 0 skipped.
- Report: files deleted, lines removed, test count before/after.
```

### OWNER 0.3
- [ ] Copy the phillyruleparser artifacts (the 24 MB corpus output) to the VM at `/srv/lotscope/corpus/` — `scp` or a GCS bucket, your call.
- [ ] Confirm `ANTHROPIC_API_KEY` is set in the production `.env` with a paid key and a sensible spend limit.

### Step 0.3 — Corpus live in production
Branch: `feat/corpus-live`

```
[session protocol]

Goal: the Philadelphia Code corpus (phillycode, 29,297 provisions) is loaded in production and is the only retrieval source for zoning/legal answers.

1. Add a management command `uv run lotscope corpus load --path /srv/lotscope/corpus` that (a) is idempotent on provision_id, (b) embeds only provisions whose content hash changed, (c) prints a coverage table by title at the end. Reuse ai/corpus.py, ai/phillycode.py, ai/embeddings.py.
2. Make PHILLYCODE_SOURCE the default retrieval scope. Delete the `title14` incumbent path (ai/scope.py's dual-scope logic, `_incumbent_context`, `source_override`), the data/title14 quick-guide loader, and their tests. Hybrid retrieval (ai/hybrid.py) stays and is the only path.
3. Add a health check: GET /health/corpus returns provision count by title and the embedding coverage %. Fail the endpoint (503) if count < 25,000.
4. Write the deploy steps into docs/runbook.md: load command, health check, expected counts.
5. Verify locally against a copy of the artifacts; report counts.
```

### Step 0.4 — Sheriff calendar wired to search, scraper on a schedule, postponement events
Branch: `feat/sheriff-calendar-live`

```
[session protocol]

Goal: "sheriff sale" in this product means "scheduled for auction", full stop. The CivilView scraper is the source, it runs daily, and status changes become events.

1. search/spatial.py: the `sheriff_sale_only` predicate currently resolves to `tax_status.in_sheriff_sale`. Replace it with an EXISTS against `sheriff_sale` where `sale_date >= current_date` and `status` is not withdrawn/stayed/sold. Rename the request field to `scheduled_for_sale`. Add an optional `sale_date` filter. Delete the Revenue-flag variant entirely.
2. Register the CivilView loader (ingestion/loaders/sheriff_civilview.py) on the nightly ARQ schedule. Keep the CSV loader (sheriff.py) only as a manual fallback; if it is dead code, delete it.
3. Add `sheriff_sale_event` (parcel_number, case_number, sale_date, old_status, new_status, old_sale_date, new_sale_date, observed_at). The loader writes one row per changed status or date. This table is what alerts and the nightly brief read.
4. api/sheriff_sales.py: GET /sheriff-sales?date=... returns the list with parcel joins (is_vacant, zoning, lot area, opening_bid, status). Remove the Pro tier gate.
5. Integration test: seed three listings, change one status, assert the event row and the search predicate.
6. Report: how many upcoming rows and distinct sale dates exist on the local prod copy after a scraper run, and how many are vacant.
```

### OWNER 0.5
- [ ] Create a Mailgun account, add the sending domain, complete DNS (SPF/DKIM/DMARC), and put `MAILGUN_API_KEY`, `MAILGUN_DOMAIN`, `MAIL_FROM` in production `.env`.

### Step 0.5 — Email works; registration requires verification
Branch: `feat/email-and-verification`

```
[session protocol]

Goal: transactional email sends in production and nobody gets an account without a verified address.

1. notifications/email.py: confirm the Mailgun transport is the production path; local dev keeps mailpit. Send a test message end to end from a management command `uv run lotscope email test <address>`.
2. Registration: on POST /auth/register create the user with `email_verified_at = NULL`, send a signed, 24-hour verification link, and return 202. Every authenticated endpoint except /auth/* and /health returns 403 `email_unverified` until the link is clicked. Add `email_verified_at` via migration. Resend endpoint rate-limited to 3/hour per address.
3. Frontend: a single "check your email" screen after register; a "verify" route that hits the token endpoint and redirects to /.
4. Delete the daily distinct-parcel quota on area search (it was a stopgap for open registration) and the parcel-view quota machinery in accounts/tiers.py only if nothing else depends on it; otherwise leave for Phase 5.
5. Playwright: update e2e/12-auth.spec.ts for the verification flow (mailpit exposes the link).
```

### Step 0.6 — CI that runs
Branch: `ci/fast-gates`

```
[session protocol]

Goal: one workflow, green in under 3 minutes on a PR, no manual SSH deploys of unverified code.

1. .github/workflows/ci.yml: lint + typecheck + unit tests on every PR (target < 90s). Integration tests (testcontainers Postgres) as a second job, required for merge, target < 3 min — if the existing integration suite is slower, mark the slowest tests and move them to a nightly workflow.
2. Branch protection notes in docs/runbook.md: required checks, squash merge.
3. deploy.yml: deploy only from main after CI is green; before stopping containers, query `ingest_run` for rows without `finished_at` and abort with a clear message if a run is active (this is the 08-24 incident guard).
4. Delete the pre-commit config if it duplicates CI; keep `make lint`/`make typecheck`/`make test` as the local entrypoints.
```

---

# Phase 1: the Sale Packet

### Step 1.1 — Buy box as the one user profile object
Branch: `feat/buy-box`

```
[session protocol]

Goal: one `buy_box` per user that every screen, the packet and (later) the Analyst read. Replace the scattered assumption/underwriting/BuyBoxPanel state.

Schema (new table `buy_box`, one row per user, migration):
- areas: list of {name, polygon GeoJSON} or zip list
- max_bid, target_use ("hold" | "build" | "flip"), min_lot_sqft, zoning_codes allowed, exclude_city_neighbor bool, exclude_open_violations bool, exclude_historic bool, exclude_flood bool
- deal assumptions: the existing underwriting assumption contract (ARV/sqft, build cost/sqft, soft-cost %, target margin) — reuse deal/assumptions.py's schema; do not invent a second one.
- owned_parcels: list of parcel numbers the user says they own (seed from OPA owner name on request, but user-editable)

1. GET/PUT /me/buy-box. Defaults are sane Philadelphia rowhouse-lot numbers; document them in the schema descriptions.
2. deal/service.py reads assumptions from the buy box when a user is in context; the market-assumption override plumbing (deal/assumptions.py, ADR-0079 remnants) is simplified to: buy box → fallback defaults. Delete the inert override paths and their key-name mapping.
3. Frontend: one BuyBox editor component reachable from /account. Delete BuyBoxOnboarding.vue and BuyBoxPanel.vue.
4. Tests: deal math with buy-box assumptions vs defaults (money math — keep these thorough).
```

### Step 1.2 — Packet composer
Branch: `feat/sale-packet`

```
[session protocol]

Goal: for one sheriff-sale date and one user's buy box, produce the Sale Packet as a structured object and as a PDF.

New module backend/src/lotscope/packet/ (models.py, compose.py, render.py, service.py, tests/).

compose.py — pure, given (sale_date, buy_box, and pre-fetched per-parcel inputs) returns PacketModel:
- header: sale date, sale type, how many listings, how many vacant, how many pass the buy box, generated_at, data-as-of timestamps per source
- lots: for every vacant lot on the date (and a collapsed appendix for non-vacant), each with:
  - address, parcel number, case number, opening bid, status, plaintiff
  - lot area, zoning, overlays, by-right result from zoning/buildability (eligible / not / needs variance, with the dimensional reason and Title 14 cite)
  - MAO under the buy box, est. margin, the two most sensitive inputs from deal/sensitivity.py
  - red flags, each with source + url: open L&I violations (count, most recent), delinquency posture with named debtor (use the attribution logic as-is), city/PHA/Land Bank adjacency, historic, flood, unsafe/ID structures adjacent, overlay flags
  - three comps from valuation with a one-line reason each, and the comp range
  - verdict line: PASS / LOOK / BID with the one sentence that justifies it, derived deterministically from buy-box rules, never from the LLM
  - "verify before bidding" list: the facts we could not confirm (e.g. water/gas liens are not in our data — say so explicitly)
- pass list: lots excluded by the buy box with the single reason each

render.py — PDF via fpdf (reuse the styling helpers from reports/dossier.py), landscape summary table first, one page per BID/LOOK lot, appendix for PASS. Every red flag and comp line prints its source URL as a footnote.

service.py — `build_packet(session, user_id, sale_date)`: fetches inputs (batched, no N+1: one query per table for the parcel set), composes, renders, stores `packet` row (user_id, sale_date, pdf_path, model_json, generated_at), returns it. Runs as an ARQ job; endpoint POST /packets {sale_date} enqueues and GET /packets/{id} returns status + download URL.

Tests: compose.py with fixture inputs — assert BID/LOOK/PASS decisions and red-flag presence; render smoke test that the PDF opens and has ≥1 page. Run one real packet on the local prod copy for the next upcoming sale date and tell me: lot count, vacant count, BID/LOOK/PASS split, page count, generation time.
```

### Step 1.3 — Postponement / withdrawal alerts and the packet email
Branch: `feat/packet-delivery`

```
[session protocol]

Goal: the packet arrives by email 48 hours before the sale, and the user is told when a lot in it moves.

1. Scheduled ARQ job (daily 09:00 America/New_York): for every user with a buy box and email verified, for every sale_date within the next 3 days that does not yet have a packet for that user, build it and email it (PDF attached + a 5-row summary in the body: BID lots with address, opening bid, MAO). Reuse notifications/digest.py templates.
2. Alert job (runs after the daily scraper): read `sheriff_sale_event` rows since last run; for each user whose latest packet for that sale_date contains the parcel, send one email per sale date listing every change ("1329 GROVE ST — continued to Oct 8", "810 N 42ND ST — stayed"). Idempotent on event id.
3. In-app: GET /packets lists the user's packets; the dossier shows a banner on any parcel with a status change in the last 14 days.
4. Manual trigger for admin: POST /admin/packets {user_id, sale_date}.
5. Test: seed events, assert one email per user per sale date, and none on re-run.
```

### Step 1.4 — The first fifty buyers
Branch: `feat/repeat-buyer-list`

```
[session protocol]

Goal: a list of every repeat vacant-lot sheriff-sale buyer in Philadelphia, with mailing addresses, and a letter for each.

1. Query design (put it in buyers/derivation.py, which already derives cash buyers from deeds): grantees on `sale` rows where document_type = "SHERIFF'S DEED" in the last 24 months, on parcels that were `is_vacant` at the time or are vacant now, grouped by normalised grantee key; keep buyers with ≥2 purchases. For each: name, purchase count, total consideration, their parcels, and the mailing address from OPA on the parcels they now own (the `mailing_street` column — the correct one). Exclude public owners and known institutional plaintiffs.
2. Export: `uv run lotscope buyers repeat --since 24m --min 2 --csv out.csv`.
3. Letter: reuse reports/loi.py / outreach letter rendering to produce one PDF per buyer: page 1 is their own last three purchases graded (by-right, MAO at default assumptions, current red flags, sourced); page 2 says a Sale Packet for the next sale date is free, with a personal link that pre-creates their account (token → register with prefilled email if we have one, else a code). Neutral tone, no sales copy. I will edit the copy; put it in one template file.
4. Report: how many buyers qualify, distribution of purchase counts, how many have a usable mailing address.
```

### OWNER 1.5
- [ ] In Stripe, create two one-time Prices: Sale Packet $49, Lot Diligence $199. Copy the Price IDs into production `.env` as `STRIPE_PRICE_PACKET` and `STRIPE_PRICE_DILIGENCE`.
- [ ] Print and mail the letters from 1.4 (or use Lob/Click2Mail — your call). Send the trial user her packet by hand first.

### Step 1.5 — Two SKUs, nothing else
Branch: `feat/per-deal-billing`

```
[session protocol]

Goal: replace the tier system with two one-time purchases. Nobody has a subscription; delete the machinery.

1. Delete: accounts/tiers.py (limits dicts, FEED_TIERS, PLAN_CATALOG), credit packs (packs.py), credit_ledger service paths (leave the table; drop it in Phase 4), founding-price code, appeal-packet price, every `tier` gate in api/*.py (`@requires_tier`, 429 quota paths for leads/watchlist/pipeline/exports/ask), frontend PricingPlans.vue, UpgradePrompt.vue, tier arrays in every page. `app_user.tier` stays as a column but is only "user" | "admin".
2. Add `purchase` (user_id, sku, stripe_session_id, object_ref e.g. packet id or parcel number, paid_at). Checkout: POST /checkout {sku, object_ref} → Stripe Checkout session; webhook marks paid. A packet PDF download requires a paid purchase for that packet unless the user has `comp_until` (admin-set free-access date — use this for the trial user and the letter recipients).
3. Frontend: one "Get this packet — $49" button on the packet card and a "Diligence — $199" button on the Lot page (the latter is disabled with "coming soon" until Phase 5).
4. Tests: webhook idempotency; download gate.
```

---

# Phase 2: the Analyst

### Step 2.1 — Agent runtime
Branch: `feat/agent-runtime`

```
[session protocol]

Goal: an agent module that runs Claude with tools over our services, persists every step, and streams to the client. This session builds the runtime and two tools; later sessions add tools.

Module backend/src/lotscope/agent/ :
- tools/registry.py: `@tool(name, description)` decorator over async functions with Pydantic input models; registry emits Anthropic tool schemas. Tool descriptions are the model's interface — write them carefully; they are the one place prose belongs in code.
- envelope.py: every tool returns ToolResult{data, sources: list[Source{name, url, fetched_at|computed_at}], unverified: list[str]}. The run loop serialises this to the model verbatim so citations are possible.
- runtime.py: run loop using the Anthropic SDK with tool use, model configurable (default the current Sonnet; `ANALYST_MODEL` env), max 25 tool calls per run, per-run token budget, cancellation. Persists `agent_conversation`, `agent_run`, `agent_step` (tool name, input, result envelope, tokens, ms). Long-running tools (packet build, screens over > 50 parcels) are dispatched to ARQ and the run yields a "working…" step, resuming on completion.
- stream.py: SSE endpoint GET /analyst/runs/{id}/events streaming text deltas, tool-call started/finished (with the envelope's sources), and final. POST /analyst/messages {conversation_id?, text} creates a run.
- system prompt (agent/prompts.py): the Analyst's identity (Philadelphia land acquisitions analyst), the citation rule (every factual claim names its source; anything absent from tool results is "unverified"), the honesty rule (never infer owner motive; say "likely" when the source says likely), the action rule (do the work; ask one question only when a required input is genuinely missing), buy box and owned parcels injected from memory (Step 2.4).
- Two tools to prove the loop: `get_parcel(parcel_number|address)` (wraps parcels service + verdict) and `search_area(polygon|center+radius, filters from buy box)`.

Tests: registry schema generation; run loop with a fake model that emits a tool call then text; envelope persistence; SSE ordering. No real API calls in tests.
Report: a transcript of one real local run for "what's the story on 2138 N Fairhill St" with the step list and token totals.
```

### Step 2.2 — Read tools
Branch: `feat/agent-read-tools`

```
[session protocol]

Goal: the Analyst can answer anything the old dashboard showed, with sources.

Add tools, each wrapping the existing service (never re-implement logic):
- get_verdict(parcel) — buildability, risk, distress, deal signal
- get_zoning(parcel) — district, effective standards with overlay resolution, by-right eligibility for a proposed use/unit count, with Title 14 provision ids
- get_code(provision_id | question) — corpus retrieval (ai/hybrid.py); returns provision text + ids
- get_comps(parcel, radius_m?, months?) — the comp set with inclusion/exclusion reasons
- get_deed_chain(parcel) — RTT deeds with grantor/grantee/consideration/doc ids
- get_violations(parcel) — open vs on-record with case status
- get_delinquency(parcel) — posture, named debtor, attribution reasoning
- get_sheriff_listing(parcel | sale_date) — listing, status, events
- get_neighbors(parcel) — adjacent parcels with owner class (private/public), vacancy, structure flags; assemblage candidates
- get_overlays_and_flags(parcel) — overlays, historic, flood, RCOs
- get_owner_portfolio(parcel | owner_key) — other parcels held by the same owner key
Each tool's envelope lists sources with URLs (Carto/ArcGIS/Atlas/L&I/CivilView) where a public URL can be constructed.

Delete ai/service.py's `ask_the_parcel`, its endpoint, AskBox.vue and the ParcelAnswer schema — the Analyst replaces them. Keep `summarize_parcel` for now (the Lot page uses it) and `draft_parcel_report`.

Eval: create backend/src/lotscope/agent/evals/tasks.yaml with 15 questions on the trial user's six lots and four other parcels, each with the expected tools and 2–3 factual assertions (owner name, deed date, open violation count, by-right answer). `uv run lotscope agent eval` runs them against the real model and prints pass/fail per assertion. Run it and paste the table.
```

### Step 2.3 — Action tools
Branch: `feat/agent-action-tools`

```
[session protocol]

Goal: the Analyst does work, not just answers.

Tools:
- compute_deal(parcel, overrides?) and run_sensitivity(parcel) — buy-box assumptions with per-call overrides; returns MAO, margin, sensitivity table
- screen_sale(sale_date, overrides?) — enqueues the packet build for this user; returns packet id and, when done, the BID/LOOK/PASS summary
- screen_parcels(parcel_numbers | area) — the same screen over an arbitrary set (≤200), returns the summary table
- add_to_pipeline(parcel, stage?, note?) / update_deal(deal_id, fields) / list_pipeline()
- watch(parcel | saved search spec) / unwatch(...)
- draft_loi(parcel, price, terms) — returns the LOI PDF path via reports/loi.py
- draft_letter(parcel | owner_key, purpose) — owner letter via the outreach renderer; never sends
- create_alert(kind: sale_status | new_violation | new_delinquency | neighbor_deed | zba_filing, scope: parcel | area | owned_neighbors) — persisted; consumed by Step 2.5
- export_csv(parcel set, columns)

Every mutating tool records `agent_run_id` on the row it creates. The system prompt gets one line: confirm before sending anything to a third party; everything else, just do it and report.

Frontend hook (temporary until Phase 3): none. Verify via the SSE endpoint with curl and paste one run where the user asks "screen the Sept 10 list against my box and add the BID lots to my pipeline".
```

### Step 2.4 — Live verification tools
Branch: `feat/agent-live-verify`

```
[session protocol]

Goal: for facts a buyer will check, the Analyst reads the primary source at answer time and shows both timestamps.

Tools (all async httpx, 8s timeout, cached in Redis for 15 minutes, failures return unverified rather than raising):
- live_opa(parcel) — Carto opa_properties_public row: owner, mailing, sale_date, sale_price, market_value, land_use
- live_rtt(parcel) — Carto rtt_summary latest 5 documents
- live_li(parcel) — L&I violations/cases for the parcel (Carto li_violations / li_case tables or the ArcGIS layer — pick the one with case status)
- live_sheriff(case_number | parcel) — CivilView detail page status + sale date (reuse the scraper's parsers)
Each returns the live values alongside our stored values with a `diff` list. Envelope sources carry the live URL and fetched_at.

System prompt rule: before stating owner, last sale, open-violation count or sale status, call the live tool; if live and stored disagree, state the live value, note the disagreement, and file a `parcel_correction` row automatically (reuse corrections/service.py) so the ingest catches up.

Test: fake transport fixtures for each; a diff case. Eval: add 5 tasks where the local copy is deliberately stale (edit owner on a fixture parcel) and assert the Analyst reports the live value.
```

### Step 2.5 — Memory and the nightly brief
Branch: `feat/agent-memory-brief`

```
[session protocol]

Goal: the Analyst remembers the user and works overnight.

1. Memory: `analyst_memory` (user_id, kind: fact|preference|decision, text, source_run_id, created_at). The runtime injects buy box + owned parcels + the 30 most recent memory rows into the system prompt. A `remember(text, kind)` tool lets the model store durable facts the user states ("I only buy west of Broad", "I lost 2138 Fairhill at auction last year"). Conversations older than 50 turns are summarised into memory rows.
2. Signals: a nightly ARQ job builds `signal` rows per user from: sheriff_sale_event, new delinquency or violation on parcels adjacent to owned_parcels, new deed on adjacent parcels, new ZBA filing within buy-box areas, new listing within buy-box areas passing the box, alerts from create_alert. Idempotent on (user, signal key).
3. Brief: a second job runs the Analyst in "brief mode" per user with the day's signals as input and a fixed instruction: ≤8 items, most actionable first, each with the source; no item without a signal behind it; end with "nothing else changed" if true. Store as `brief` (user_id, date, text, run_id); email it at 07:00 America/New_York; GET /briefs lists them.
4. Test the signal builder with fixtures; run one real brief for the trial user's profile on the local copy and paste it.
```

### Step 2.6 — Analyst eval on PRs
Branch: `ci/agent-eval`

```
[session protocol]

Goal: prompt or tool changes cannot silently degrade answers.

1. `uv run lotscope agent eval --record` snapshots tool-call sequences and assertion results for tasks.yaml into evals/baseline.json.
2. A nightly workflow runs the eval against the real model with a spend cap and posts the pass-rate delta; a PR touching agent/ runs a 10-task subset.
3. Grow tasks.yaml to 40 tasks: the trial user's lots, the ten highest-distress vacant lots in Mantua, five city-owned lots (must say "public disposition, not a private sale"), five with stale OPA owners (must report live), five non-vacant parcels (must decline to price as land).
```

---

# Phase 3: three screens

### Step 3.1 — Routes and deletions
Branch: `refactor/three-screens`

```
[session protocol]

Goal: the frontend has five routes. Everything else is deleted this session, even if the replacement is not pretty yet.

Routes: `/` (Analyst), `/lot/:parcelNumber`, `/deals`, `/account`, `/admin`, plus `/login`, `/register`, `/verify`, `/legal/:slug`.

Delete pages: LandingPage (replace with a 1-screen static page at `/welcome` with one paragraph and a sign-in button), HomePage, ExplorePage (map moves into the Lot page and an Analyst drawer), FeedPage, TopPlaysPage, BuyersPage, BuyerProfilePage, MarketPage, MarketHealthPage, ListsPage, LeadsPage, SheriffSalesPage, OpsPage (fold the ingest status table into /admin), and their spec files.
Delete components: AssemblagePanel? NO — keep as a Lot section. Delete: BuyBoxOnboarding, BuyBoxPanel, BuyersNearbyPanel, CompareTable, CompareTray, DiscoverySources, FirstSteps, HeroShowcase, MarketContextPanel, MarketSwitcher, MobileTabBar, OnboardingTour, PricingPlans, SavedSearchesList, UpgradePrompt, WhyScoreDrawer, AskBox, DataCoverageChip, AssessmentPanel (appeal product is gone), ReportPanel, NextAction. Delete stores: compare, credits, filters, firstSteps, market, push, savedSearches (watching is an Analyst action now; keep watchlist store only if the Lot page needs it). Delete public/sw.js and push registration.
Backend: delete api routers feed, buyers (keep buyers/derivation for the repeat-buyer export), neighborhoods, digests (replaced by briefs), push, exports if only used by deleted pages, policies if unused; delete modules feed, compare, neighborhoods, assessment, appeal, market, goldset, savedsearch (watch subsumes it — migrate any real rows into watchlist first), notifications/push.py and vapid_keys.py.
Keep AppShell/AppSidebar/AppTopBar but reduce the sidebar to Analyst / Deals / Account.
Run vue-tsc and the Playwright suite; delete e2e specs for removed pages and fix the rest. Report route count, component count, store count before/after.
```

### Step 3.2 — The Analyst screen
Branch: `feat/analyst-ui`

```
[session protocol]

Read /mnt/skills/public/frontend-design/SKILL.md if present in this environment; otherwise design with restraint: one typeface, dense, no marketing chrome.

Goal: `/` is a conversation with the Analyst, and it feels like working with a person who has the files open.

- Left: conversation list (today's brief pinned at top, then conversations). Center: the thread. Right: an evidence drawer.
- Messages stream (SSE from Step 2.1). Tool calls render as compact cards ("Checked OPA live · 2 fields differ", "Screened 41 lots · 6 BID") that expand to the envelope: data table + sources with links. Every source link either opens the Lot page in the drawer (internal) or the primary source in a new tab (external).
- Attachments: packets, LOIs, letters and CSVs the Analyst produced show as file cards with download.
- Composer: text, plus two shortcuts that just insert text: "Screen the next sale" and "What changed on my lots".
- Brief view: the nightly brief renders as a message with each item's source card.
- Empty state on first visit: the Analyst opens with one message asking for the buy box if none exists, then offers to screen the next sale date. Implemented by a server-side first-run, not client copy.
- Mobile: single column, drawer becomes a bottom sheet. Tap works for everything; no hover-only affordances anywhere.
Vitest: composer, tool-card expand, source routing. Playwright: send a message with a mocked SSE stream, open a source in the drawer.
```

### Step 3.3 — The Lot page
Branch: `feat/lot-page`

```
[session protocol]

Goal: `/lot/:parcelNumber` is the evidence page. Every fact has a "Show me" that opens the source.

Sections, in this order, nothing else: header (address, parcel, owner with live-verified badge and fetched_at), map (MapView.vue, this parcel + neighbours colour-coded private/public/owned-by-you), Verdict (buildability with dimensional table and Title 14 cites; risk flags; distress with factors; deal: MAO/margin/sensitivity under the user's buy box, editable inline), Sheriff listing + events if any, Deeds, Violations (open vs on-record), Delinquency (posture + named debtor + reasoning), Comps (with reasons), Zoning & overlays, Neighbours/assemblage, Corrections (report + status).
"Show me" on a fact opens: the deed document link (RTT doc id → Atlas/Recorder URL where constructible), the L&I case URL, the Title 14 provision text from the corpus in a popover, the CivilView listing, or the Carto row. Where no public URL exists, show the stored source name and the as-of timestamp.
"Ask the Analyst about this lot" button opens `/` with the parcel preloaded in context.
Buttons: Add to Deals, Watch, Diligence ($199, disabled until Phase 5).
Delete VerdictHero/VerdictPanel duplication — one verdict section. Delete SnapshotPanel if the LLM summary adds nothing over the verdict section; otherwise keep it as a collapsed "in plain words".
Playwright: open a lot, expand a Show-me, edit an assumption and see MAO change.
```

### Step 3.4 — Deals
Branch: `feat/deals-page`

```
[session protocol]

Goal: `/deals` is a list, not a board. Stage as a dropdown, next action, MAO vs offer, sale date if any, last Analyst note. Bulk actions: export, ask the Analyst about selected. Delete the drag-and-drop board and DealCard's kanban mode; keep GenerateOfferDialog (LOI). Mobile-first table.
```

---

# Phase 4: compute on read, prune tests

### Step 4.1 — No versions, no sweeps
Branch: `refactor/compute-on-read`

```
[session protocol]

Goal: a verdict is computed when read and cached on its inputs. There is no stored verdict that can be stale.

1. verdict/service.py: `get_verdict(parcel)` computes from current inputs and caches in Redis for 24h under a key that is the hash of (parcel.updated_at, max(sale.updated_at), max(li_event.updated_at), tax_status.updated_at, zoning inputs' updated_at, code git SHA). Any write to those tables for a parcel deletes its key (add an `invalidate_parcel(parcel_number)` called from the ingest merge step).
2. Delete: VERDICT_VERSION, DECISION_VERSION, distress profile versions, verdict/jobs.py sweeps and `--only-stale`, scripts/verify_v11.py, goldset module, all `pre_*` baseline tables (migration drops them), trust.py if it only reasons about versions.
3. Keep `parcel_distress` as a nightly-rebuilt index because search and the packet filter on score; it is rebuilt fully every night (measured ~6 min) and is never asserted to a user without the live compute. Same for any stored `opportunity_score` used for ranking.
4. AI summary cache: key on the verdict cache key + prompt version + model; delete the manual purge tooling.
5. Verify: read a parcel, change a violation row, read again, assert the verdict changed without any job. Report p50/p95 compute time on 50 parcels.
```

### Step 4.2 — Prune the test suite
Branch: `chore/prune-tests`

```
[session protocol]

Goal: the suite covers money math and the Analyst, runs fast, and nothing else.

Keep and, where thin, strengthen: zoning dimensional eligibility and overlay resolution, deal/MAO/sensitivity, delinquency attribution and party matching, comp selection and exclusion, parcel-key reconciliation, ingestion row mappers for the Philadelphia loaders (one test per carried column), packet compose, agent registry/runtime/envelope, live-verify diff logic.
Delete tests for anything removed in Phases 0–3 and any test that asserts prose, layout, or version strings. Delete the golden-set fixtures.
Report suite size and wall time before/after. Target: unit < 60s, integration < 3 min.
```

---

# Phase 5: Diligence, off-market, then a plan

### Step 5.1 — Lot Diligence
Branch: `feat/lot-diligence`

```
[session protocol]

Goal: a pre-closing checklist on one parcel, produced by the Analyst with the live tools, honest about what our data cannot see, sold at $199.

diligence/ module: a fixed checklist schema — title chain (RTT deeds, gaps flagged), delinquency and named debtor (live), L&I open + case status (live), unsafe/ID structure adjacency, Act 135 / conservatorship signals if any source exists (if none, the line says "not in our data — check Court of Common Pleas"), historic designation, overlays and RCOs, flood, public-owner adjacency and Land Bank disposition status, estate/probate signals in grantor strings, party-wall and lot-line notes from PWD geometry (shared boundaries with structures), utilities/curb (say "not in our data" if not), and a closing block: "Order a title search and a municipal lien letter before closing; we do not see Water Revenue or PGW liens." Each line: status (clear / flag / unverified), evidence, source, fetched_at.
The Analyst runs it via a `run_diligence(parcel)` tool → PDF via the packet renderer's styles → purchase gate from Step 1.5 → download.
Eval: 5 parcels including one with a known open case and one with a public-owner neighbour.
```

### OWNER 5.2
- [ ] Open a BatchData account, accept terms, get the API key; note the 30-day cache clause. Set `SKIPTRACE_PROVIDER=batchdata`, `SKIPTRACE_API_KEY`.

### Step 5.2 — Off-market outreach through the Analyst
Branch: `feat/outreach-agent`

```
[session protocol]

Goal: the Analyst can find and contact owners, with the law built in.

1. skiptrace: BatchData client behind the existing protocol; DNC + litigator scrub on every hit; cache ≤30 days; no-hit costs nothing to the user (we absorb it — no credit ledger).
2. outreach: sequences (letter → letter+14d → email if we have one) stored per parcel with status; CAN-SPAM footer and opt-out on email; no SMS or calls at all. Sending requires an explicit user confirmation in the conversation ("Send to these 12?"); the Analyst never sends unprompted.
3. Tools: trace_owner(parcel), start_outreach(parcel set, sequence), outreach_status(). Replies logged by a Mailgun inbound route into the conversation as a signal.
4. Pricing: one-time $1 per traced owner charged via the purchase table at confirmation time (Stripe Price created by you when we get here).
```

### Step 5.3 — The monthly plan (only when ten per-deal purchases exist)
Not scheduled. When `purchase` has ten paid rows from at least five users, come back and add one Stripe subscription price ("Analyst", proposed $199/month): unlimited packets, briefs, diligence at a discount. Until then, do not build subscriptions.

---

## What is deliberately not on this list
- Any second market.
- Push notifications, PWA, mobile app.
- Tiers, credits, founding offers, appeal packets, buyer intelligence pages, market health, feed, top plays, compare.
- Version bumps, sweeps, golden sets, ADRs, handoffs longer than ten lines.
