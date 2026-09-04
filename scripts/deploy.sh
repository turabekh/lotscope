#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GIT_SHA="$(git rev-parse HEAD)"
export GIT_SHA
echo "==> Deploying ${GIT_SHA}"

APP_RECREATED=0

on_failure() {
  local code=$?
  [ "$code" -eq 0 ] && return 0
  echo "" >&2
  echo "DEPLOY FAILED (exit ${code})." >&2
  if [ "$APP_RECREATED" -eq 1 ]; then
    echo "The app had already been recreated; it may be serving the new build." >&2
    docker compose ps >&2
    return 0
  fi
  echo "Nothing was recreated, so the previously running app should still be serving." >&2
  local serving
  serving="$(docker compose exec -T api python -c \
    'import json,urllib.request;print(json.load(urllib.request.urlopen("http://localhost:8000/health"))["version"])' \
    2>/dev/null || true)"
  if [ -n "$serving" ]; then
    echo "OLD APP STILL SERVING: ${serving}. No outage; fix the cause and re-run." >&2
  else
    echo "OLD APP IS NOT SERVING — this is an outage, not just a failed deploy." >&2
    docker compose ps >&2
  fi
}
trap on_failure EXIT

echo "==> Building images"
docker compose --profile app build --build-arg GIT_SHA="${GIT_SHA}"

alembic_revisions() {
  docker compose run --rm --entrypoint sh migrate -c \
    'alembic current 2>/dev/null; echo "--"; alembic heads 2>/dev/null' 2>/dev/null || true
}

migrations_pending() {
  local output current head
  output="$(alembic_revisions)"
  current="$(echo "${output}" | sed -n '1,/^--$/p' | grep -oE '^[0-9a-f]{12}' | head -1)"
  head="$(echo "${output}" | sed -n '/^--$/,$p' | grep -oE '^[0-9a-f]{12}' | head -1)"
  if [[ -z "${current}" || -z "${head}" ]]; then
    echo "    could not determine migration state; assuming migrations are pending" >&2
    return 0
  fi
  echo "    current ${current}, head ${head}" >&2
  [[ "${current}" != "${head}" ]]
}

if [[ "${SKIP_PRE_MIGRATION_BACKUP:-0}" == "1" ]]; then
  echo "==> WARNING: pre-migration backup skipped by SKIP_PRE_MIGRATION_BACKUP=1"
elif migrations_pending; then
  echo "==> Migrations pending — taking a pre-migration backup"
  BACKUP_LABEL=pre-migration "$(dirname "${BASH_SOURCE[0]}")/backup-db.sh"
else
  echo "==> No migrations pending — skipping the pre-migration backup"
fi

echo "==> Running migrations against the live database (old app still serving)"
PGOPTIONS="-c lock_timeout=30s" docker compose run --rm -e PGOPTIONS migrate

echo "==> Seeding reference data (zoning standards)"
docker compose run --rm --entrypoint python migrate -m lotscope.zoning.seed

echo "==> Refreshing parcel-overlay membership"
docker compose run --rm --entrypoint python migrate -m lotscope.zoning.overlay_membership

echo "==> Recreating app services"
APP_RECREATED=1
docker compose --profile app up -d

echo "==> Verifying the running build matches ${GIT_SHA} (drift guard)"
running=""
for _ in $(seq 1 24); do
  running="$(docker compose exec -T api python -c \
    'import json,urllib.request;print(json.load(urllib.request.urlopen("http://localhost:8000/health"))["version"])' \
    2>/dev/null || true)"
  [ -n "$running" ] && break
  sleep 5
done

if [ -z "$running" ]; then
  echo "DEPLOY FAILED: api /health never reported a version after ~2min" >&2
  docker compose ps >&2
  exit 1
fi

if [ "$running" != "$GIT_SHA" ]; then
  echo "DEPLOY DRIFT: prod is serving ${running} but this deploy pushed ${GIT_SHA}" >&2
  echo "The new build did not take effect. Do not treat this deploy as successful." >&2
  exit 1
fi

echo "==> OK: prod is serving ${GIT_SHA}"

echo "==> Pruning old images"
docker image prune -f

docker compose ps
