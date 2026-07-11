# 63. CivilView HTML adapter — addendum to ADR-0038

Date: 2026-07-12

## Status

Accepted (adapter shipped) · Proposed (hardening scope)

Addendum to ADR-0038 (sheriff-sale calendar). Records what the CivilView HTML adapter actually shipped as, the
§15 dependency review, and the small remaining hardening — so the deal-closing batch's "Slice 5" does **not**
rebuild a live feature.

## Context — drift

ADR-0038 specified the CivilView HTML adapter as a slice-2 follow-up behind the `SheriffSource` interface. That
adapter was **built, merged, and deployed earlier this session** (`main` @ `3c6655e`, prod `/health` verified):
`ingestion/loaders/sheriff_civilview.py` with pure fixture-tested parsers, a session-cookie-primed fetch adapter,
the `SHERIFF_SALE_SOURCE=csv|civilview` toggle, a `("phl","sheriff_sale")` cadence entry, INGEST_JOBS wiring,
the 05:30 failure alert riding generic freshness, an admin coverage spot-check (`POST /admin/ops/sheriff-coverage`),
and `docs/runbook.md`. Live-verified against CivilView (~97% of ~1,483 listings reconcile to phl parcels).

So the batch's F3 is **largely done**. This addendum records the acquisition decisions retroactively and scopes
only the genuine gaps.

## Decision

### 1. Dependency review (§15) — `selectolax`

The HTML parser dependency resolved to **`selectolax`** (lean, C-based lexbor binding) over `lxml`: ample for
CivilView's regular list + detail markup, smaller footprint, no XML/XPath surface we don't need. Parsing is a
**pure function over saved HTML**, isolated from the fetch, so a re-skin is a fixture-and-parser change, not a
network change.

### 2. Acquisition discipline (as shipped)

Single GET to `/Sales/SalesSearch?countyId=60` returns the **entire** open-listing set (~1,500 rows) in one
response; each row's detail page is then fetched, **primed by a session cookie the list response sets** (detail
pages 302 to home without it), paced by `SHERIFF_SALE_CIVILVIEW_REQUEST_DELAY_SECONDS`. OPA# → canonical key via
the existing normalizer; robots.txt is 404 (no restriction); scrape stays low-volume and ToS-honoring; CSV
adapter remains the default and the operational fallback (runbook §"If the scrape breaks").

**We deliberately do NOT add sale-month list paging** (ADR-0038's original slice-5 idea). CivilView returns the
full county list in one request and is not paginated in a way we benefit from; a month-filter loop would add
request volume and a second failure mode for no coverage gain. If CivilView ever caps or paginates the list,
revisit — until then the single-request fetch is simpler and correct.

### 3. Remaining hardening (the only F3 work in this batch)

1. **Skipped-row observability** — the loader silently `continue`s on malformed / OPA-less rows; add a
   **skipped-and-counted** tally surfaced in the ingest run report (`IngestRun`), so a parser drift shows up as
   a rising skip count rather than silent shrinkage. (The admin coverage endpoint measures reconciliation, not
   per-run drops — distinct concern.)
2. **Test gaps** (parsing logic already handles these; only assertions are missing): a **POSTPONED status
   transition** updating the same `case_number` on a second load, and a **missing-opening-bid detail fixture**
   exercised end-to-end.
3. **Demo row** — after the first verified live load on prod, delete the manually-inserted demo row
   (`DELETE FROM sheriff_sale WHERE case_number='BW-DEMO-01';`), gated on explicit confirmation, as a post-deploy
   step. It exists only on prod/dev manually — no repo seed.

## Consequences

- **Slice 5 collapses from "build the scraper" to a small hardening pass** — no rebuild, no new dependency
  decision, no re-derivation of the parser. This is the batch's cheapest slice.
- **The one intentional divergence from ADR-0038 (no sale-month paging) is recorded with rationale**, so it
  reads as a decision, not an omission.
- **Activation stays a dormant env flip** (`SHERIFF_SALE_SOURCE=civilview` on the VM) documented in the runbook;
  this addendum does not change activation.
- **`VERDICT_VERSION` unaffected** — F3 is a data source for an existing table.
