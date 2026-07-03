# 38. Sheriff-sale calendar

Date: 2026-07-03

## Status

Proposed

Gates PRD-amendment-01 feature **A4** (Phase 4). Depends on ADR-0036 (raw→staging→merge + `parcel_event`) and ADR-0037 (Deal Feed read model); extends §5.5 risk/due-diligence, ADR-0015 (distress index) and ADR-0017 (change taxonomy — the `sheriff_sale` code); tier-gated per ADR-0030; nav slot per ADR-0029.

## Context

We already carry a coarse `in_sheriff_sale` boolean on `tax_status`, sourced from the Revenue tax-delinquency dataset, and it drives a risk flag and a `sheriff_sale` Deal Feed event. What it does **not** tell a user is *when* the auction is, *which case* it is, or *what the opening bid is* — exactly the facts auction-prep buyers need. Auction-prep is a proven standalone SKU ($40–200/mo elsewhere); A4 turns our boolean into a dated, ranked calendar.

The amendment flagged the open risk as **"sheriff list acquisition mechanics and stability of the source format."** Investigation resolves it:

- **Upstream source: CivilView `salesweb.civilview.com` (`countyId=60` = Philadelphia).** Server-rendered HTML — a filterable list (by status, sale month/date, address) plus a per-property detail page. Each list row carries **Book & Writ (case number), OPA #, address, plaintiff**; the detail page adds **sale type, status, sale date, opening bid**. ~1,600 open listings at time of writing. The list is also exportable as CSV from the same system.
- The consumer site `phillysheriff.com/services/list-of-properties/` is a bot-protected Bid4Assets/CivilView embed (returns 403 to a plain fetch, JS-rendered). It is **not** an acquisition target; CivilView is the same data upstream and is scrapable/exportable.
- **The row carries an OPA number.** This dissolves most of the reconciliation risk the amendment anticipated: we map OPA # → `parcel_number` with the existing `normalize_account`, address only as a fallback. Sheriff sale records are public record.

Two properties of the source shape the decision. It is **fragile** (HTML scraping breaks when a vendor re-skins) and it is **third-party** (scrape ToS/robots must be honored, §13). So we must not couple the rest of the feature to the scrape.

## Decision

**Build A4 as a staged Carto-free loader on the ADR-0036 path, decoupling the record contract from acquisition, with the Sheriff's Office as the authoritative source of the dated `sheriff_sale` event.** Four slices, each independently tested and committed.

### 1. Acquisition — contract first, scraper behind an interface

Define a normalized `SheriffSaleRecord` (case_number, opa_number, address, sale_type, status, sale_date, opening_bid, plaintiff). A `SheriffSource` interface yields those records; the loader consumes the stream and is blind to where they came from. Two adapters:

- **File/CSV adapter (built first).** Reads a CivilView CSV export from a configured path. Deterministic, fully fixture-testable, unblocks merge + API + frontend immediately, and is the **operational fallback**: if the scraper breaks, ops drop a CSV and the daily job still runs.
- **CivilView HTML adapter (follow-up, same interface).** Fetches the list (paged by sale-month filter) + detail pages via the existing `http.py` retry/backoff client, parses HTML → `SheriffSaleRecord`. Parsing is a **pure, fixture-tested** function over saved HTML, isolated from the fetch. Adding an HTML-parser dependency (`selectolax`/`lxml`) is gated by §15 review at that slice, not now.

This is the "third fetch style" the amendment predicted, fully contained in the loader — Carto/ArcGIS clients are untouched.

### 2. Data & merge (staged, per ADR-0036)

- **Core `sheriff_sale`** (owned by the **`risk`** module, beside `tax_status`/`li_event`/`flood_zone`): `id, parcel_number FK, case_number, sale_type, sale_date, status, opening_bid NUMERIC NULL, plaintiff, + IngestionMixin + TimestampMixin`. Natural upsert key **`case_number`** (unique per writ); a postponement updates `sale_date`/`status` on the same case rather than inserting a duplicate.
- `staging.sheriff_sale` (the fetch↔merge contract) + `raw.raw_record` landing (dataset `sheriff_sale`).
- **`merge_sheriff`** diffs staging vs core and upserts, reusing the L&I/RTT **new-row detector + first-load baseline** (`EXISTS (SELECT 1 FROM sheriff_sale)` guards against a spurious event per row on the first ever load).

