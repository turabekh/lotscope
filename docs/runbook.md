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

**Delete the demo row after the first verified live load** (it was inserted manually to exercise the `live`
state and must not linger beside real data):

```bash
docker compose --profile app exec db \
  psql -U lotscope -d lotscope -c "DELETE FROM sheriff_sale WHERE case_number='BW-DEMO-01';"
```

### Expect on first run

- A **burst of `sheriff_sale` Deal Feed events** — one per newly-seen case (~1,400+ parcels). Expected: that
  is the feature. The first-load baseline guard (`EXISTS (SELECT 1 FROM sheriff_sale)`) means the *very first*
  load does not spuriously event every row, but subsequent new cases do event.
- Listings whose OPA # does not resolve to a loaded parcel are retained in `raw` and skipped from core/events
  (address-match is a deferred follow-up). ~5 listings carry no OPA # at all and are skipped. The **run report
  logs the skipped-and-counted tally** (`sheriff_load_complete`) and the `dataset_freshness.detail` for
  `sheriff_sale` records `"N of M rows skipped"`, so parser drift shows up as a rising skip count.

### Rollback

Set `SHERIFF_SALE_SOURCE=csv` (or remove the line) and `docker compose --profile app up -d api worker`. Rows
already written to `sheriff_sale` remain; the job simply stops refreshing from the scrape. No migration, no
verdict impact (VERDICT_VERSION unaffected — the calendar reads existing forced-sale data).

### If the scrape breaks

CivilView is third-party HTML and can re-skin. Freshness tracking marks the `sheriff` dataset failed (visible on
the Ops dashboard) rather than going silently stale. The safe fallback is to set `SHERIFF_SALE_SOURCE=csv` +
`SHERIFF_SALE_CSV_PATH=<a CivilView CSV export>` and let the same loader/merge path run off the file while the
parser is fixed.

---

# Backup, retention, and recovery

Required by `docs/PRD-amendment-03-launch-readiness.md` §LR-P005 and §LR-P006. Backlog ticket LR-B-033.

## What runs, and when

`scripts/backup-db.sh` runs **on the VM** and dumps the production database to object storage.

`scripts/deploy.sh` calls it automatically **before migrations**, labelled `pre-migration`. A deploy that cannot back up does not migrate — the script exits non-zero and the deploy stops. This is deliberate: LR-P006 requires a production backup before risky migrations, and a requirement that can be forgotten is not a control.

The escape hatch is `SKIP_PRE_MIGRATION_BACKUP=1`, which prints a warning. It exists for a genuine emergency and leaves a trace in the deploy log.

## Configuration

Set on the VM, in `~/lotscope/.env`:

| Variable | Default | Meaning |
|---|---|---|
| `BACKUP_BUCKET` | **none — required** | Object-storage prefix, e.g. `gs://your-bucket/lotscope-backups` |
| `BACKUP_RETAIN_DAYS` | `30` | Age after which backups are pruned |
| `BACKUP_DB_CONTAINER` | `db` | Compose service holding Postgres |
| `BACKUP_DB_USER` | `lotscope` | |
| `BACKUP_DB_NAME` | `lotscope` | |

`BACKUP_BUCKET` has **no default on purpose**. A backup written only to the VM does not survive the failure it exists to protect against, so the script refuses to pretend it has succeeded.

## What the script guarantees

- Dumps with `pg_dump -Fc --no-owner --no-privileges`, restorable with `pg_restore`.
- **Rejects a dump under 1 KB.** A successful `pg_dump` of a broken connection can produce a near-empty file; uploading it would leave a backup that only fails at restore time.
- Verifies the uploaded object exists before deleting the local copy.
- Prunes objects older than the retention window by their embedded timestamp.

## Restore

```bash
gcloud storage ls gs://your-bucket/lotscope-backups/
gcloud storage cp gs://your-bucket/lotscope-backups/<dump> /tmp/restore.dump

cd ~/lotscope
docker compose stop api worker web
docker compose exec -T db dropdb -U lotscope --if-exists lotscope_restore
docker compose exec -T db createdb -U lotscope lotscope_restore
docker compose exec -T db pg_restore -U lotscope -d lotscope_restore --no-owner < /tmp/restore.dump
```

**Restore into `lotscope_restore` first, never over the live database.** Verify row counts against `docs/launch-readiness/status.md` before promoting. Promoting is a rename, and it is the point at which a mistake becomes unrecoverable.

## Objectives

| Objective | Target | Basis |
|---|---|---|
| **RPO** | 24 hours, and zero for migration-caused loss | Backups are pre-migration plus whatever schedule is configured; a migration failure loses nothing because the backup precedes it |
| **RTO** | 1 hour | Download, restore into a scratch database, verify, promote |

Both are targets, not guarantees, and neither is credible until a restore has actually been performed.

## Monthly restore test

A backup that has never been restored is a hypothesis. Once a month:

1. Restore the most recent backup into `lotscope_restore`.
2. Compare parcel and verdict counts per market against `status.md`.
3. Drop the scratch database.
4. Record the date and the counts in `docs/launch-readiness/gates.md` under **G6**.

Until step 4 has happened at least once, **G6 is not met** regardless of what this document says.

## Migration rollback

Every migration in this repository has a `downgrade()`. To roll one back:

```bash
cd ~/lotscope
docker compose run --rm migrate alembic downgrade -1
```

Downgrades that drop a column lose the data in it. Where the column is derived — `parcel_verdict.field_trust`, the screening recommendation — a recompute regenerates it. Where it is user data — `underwriting_profile`, `parcel_correction` — **restore from backup instead of downgrading**.

## Bad-verdict recompute

If a deployed change produces wrong verdicts rather than a broken schema, the response is a recompute rather than a restore:

```bash
docker compose exec -T worker python -m lotscope.verdict.jobs --market philadelphia
```

Market-scoped, so a bad Philadelphia recompute does not disturb pilots.
