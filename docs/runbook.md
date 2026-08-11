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

`scripts/deploy.sh` calls it automatically **before migrations**, labelled `pre-migration`, but **only when migrations are actually pending** — it compares the database's current Alembic revision against head and skips the backup when they match. Most deploys carry no schema change and do not need a 400 MB dump.

If the revision comparison cannot be made, the backup is taken anyway. Failing towards a backup costs a minute; failing away from one costs the database.

**A weekly backup also runs from the VM's crontab**, Sundays at 03:00 UTC, labelled `weekly`:

```cron
PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:/snap/bin
BACKUP_BUCKET=gs://lotscope-501014-db-backups
BACKUP_LABEL=weekly
0 3 * * 0 cd /home/turaboy/lotscope && /bin/bash scripts/backup-db.sh >> /home/turaboy/backup.log 2>&1
```

`PATH` is set explicitly because `gcloud` lives in `/snap/bin`, which cron's default `PATH` does not include. Without that line the job fails every week with `gcloud: command not found` and nothing announces it — the failure mode this schedule exists to prevent.

Installed and verified 2026-08-01 by running the command in a stripped environment (`env -i`), which produced `lotscope-weekly-20260801T020511Z.dump`.

**Weekly, not nightly, is a deliberate trade.** It sets the real RPO at 7 days (see *Objectives*). Nightly would cost roughly seven times the storage — still only cents a month — so if losing a week of pipelines, saved searches, and underwriting is unacceptable, change the schedule rather than the RPO figure.

**Expect one `ERROR` line in a successful run.** `gcloud` reports that it cannot check bucket compatibility for parallel composite uploads, because the VM service account holds `roles/storage.objectAdmin` (objects) and not `storage.buckets.get`. It falls back to a normal upload and succeeds. This is a performance note wearing an error's clothing; it is not a failed backup.

A deploy that cannot back up does not migrate — the script exits non-zero and the deploy stops. This is deliberate: LR-P006 requires a production backup before risky migrations, and a requirement that can be forgotten is not a control.

The escape hatch is the **`skip_pre_migration_backup`** input on the Deploy workflow, which sets `SKIP_PRE_MIGRATION_BACKUP=1` for that run only and prints a warning into the log.

It is a per-run input rather than a repository variable on purpose. A variable would persist silently and disable the gate on every later deploy, which is how a safety control stops existing without anyone deciding to remove it. As an input, each skip is an explicit choice recorded in that run's parameters.

**Used once on 2026-07-28** to apply the four migrations blocked by the `devstorage.read_only` scope. That deploy carried no backup. If those migrations need reverting, `downgrade` is the only route and `underwriting_profile` and `parcel_correction` would lose any rows written since.

## Configuration

`BACKUP_BUCKET` is supplied by the deploy workflow from the repository variable of the same name and forwarded over SSH, so a deploy carries it without anything being set on the VM. Running `scripts/backup-db.sh` by hand on the VM requires it in the environment or in `~/lotscope/.env`.

**Production bucket:** `gs://lotscope-501014-db-backups` — US-EAST1 (same region as the VM), uniform access, 30-day delete lifecycle. The VM service account holds `roles/storage.objectAdmin`, which the script needs for both upload and pruning.

### Resolved: the VM can write to Cloud Storage

The instance was originally created with the OAuth scope `devstorage.read_only`. **Access scopes are a ceiling above IAM**, so the `objectAdmin` binding was correct but unreachable and uploads failed with *"Provided scope(s) are not authorized"*.

**Fixed 2026-07-28** by widening the scope to `devstorage.read_write`, verified by a real write and delete from the VM. The gate has since run unattended twice: a pre-migration backup on 2026-08-01 and the first scheduled `weekly` backup the same day.

Widening a scope requires the instance to be `TERMINATED`, and stopping it released the VM's ephemeral external IP. See *The IP incident* in `docs/handoff/0030-2026-07-28.md`: **check `natIP` allocation type before stopping a GCE instance.** The address is now the reserved static `lotscope-static`, so a stop/start cannot repeat it — but note that the deploy path also holds the address as a literal in the `VM_HOST` GitHub secret, which must be updated in the same breath as DNS if it ever changes again.

The lifecycle rule and the script's `BACKUP_RETAIN_DAYS` both sit at 30 days deliberately. The script prunes by the timestamp in each filename; the lifecycle prunes by object age. If the script's pruning ever breaks, the bucket rule still caps storage growth.

Other settings, on the VM in `~/lotscope/.env`:

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
| **RPO** | **7 days**, and zero for migration-caused loss | The schedule is weekly (Sundays 03:00 UTC), plus a pre-migration backup; a migration failure loses nothing because the backup precedes it |
| **RTO** | 1 hour | Measured 2026-08-01: 4s download + 4m19s restore + verification. The remaining budget is promotion and service restart |

The RPO is **7 days because the schedule is weekly**, not because a week of loss is comfortable. It is the figure the configuration actually supports. Moving to a nightly cron makes it 24 hours for a few cents a month; changing the number without changing the schedule makes it fiction.

