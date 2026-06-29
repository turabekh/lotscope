# Session handoff — 2026-06-29

A working note for the next session. Not an ADR (no decision here); just state + next steps. Delete or trim once consumed.

## What shipped this session (all on `main`, pushed)

1. `feat(savedsearch)` — saved searches + new-match email/push alerts (ADR-0024). Pro-tiered (`saved_search_limit`). Daily worker job `send_saved_search_match_alerts`.
2. `test(notifications)` — golden-file test for the saved-search alert email.
3. `feat(search)` — spatial **area search** (ADR-0025): `POST /search/area` with radius (`ST_DWithin`), polygon (`ST_Intersects`), and neighborhood shapes; `GET /neighborhoods`.
   - Radius UI (click center + slider, generated GeoJSON circle).
   - Freehand polygon draw via **terra-draw** (`terra-draw` + `terra-draw-maplibre-gl-adapter`, pinned).
   - Named-neighborhood search backed by a new `neighborhood` table + ArcGIS ingest job (`neighborhoods`); 57 areas ingested from the City `Philadelphia_Neighborhoods` service.
4. `feat(owners)` — owner portfolio (`GET /parcels/{id}/owner-portfolio`) + dossier panel. Matches on normalized owner string.
5. `feat(documents)` — **deed-restriction RAG Phase 1** (ADR-0026): `deed_document` + `deed_restriction` tables; LLM `extract_restrictions`; `process_deed_text` pipeline embeds deed text into the shared `document` store as `source='deed'`, parcel-scoped via `doc_metadata`; `ask_the_parcel` now retrieves+cites parcel deeds; `GET /parcels/{id}/deed-restrictions` + dossier panel. OCR/blob/source behind protocols, mocked in tests.
6. `feat(admin)` — admin console (`/admin` overview/datasets/users + `PATCH /admin/users/{id}`), role-gated; frontend Admin page (admins only).

State: backend **420 tests** + frontend **23 tests** green; ruff/mypy/eslint/vue-tsc clean; prod build OK. Local dev DB has the full ~550k-parcel dataset, 57 neighborhoods, and one demo deed restriction on parcel `011001560`.

## Next steps / open decisions (each needs your call or external setup)

- **Deed-RAG Phase 2 (your env):** install the optional extra (`uv sync --extra ocr` → pulls `paddleocr`/`paddlepaddle`/`boto3`), set Voyage + Anthropic keys, run `python -m lotscope.documents.cli <parcel> <deed.pdf>` to exercise the real OCR→extract→embed pipeline. Couldn't run here (heavy model + keys). Then add a worker job + MinIO/S3 `BlobStore` wiring.
- **Deed-RAG Phase 3 (decision + ToS):** the DOR-portal `DeedSource` harvester. Needs a ToS/legal review and live portal access; I can't validate the portal from here.
- **Access / easements flags (§5.5, Differentiator):** the cleanest remaining *autonomous* build **iff** derivable from existing data (e.g. landlocked detection via PWD parcel geometry + street adjacency). Verify a data basis first; otherwise needs a source.
- **Utilities proximity (§5.2):** needs a water/sewer/electric/gas data source (not ingested) — a data-source decision.
- **Lot-condition CV (§5.2):** needs an imagery source + ML model/provider decision.
- **Smaller follow-ups:** fuzzy/normalized owner matching (today exact-string, so spelling variants split a portfolio); swap neighborhoods to the finer ~158-area Azavea set (one loader URL change — changes the data source); `MapPage` bundle is ~990 kB (gzip ~270 kB) → consider `manualChunks`; area search doesn't auto-refresh when the map's "Vacant only" toggles on an active circle.

## How to resume the app

`make up` (db/redis/martin) → `make migrate` → `make dev` (api :8000 + web :5173). Promote yourself to admin to see the console: `UPDATE app_user SET role='admin' WHERE email='turabekh@gmail.com';`.
