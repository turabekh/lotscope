#!/usr/bin/env bash
# Restore the newest nightly dump into a scratch database and count what came back.
#
# A backup that has not been restored is a hypothesis. This runs on the VM weekly, proves
# the hypothesis against the real dump, and writes the result into `job_run` so a restore
# that silently stopped working shows up on the same screen as every other job.
set -euo pipefail

DB_CONTAINER="${BACKUP_DB_CONTAINER:-db}"
DB_USER="${BACKUP_DB_USER:-lotscope}"
DB_NAME="${BACKUP_DB_NAME:-lotscope}"
SCRATCH_DB="${BACKUP_SCRATCH_DB:-lotscope_restore_check}"
LABEL="${BACKUP_LABEL:-nightly}"
JOB_ID="backup:restore_check"

if [[ -z "${BACKUP_BUCKET:-}" ]]; then
  echo "BACKUP_BUCKET is not set, so there is no backup to verify." >&2
  exit 1
fi

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

psql_main() { docker compose exec -T "${DB_CONTAINER}" psql -U "${DB_USER}" -d "${DB_NAME}" "$@"; }

started="$(date -u +'%Y-%m-%d %H:%M:%S+00')"
dump_file=""

record() {
  local status="$1" rows="$2" error="$3"
  psql_main -v ON_ERROR_STOP=1 \
    -v status="${status}" -v rows="${rows}" -v err="${error}" -v started="${started}" \
    -c "INSERT INTO job_run (job_id, label, kind, status, started_at, finished_at,
          duration_ms, result_count, error, created_at, updated_at)
        VALUES ('${JOB_ID}', 'restore_check', 'backup', :'status', :'started', now(),
          round(extract(epoch FROM (now() - :'started'::timestamptz)) * 1000),
          nullif(:'rows','')::int, nullif(:'err',''), now(), now())" > /dev/null
}

cleanup() {
  [[ -n "${dump_file}" ]] && rm -f "${dump_file}"
  docker compose exec -T "${DB_CONTAINER}" \
    psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${SCRATCH_DB}" > /dev/null 2>&1 || true
}
trap cleanup EXIT

fail() {
  echo "$1" >&2
  record failed "" "$1" || true
  exit 1
}

# A restore is a second copy of the database on the same disk. Refuse rather than fill it.
db_bytes="$(psql_main -tAc "SELECT pg_database_size('${DB_NAME}')" | tr -d '[:space:]')"
free_bytes=$(( $(df -P --output=avail / | tail -1) * 1024 ))
if (( free_bytes < db_bytes * 2 )); then
  fail "Not enough free disk to restore: $(( free_bytes / 1024**3 )) GB free, database is $(( db_bytes / 1024**3 )) GB."
fi

echo "==> Finding the newest ${LABEL} backup"
newest="$(gcloud storage ls "${BACKUP_BUCKET%/}/lotscope-${LABEL}-*.dump" 2>/dev/null | sort | tail -1)"
[[ -n "${newest}" ]] || fail "No ${LABEL} backup exists in ${BACKUP_BUCKET}."
echo "    ${newest}"

dump_file="/tmp/$(basename "${newest}")"
gcloud storage cp "${newest}" "${dump_file}" || fail "Could not download ${newest}."
size="$(wc -c < "${dump_file}")"
(( size > 1024 )) || fail "Downloaded dump is ${size} bytes, which is not a database."

echo "==> Restoring into ${SCRATCH_DB}"
docker compose exec -T "${DB_CONTAINER}" psql -U "${DB_USER}" -d postgres \
  -c "DROP DATABASE IF EXISTS ${SCRATCH_DB}" -c "CREATE DATABASE ${SCRATCH_DB}" > /dev/null

# pg_restore reports non-fatal noise (extension owners, comments) on a --no-owner dump,
# so the count below is the pass condition, not the exit code.
docker compose exec -T "${DB_CONTAINER}" \
  pg_restore -U "${DB_USER}" -d "${SCRATCH_DB}" --no-owner --no-privileges \
  < "${dump_file}" > /dev/null 2>&1 || true

rows="$(docker compose exec -T "${DB_CONTAINER}" \
  psql -U "${DB_USER}" -d "${SCRATCH_DB}" -tAc 'SELECT count(*) FROM parcel' 2>/dev/null \
  | tr -d '[:space:]')"

[[ "${rows}" =~ ^[0-9]+$ ]] || fail "The restored database has no readable parcel table."
(( rows > 0 )) || fail "The restored database holds 0 parcels."

echo "==> Restored ${rows} parcels from $(basename "${newest}") (${size} bytes)"
record success "${rows}" ""
