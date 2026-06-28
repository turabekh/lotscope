# 21. One-click PDF dossier

Date: 2026-06-28

## Status

Accepted

## Context

PRD §5.10 — a one-click **branded full parcel report** (PDF) that packages the verdict, property facts, risk, assemblage, and distress into a shareable document. The main decision is how to render the PDF server-side.

## Decision

**Server-side PDF with `fpdf2`, composed from the existing engine results.**

- **`fpdf2`, not WeasyPrint.** WeasyPrint produces nicer HTML/CSS output but needs native system libraries (pango/cairo/gdk-pixbuf) that complicate local and Docker installs. `fpdf2` is a pure-Python wheel with no system dependencies, so the dossier builds reliably everywhere. The trade-off — a programmatic, fixed layout instead of HTML/CSS — is acceptable for a structured one/two-page report.
- **`reports` module composes services, owns no domain truth.** `build_parcel_dossier` gathers `ParcelDetail`, the verdict (computed on demand and cached if not yet present), `compute_assemblage`, and `assess_parcel_distress`, and hands them to a pure `render_dossier_pdf` that draws a branded header band, the opportunity score, buildability/value/risk, property facts, assemblage, and the distress index, with an informational disclaimer footer.
- **Latin-1 sanitization.** fpdf2's core fonts are Latin-1; a `_s()` helper maps the unicode we emit (em dash, arrow, ©, smart quotes) to ASCII so any field (risk-flag details, assemblage "1 -> 6") renders without bundling a TTF font.
- **Endpoint:** `GET /parcels/{id}/dossier` (auth) returns `application/pdf` with a `Content-Disposition: attachment` filename. The frontend downloads it as an authenticated blob and triggers a save; a "PDF dossier" button sits on the parcel panel.

## Consequences

- **No native dependencies** — the report works in dev (uv) and the Docker image without extra OS packages.
- **Generating a dossier computes the verdict if missing** (and commits it), so the report always has a verdict; a side effect consistent with caching.
- **Ungated for now** — available to any authenticated user. PRD §5.14 envisions metered "report credits"; tier-gating or metering can wrap this endpoint later without touching the renderer.
- **Fixed layout.** Richer, themeable reports (investor/lender package, standalone comp report, feasibility pro-forma — §5.10) and white-label branding would likely move to an HTML-template renderer (WeasyPrint/headless) behind the same `reports` service interface.
- **Deferred:** shareable live web links, CSV/Excel export, scheduled/auto reports, and co-branded templates.
