#!/usr/bin/env bash
set -euo pipefail

cd "$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

GIT_SHA="$(git rev-parse HEAD)"
export GIT_SHA
echo "==> Deploying ${GIT_SHA}"

echo "==> Building images"
docker compose --profile app build

echo "==> Stopping app services (frees DB locks for migration)"
docker compose stop api worker web || true

echo "==> Running migrations"
docker compose run --rm migrate

echo "==> Starting app"
docker compose --profile app up -d

echo "==> Pruning old images"
docker image prune -f

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
docker compose ps