RTO is now evidence-based rather than estimated, but it covers a *verified scratch restore* — the promote-and-restart step has still never been performed under pressure.

## Monthly restore test

A backup that has never been restored is a hypothesis. Once a month:

1. Restore the most recent backup into `lotscope_restore`.
2. Compare parcel and verdict counts per market against `status.md`.
3. Drop the scratch database.
4. Record the date and the counts in `docs/launch-readiness/gates.md` under **G6**.

**Do not stop `api`, `worker`, or `web` for this test.** The *Restore* section above stops them because it describes a real recovery, where the live database is about to be replaced. The monthly test writes only to a scratch database, so stopping services would take production down to verify a copy — cost with no benefit.

**Performed 2026-08-01**, the first time. `pg_restore` returned 0 with no stderr output, and every count matched live exactly:

| Measure | Live | Restored |
|---|---|---|
| phl / pgh / wlm / hbg parcels | 550,976 / 143,355 / 26,197 / 19,502 | identical |
| `parcel_verdict` | 740,030 | identical |
| `app_user` / `deal` / `deal_activity` / `saved_search` | 10 / 5 / 2 / 3 | identical |
| Tables | 45 | 44 |

The single table difference is `policy_document`, and the restored `alembic_version` is `d9f3b1c7e485` rather than `b3c45f2553b6`. That is correct: the dump is labelled `pre-migration` and was taken before `b3c45f2553b6` applied. A pre-migration backup that already contained the migration would be the defect.

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

## Verdict v9 rollout — overlay-aware zoning standards

v9 changes how zoning standards resolve (ADR-0080) and requires a full `phl` recompute. **Order matters**, because `get_or_compute_current_verdict` recomputes lazily on version mismatch: between deploy and recompute, every parcel view of a v8 row pays a full `compute_verdict`.

### Ordering

1. **Stop the app before Alembic.** `scripts/deploy.sh` takes a `pre-migration` backup automatically when migrations are pending; this deploy carries two (`e5b1c93a7d24` overlay_standard, `f3a71c8d0e59` parcel_overlay).
2. **Migrate**, then **seed**: `make seed` writes the six `overlay_standard` rows, RSA-5 at 960, RM-1's provision and the industrial FARs. The base flip and the overlay rows must land together — 960 without the overlay layer is the 54,376-parcel false-positive window ADR-0080 exists to close.
3. **Populate membership before traffic returns — now automatic.** `scripts/deploy.sh` runs `python -m lotscope.zoning.overlay_membership` between the seed and app start, and **exits nonzero if any market ends up with zero memberships**, which fails the deploy rather than serving a wrong standard. An empty `parcel_overlay` does not fail loudly on its own: it silently resolves every parcel to its base standard, which for RSA-5 is 960 everywhere — exactly the failure mode being prevented. To run it by hand:
   ```
   cd backend && uv run python -m lotscope.zoning.overlay_membership
   ```
   Measured locally: **phl 1,487,536 + wlm 14,777 rows in ~60s**. Thereafter the nightly overlay ingest refreshes it automatically. The refresh covers **every market with overlay polygons**, discovered from `zoning_overlay` rather than hardcoded — `wlm` has 7 polygons and would otherwise lose overlay display entirely.
4. **Verify before traffic:** `make verify-zoning-standards` → `OK` (0.44s). Exits nonzero on divergence.
5. **Start the app**, then **recompute**.

### Recompute

```
make recompute-verdicts          # python -m lotscope.verdict.jobs, batch size 500
```

**Scope to `phl`.** pgh (143,355), wlm (26,197) and hbg (19,502) are untouched by every v9 correction; recomputing them burns hours for no change.

**Measured wall-clock**, sequential, local hardware (40-parcel samples, `compute_verdict`):

| path | p50 | rate | full phl (550,945) |
|---|---|---|---|
| v8 baseline | 67.9 ms | 14.7/s | 10.38 h |
| v9, live `ST_Intersects` | 95.0 ms | 10.0/s | 15.30 h |
| **v9, materialized membership** | **70.2 ms** | **13.1/s** | **11.70 h** |

v9's own overhead is **+1.13 h** over v8; the remaining ~10.5 h is pre-existing recompute cost. Production hardware will differ — treat these as ratios, not promises.

**Recompute after the app is up, not before.** Post-materialization the lazy path costs ~70 ms per first view rather than ~95 ms, which is acceptable for the window it takes the batch job to catch up. Recomputing before traffic would gate the deploy on 11.7 h for no safety gain, since the effective standard is correct the moment step 3 completes.

### Rollback

`overlay_standard` and `parcel_overlay` are new tables; `CREATE TABLE` takes no lock on hot tables and `downgrade -1` twice drops them cleanly. Reverting the code without reverting the seed leaves RSA-5 at 960 with no overlay layer — **the unsafe state**. Roll back seed and code together, or re-seed from the previous revision.