### 3. Event emission — A4 owns `sheriff_sale`

`merge_sheriff` emits the authoritative, dated `sheriff_sale` **HIGH** event when a new case appears for a parcel: `new_value = {case_number, sale_date, sale_type, opening_bid}`, `dataset = "sheriff"`. **The tax `diff_tax` sheriff branch is removed** so the same underlying sale is not double-counted in the Deal Feed; the `in_sheriff_sale` boolean stays on `tax_status` for the risk score, but the feed event's single, authoritative provenance is now the Sheriff's Office (a real case number and date), not a coarse Revenue flag. The `<30-day imminent` distinction is a **read-time badge** computed from `sale_date` on the dossier/feed, not a separate event. Postponement/relisting events are a follow-up.

### 4. Reconciliation, API, frontend

- **Reconciliation:** OPA # → `normalize_account` → `parcel_number`. Rows with no resolvable parcel are retained in `raw` but skipped from core + events (address-match is a follow-up). Tested as a first-class concern (§11).
- **API:** `GET /sheriff-sales?from=&to=&zip=` (Pro+ gated, ADR-0030), joining `sheriff_sale` → `parcel` → `parcel_verdict`, ranked by `verdict.max_allowable_offer − opening_bid` (higher = better deal) where `opening_bid` is present, nulls last. Composition/ranking in a service; router thin; pagination consistent with feed/search.
- **Frontend (last slice):** Pro+ sidebar item → calendar/list page at `/:market/sheriff-sales`; a sale-date countdown chip on the parcel dossier. Store + `lib`, per ADR-0029.

### Scheduling

New `sheriff` entry in `INGEST_JOBS`; runs inside the daily `ingest_all` (and thus emits events through the same merge path). The retention sweep (ADR-0036) already covers the new `raw`/`parcel_event` rows.

### Verdict impact

**None this slice.** Sheriff timing enriches the risk flag *detail* and powers the new endpoint/feed; the risk **score** and the verdict contract are unchanged, so no version bump and no recompute. Folding imminent-sale timing into the risk/distress score is a deliberate follow-up (its own ADR + recompute) if the signal proves predictive.

## Consequences

- **The last Deal Feed code goes live.** `parcel_event` now covers tax + L&I + OPA + RTT + **sheriff**, and the sheriff event finally carries a date and case number instead of a bare boolean — a materially better feed entry and the seed of the auction-prep SKU.
- **A behavior change lands in tax ingestion:** `diff_tax` no longer emits `sheriff_sale`, and its tests change. The risk score is unaffected (it still reads `in_sheriff_sale`). Deal Feed history from before cutover keeps its old tax-sourced sheriff events; new ones come from A4.
- **Source fragility is contained, not eliminated.** The CSV/file adapter keeps the feature operational independent of the scraper, and the pure HTML parser is fixture-tested; but a CivilView re-skin still requires a parser update. Freshness tracking + loud failure (§14) make a broken scrape visible rather than silently stale.
- **Compliance:** scraping CivilView must honor robots/ToS; the CSV-drop path is the safe default and the scraper is added only after that check. Sheriff-sale data is public record; product output stays informational (§13).
- **New surface to own:** a `sheriff_sale` table + read service in `risk`, a new loader/merge in `ingestion`, one API endpoint, one frontend page. All follow existing patterns (staged loader, thin router, market-scoped page), so the marginal complexity is low.
- **Deferred:** the live CivilView scraper (slice-2 follow-up behind the same interface), address-based reconciliation for OPA-less rows, postponement/relisting events, and folding sheriff timing into risk scoring.
