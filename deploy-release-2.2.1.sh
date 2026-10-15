#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="/mnt/apps/dockge/data/180226galleryrepo"
COMPOSE_FILE="$STACK_DIR/compose.yaml"
RELEASE_COMMIT="2be3a1160cdf860ac2adf0781ad2c53e9f23ac6b"
RELEASE_COMPOSE="$(mktemp "$STACK_DIR/compose.release-2.2.1.XXXXXX")"

cleanup_release_compose() {
  rm -f "$RELEASE_COMPOSE"
}
trap cleanup_release_compose EXIT

cd "$STACK_DIR"

sed "s|180226galleryrepo.git#main:|180226galleryrepo.git#$RELEASE_COMMIT:|g" \
  "$COMPOSE_FILE" > "$RELEASE_COMPOSE"

grep -q "180226galleryrepo.git#$RELEASE_COMMIT:backend" "$RELEASE_COMPOSE"

docker image tag "$(docker inspect wbm-backend --format '{{.Image}}')" \
  wbm-backend:rollback-before-release-2.2.1

docker compose -f "$RELEASE_COMPOSE" build --no-cache backend

docker run --rm --entrypoint sh 180226galleryrepo-backend:latest -lc '
python -m py_compile server.py voice_message_service.py &&
PYTHONPATH=/app pytest -q \
  tests/test_voice_message_service_unit.py \
  tests/test_voice_message_api_structure_unit.py
'

docker compose -f "$RELEASE_COMPOSE" up -d --no-deps --force-recreate backend

release_health=0
for attempt in {1..30}; do
  if curl -fsS https://weddingsbymark.uk/api/admin/check-setup >/dev/null; then
    release_health=1
    break
  fi
  sleep 2
done

test "$release_health" -eq 1
echo "Release 2.2.1 is responding"

docker inspect wbm-backend \
  --format 'image={{.Image}} status={{.State.Status}} started={{.State.StartedAt}}'
curl -fsS https://weddingsbymark.uk/api/admin/check-setup && echo
docker logs --since 5m wbm-backend 2>&1 |
  grep -Ei 'error|exception|traceback|failed' || echo "No backend errors found"

echo "Release 2.2.1 deployed successfully. Record and send one short QR voice message now."
