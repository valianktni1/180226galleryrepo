#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="/mnt/apps/dockge/data/180226galleryrepo"
COMPOSE_FILE="$STACK_DIR/compose.yaml"
RELEASE_COMMIT="863f52c780b6ca01f2833f2cdf8ba4430437f901"
RELEASE_COMPOSE="$(mktemp "$STACK_DIR/compose.release-2.2.1-resume.XXXXXX")"

cleanup_release_compose() {
  rm -f "$RELEASE_COMPOSE"
}
trap cleanup_release_compose EXIT

cd "$STACK_DIR"

sed "s|180226galleryrepo.git#main:|180226galleryrepo.git#$RELEASE_COMMIT:|g" \
  "$COMPOSE_FILE" > "$RELEASE_COMPOSE"

grep -q "180226galleryrepo.git#$RELEASE_COMMIT:backend" "$RELEASE_COMPOSE"
grep -q "180226galleryrepo.git#$RELEASE_COMMIT:frontend" "$RELEASE_COMPOSE"

# The cross-mobile frontend image completed successfully in the previous run.
# Rebuild only the corrected backend; unchanged dependency layers may be reused.
docker compose -f "$RELEASE_COMPOSE" build backend

docker run --rm --entrypoint sh 180226galleryrepo-backend:latest -lc '
python -m py_compile server.py voice_message_service.py &&
PYTHONPATH=/app pytest -q \
  tests/test_voice_message_service_unit.py \
  tests/test_voice_message_api_structure_unit.py \
  tests/test_heavy_job_queue_unit.py
'

docker run --rm --entrypoint sh 180226galleryrepo-frontend:latest -lc '
nginx -t &&
grep -R -q "Record Your Personal Message" /usr/share/nginx/html/static/js &&
grep -R -q "Personal Voice Messages" /usr/share/nginx/html/static/js &&
grep -R -q "No compatible audio recorder configuration is available" /usr/share/nginx/html/static/js &&
echo "Release 2.2.1 cross-mobile frontend checks passed"
'

docker compose -f "$RELEASE_COMPOSE" up -d --no-deps --force-recreate backend frontend

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

docker inspect wbm-backend wbm-frontend \
  --format '{{.Name}} image={{.Image}} status={{.State.Status}} started={{.State.StartedAt}}'
curl -fsS https://weddingsbymark.uk/api/admin/check-setup && echo
docker logs --since 5m wbm-backend 2>&1 |
  grep -Ei 'error|exception|traceback|failed' || echo "No backend errors found"
docker logs --since 5m wbm-frontend 2>&1 |
  grep -Ei 'emerg|alert|crit' || echo "No serious frontend errors found"

echo "Release 2.2.1 deployed successfully. Record and send one short QR voice message now."
