#!/usr/bin/env bash
set -euo pipefail

DB_CONTAINER="${BACKUP_DB_CONTAINER:-db}"
DB_USER="${BACKUP_DB_USER:-lotscope}"
DB_NAME="${BACKUP_DB_NAME:-lotscope}"
RETAIN_DAYS="${BACKUP_RETAIN_DAYS:-14}"
LABEL="${BACKUP_LABEL:-manual}"

if [[ -z "${BACKUP_BUCKET:-}" ]]; then
  cat >&2 <<'MSG'
BACKUP_BUCKET is not set, so this backup would exist only on the VM.
An on-host copy does not survive the failure it exists to protect against.

Set it on the VM, for example:
  echo 'BACKUP_BUCKET=gs://your-bucket/lotscope-backups' >> ~/lotscope/.env

Refer to docs/runbook.md for the retention and restore procedure.
MSG
  exit 1
fi

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

stamp="$(date -u +%Y%m%dT%H%M%SZ)"
dump="lotscope-${LABEL}-${stamp}.dump"
target="${BACKUP_BUCKET%/}/${dump}"

trap 'rm -f "/tmp/${dump}"' EXIT

echo "==> Dumping ${DB_NAME} to ${dump}"
docker compose exec -T "${DB_CONTAINER}" \
  pg_dump -U "${DB_USER}" -d "${DB_NAME}" -Fc --no-owner --no-privileges > "/tmp/${dump}"

size="$(wc -c < "/tmp/${dump}")"
if [[ "${size}" -lt 1024 ]]; then
  echo "Dump is ${size} bytes, which is too small to be a real database." >&2
  exit 1
fi
echo "==> Dump is ${size} bytes"

echo "==> Uploading to ${target}"
gcloud storage cp "/tmp/${dump}" "${target}"

echo "==> Verifying the uploaded object exists"
gcloud storage ls "${target}" > /dev/null

echo "==> Pruning backups older than ${RETAIN_DAYS} days"
cutoff="$(date -u -d "${RETAIN_DAYS} days ago" +%Y%m%dT%H%M%SZ 2>/dev/null \
  || date -u -v-"${RETAIN_DAYS}"d +%Y%m%dT%H%M%SZ)"
gcloud storage ls "${BACKUP_BUCKET%/}/" 2>/dev/null | while read -r object; do
  name="$(basename "${object}")"
  object_stamp="$(echo "${name}" | grep -oE '[0-9]{8}T[0-9]{6}Z' || true)"
  if [[ -n "${object_stamp}" && "${object_stamp}" < "${cutoff}" ]]; then
    echo "    removing ${name}"
    gcloud storage rm "${object}"
  fi
done

echo "==> Backup complete: ${target}"
