# PRD Amendment-02 §5 — discrepancies vs. the actual codebase (Slice 0 recon, 2026-07-05)

The PRD was written 2026-07-04; the codebase moved since. This records where PRD §5's "current behavior" statements no longer match, so the Wave-0 prompt and the Phase-P slices work from reality. It corrects nothing in the PRD (a draft); it annotates it.

## Numbering / versioning

- **ADR numbers are stale.** PRD proposes ADR-0029–0034; all are taken (0029 = "App shell and market scope", latest is 0050). Phase P authors **0051** (B1), **0052** (B2), **0053** (B3/B4). Wave ADRs continue from 0054.
- **`VERDICT_VERSION` is `v8`, not `v5`.** PRD B9 plans folding into "Amendment-01's v6 bump" — that ship has sailed (v5→v8 across sessions). **Phase P bumps nothing** (per the Phase-P exit criterion); expansion field additions ride the next batched bump whenever one is next warranted.

## Market primitive already partly exists

- `core/markets.py` defines `Market(StrEnum)` with a single member **`philadelphia`** + `DEFAULT_MARKET`; `/search` accepts a cosmetic (unfiltered) `market` query param.
- The frontend shipped `/:market/...` routing, a market store, and a router guard (ADR-0029) — all using the string **`philadelphia`**, not `phl`.
- **Consequence:** the PRD's short codes (`phl`, `pgh`, …) collide with the shipped `philadelphia`. ADR-0051 resolves this as **code=`phl` + `url_slug='philadelphia'`** (decision to confirm). Any Wave prompt must use the short code as the canonical key prefix and the slug for URLs.

## B1 (parcel key) — reality is broader than the PRD list

- PRD lists 9 child tables; the actual FK graph is **14 CASCADE FK tables + 6 non-FK `parcel_number` columns** (staging + `zba_appeal`), and `sheriff_sale`/`li_event` are each defined twice (staging + core). New tables since the PRD: `zba_appeal`, `deed_restriction`, `appeal_packet`, `parcel_event`, `parcel_assemblage`.
- `normalize_account` (the canonical-key generator) hard-rejects >9 digits — must be rewritten (B4).
- Colon hygiene: Redis keys and MVT properties are colon-safe (no `.split(':')` anywhere); PDF filenames need `:`→`-` sanitization.

## B2 (geometry) — 17 spatial queries, not "a handful"

- 8 `geom_2272` tables; **17 cross-parcel/context spatial queries** catalogued (see ADR-0052). New since PRD: zoning-overlay/RCO intersects (ADR-0040), subdivision adjacency (via assemblage), neighborhood market-stats. MVT functions are richer (`f5b2d8c1a9e7_parcels_mvt_rich_verdict` carries verdict scores).

## B3 (ingestion) — the raw-landing layer already exists

- PRD says raw capture was "deferred in ADR-0004" and should be built with `ExtractClient`. **It already exists** (`raw` schema, `RawRecord`, `write_raw`, `staging.*`, `merge.py`; `opa/tax/rtt/li/sheriff` write through it). So `ExtractClient` writes *through* it — no new raw path needed (ADR-0053 records this).
- 17 `INGEST_JOBS` (not "thirteen"): the PRD-era 13 plus `zoning_overlays`, `rco`, `historic`, `zba`.
- `dataset_freshness` PK is `dataset` alone — no market dimension (blocker, addressed B3).

## B10 (frontend scope) — mostly as described

- Frontend market routing shipped; only `/search` sends `market` (cosmetic). `/search/area`, `/leads`, saved-search carry no market. Map constants live only in `MapView.vue` (center `[-75.1652, 39.9526]`, zoom 13 init / 11.5 reset; **no `maxBounds`/`fitBounds` exist** — the `map_bounds` market field will be new, not lifted).

## Deploy / CI (not in PRD scope, but gates Phase P)

- **No deploy automation in the repo**; deploy is a **VM-side git-pull + docker-compose** on push to `main`. **Nothing runs `alembic upgrade head` on deploy** — the api Dockerfile just runs uvicorn. Slice 0 adds a one-shot `migrate` step to the deploy path so migration-bearing slices (esp. B1) apply on deploy.
- CI (`ci.yml`) runs backend lint/type/unit + PostGIS integration + web on every PR and push-to-main; solid. Slice 0 adds `feat/**` to push triggers for pre-PR feedback.
