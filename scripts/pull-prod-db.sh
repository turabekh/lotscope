#!/usr/bin/env bash
set -euo pipefail

PROD_HOST="${PROD_HOST:-34.148.129.129}"
PROD_USER="${PROD_USER:-turaboy}"
PROD_KEY="${PROD_KEY:-$HOME/.ssh/lotscope_deploy}"
PROD_DIR="${PROD_DIR:-~/lotscope}"
DB_USER="${DB_USER:-lotscope}"
DB_NAME="${DB_NAME:-lotscope}"
LOCAL_DB_SERVICE="${LOCAL_DB_SERVICE:-db}"
DUMP_DIR="${DUMP_DIR:-/tmp}"

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ "${1:-}" != "--confirm" ]]; then
  cat >&2 <<'MSG'
This REPLACES your entire local database with a copy of production.

Everything local is destroyed: seeded accounts, test data, anything you
have not committed to a migration. Production is only read from.

The copy carries real owner PII and real user accounts. Treat the local
database as sensitive and delete it when you no longer need it (docs/runbook.md).

Re-run with --confirm to proceed:
  ./scripts/pull-prod-db.sh --confirm
MSG
  exit 1
fi

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dump="${DUMP_DIR}/lotscope-prod-${stamp}.dump"

echo "==> Dumping production (${PROD_HOST})"
ssh -i "${PROD_KEY}" -o StrictHostKeyChecking=accept-new "${PROD_USER}@${PROD_HOST}" \
  "cd ${PROD_DIR} && docker compose exec -T ${LOCAL_DB_SERVICE} pg_dump -U ${DB_USER} -d ${DB_NAME} -Fc --no-owner --no-acl" \
  > "${dump}"

size="$(wc -c < "${dump}")"
if [[ "${size}" -lt 10000000 ]]; then
  echo "==> Dump is only ${size} bytes, which is far too small to be the real database." >&2
  echo "    Refusing to restore from it. The local database is untouched." >&2
  exit 1
fi
echo "==> Dumped $(( size / 1024 / 1024 )) MB to ${dump}"

echo "==> Recreating the local database"
docker compose exec -T "${LOCAL_DB_SERVICE}" psql -U "${DB_USER}" -d postgres \
  -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '${DB_NAME}' AND pid <> pg_backend_pid()" >/dev/null
docker compose exec -T "${LOCAL_DB_SERVICE}" psql -U "${DB_USER}" -d postgres -c "DROP DATABASE IF EXISTS ${DB_NAME}" >/dev/null
docker compose exec -T "${LOCAL_DB_SERVICE}" psql -U "${DB_USER}" -d postgres -c "CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}" >/dev/null

echo "==> Restoring"
docker compose exec -T "${LOCAL_DB_SERVICE}" pg_restore -U "${DB_USER}" -d "${DB_NAME}" --no-owner --no-acl < "${dump}" \
  || echo "==> pg_restore reported non-fatal errors (usually extension ownership); verifying below"

echo "==> Verifying"
docker compose exec -T "${LOCAL_DB_SERVICE}" psql -U "${DB_USER}" -d "${DB_NAME}" -c "
SELECT (SELECT count(*) FROM parcel) AS parcels,
       (SELECT count(*) FROM parcel_verdict) AS verdicts,
       (SELECT count(*) FROM parcel_verdict WHERE verdict_version = 'v11') AS v11,
       (SELECT version_num FROM alembic_version) AS alembic_head"

echo "==> Done. Dump kept at ${dump} — delete it when finished."
