# Production activation runbook

Several features ship **built but dormant**, gated by an env value on the VM (`~/lotscope/.env`) rather than
code. Flipping one is an owner action: edit `.env`, recreate the services that read it, verify. This runbook
documents those activations. For email specifically see [email.md](email.md); for pricing/skip-trace env keys
see the tables in [.env.example](../.env.example) and ADR-0030 / ADR-0060.

Deploy itself is a separate, manual step (`gh workflow run deploy.yml` → SSH → `~/lotscope/deploy.sh`), and
**does not** change these flags — it only ships code. Activations below are `.env` edits applied by recreating
containers, no redeploy required.

---

## Sheriff-sale live source (`SHERIFF_SALE_SOURCE`) · ADR-0038

The Philadelphia sheriff-sale calendar reads the `sheriff_sale` table. That table is populated by the daily
`sheriff` ingest job, whose acquisition adapter is chosen by `SHERIFF_SALE_SOURCE`:

| Value | Adapter | Behavior |
|---|---|---|
| `csv` *(default)* | `CsvSheriffSource` | Reads a CivilView CSV export from `SHERIFF_SALE_CSV_PATH`; if that path is unset the job is a **no-op** (the calendar stays honest-empty). The operational fallback. |
| `civilview` | `CivilViewSheriffSource` | Scrapes the live CivilView list + detail pages (county `SHERIFF_SALE_COUNTY_ID`, phl = 60), reconciles OPA # → parcel, upserts `sheriff_sale`, emits `sheriff_sale` Deal Feed events. |

Supporting keys (all have safe defaults — see [.env.example](../.env.example)): `SHERIFF_SALE_COUNTY_ID`,
`SHERIFF_SALE_CIVILVIEW_BASE_URL`, `SHERIFF_SALE_CIVILVIEW_REQUEST_DELAY_SECONDS`,
`SHERIFF_SALE_CIVILVIEW_DETAIL_LIMIT` (blank = no cap; set a small integer only for a smoke run).

### Before you flip — check coverage

The calendar only lands rows for listings whose OPA # matches a parcel already loaded in the DB. Confirm that
rate on prod first: **Ops dashboard → Sheriff-sale coverage → Run coverage check** (admin-only; live regardless
of this flag). Healthy is ~97% reconciled. A low number means the phl parcel load is incomplete — fix that
before relying on the calendar.

### Activate

On the VM, in `~/lotscope`:

```bash
# 1. Set (or update) the flag — idempotent
grep -q '^SHERIFF_SALE_SOURCE=' .env \
  && sed -i 's/^SHERIFF_SALE_SOURCE=.*/SHERIFF_SALE_SOURCE=civilview/' .env \
  || echo 'SHERIFF_SALE_SOURCE=civilview' >> .env

# 2. Recreate the services that read it (api serves the calendar, worker runs the job)
docker compose --profile app up -d api worker

# 3. Confirm
grep '^SHERIFF_SALE_SOURCE=' .env
```

The job runs inside the daily `ingest_all` (worker cron 04:00). To populate immediately instead of waiting:

```bash
docker compose --profile app run --rm api make ingest DATASETS=sheriff
```

### Verify

```bash
docker compose --profile app exec db \
  psql -U lotscope -d lotscope -c "SELECT count(*), max(sale_date) FROM sheriff_sale;"
```

Then load `/philadelphia/sheriff-sales` — the per-market state flips from `empty` to `live` once dated rows
exist (`markets/capabilities.sale_calendar_state`).

### Expect on first run

- A **burst of `sheriff_sale` Deal Feed events** — one per newly-seen case (~1,400+ parcels). Expected: that
  is the feature. The first-load baseline guard (`EXISTS (SELECT 1 FROM sheriff_sale)`) means the *very first*
  load does not spuriously event every row, but subsequent new cases do event.
- Listings whose OPA # does not resolve to a loaded parcel are retained in `raw` and skipped from core/events
  (address-match is a deferred follow-up). ~5 listings carry no OPA # at all and are skipped.

### Rollback

Set `SHERIFF_SALE_SOURCE=csv` (or remove the line) and `docker compose --profile app up -d api worker`. Rows
already written to `sheriff_sale` remain; the job simply stops refreshing from the scrape. No migration, no
verdict impact (VERDICT_VERSION unaffected — the calendar reads existing forced-sale data).

### If the scrape breaks

CivilView is third-party HTML and can re-skin. Freshness tracking marks the `sheriff` dataset failed (visible on
the Ops dashboard) rather than going silently stale. The safe fallback is to set `SHERIFF_SALE_SOURCE=csv` +
`SHERIFF_SALE_CSV_PATH=<a CivilView CSV export>` and let the same loader/merge path run off the file while the
parser is fixed.
