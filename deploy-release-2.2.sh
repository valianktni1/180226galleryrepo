#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="/mnt/apps/dockge/data/180226galleryrepo"
COMPOSE_FILE="$STACK_DIR/compose.yaml"
RELEASE_COMMIT="6dfd3f66538d718c7096b28d9f7b454644b96dcc"
RELEASE_COMPOSE="$(mktemp "$STACK_DIR/compose.release-2.2.XXXXXX")"

cleanup_release_compose() {
  rm -f "$RELEASE_COMPOSE"
}
trap cleanup_release_compose EXIT

cd "$STACK_DIR"

# Build this release from its exact, verified GitHub commit. Docker BuildKit can
# otherwise retain a stale moving `main` ref even when --no-cache is requested.
sed "s|180226galleryrepo.git#main:|180226galleryrepo.git#$RELEASE_COMMIT:|g" \
  "$COMPOSE_FILE" > "$RELEASE_COMPOSE"

grep -q "180226galleryrepo.git#$RELEASE_COMMIT:backend" "$RELEASE_COMPOSE"
grep -q "180226galleryrepo.git#$RELEASE_COMMIT:frontend" "$RELEASE_COMPOSE"

docker image tag "$(docker inspect wbm-backend --format '{{.Image}}')" \
  wbm-backend:rollback-before-release-2.2
docker image tag "$(docker inspect wbm-frontend --format '{{.Image}}')" \
  wbm-frontend:rollback-before-release-2.2

docker compose -f "$RELEASE_COMPOSE" build --no-cache backend frontend

docker run --rm --entrypoint sh 180226galleryrepo-backend:latest -lc '
python -m py_compile server.py voice_message_service.py album_downloads.py album_selection.py backup_service.py database_backup_service.py download_job_service.py heavy_job_queue.py maintenance_cleanup.py maintenance_scan.py security_paths.py share_security.py share_selection.py system_health.py broadcast_service.py &&
PYTHONPATH=/app pytest -q \
  tests/test_voice_message_service_unit.py \
  tests/test_voice_message_api_structure_unit.py \
  tests/test_maintenance_scan_unit.py \
  tests/test_maintenance_cleanup_unit.py \
  tests/test_release_2_1_2_cleanup_structure_unit.py \
  tests/test_release_1_9_structure_unit.py \
  tests/test_database_backup_service_unit.py \
  tests/test_heavy_job_queue_unit.py \
  tests/test_release_2_1_reliability_structure_unit.py \
  tests/test_backup_service_unit.py \
  tests/test_download_job_service_unit.py \
  tests/test_download_jobs_api_structure_unit.py \
  tests/test_album_selection_unit.py \
  tests/test_album_selection_structure_unit.py \
  tests/test_album_cover_download_unit.py \
  tests/test_add_subfolder_unit.py \
  tests/test_guest_upload_cleanup_unit.py \
  tests/test_backup_api_structure_unit.py \
  tests/test_hardening_structure_unit.py \
  tests/test_security_paths_unit.py \
  tests/test_share_security_unit.py \
  tests/test_gallery_ready_share_selection_unit.py \
  tests/test_system_health_unit.py \
  tests/test_broadcast_campaign_unit.py
'

docker run --rm --entrypoint sh 180226galleryrepo-frontend:latest -lc '
nginx -t &&
grep -R -q "Record Your Personal Message" /usr/share/nginx/html/static/js &&
grep -R -q "Personal Voice Messages" /usr/share/nginx/html/static/js &&
grep -R -q "Listen before you send" /usr/share/nginx/html/static/js &&
grep -R -q "Download MP3" /usr/share/nginx/html/static/js &&
grep -R -q "voice-message" /usr/share/nginx/html/static/js &&
echo "Release 2.2 frontend checks passed"
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
echo "Release 2.2 is responding"

docker compose -f "$RELEASE_COMPOSE" ps backend frontend
docker inspect wbm-backend wbm-frontend \
  --format '{{.Name}} image={{.Image}} status={{.State.Status}} started={{.State.StartedAt}}'
curl -fsS https://weddingsbymark.uk/api/admin/check-setup && echo
docker logs --since 5m wbm-backend 2>&1 |
  grep -Ei 'error|exception|traceback|failed' || echo "No backend errors found"
docker logs --since 5m wbm-frontend 2>&1 |
  grep -Ei 'emerg|alert|crit' || echo "No serious frontend errors found"

echo "Release 2.2 deployed successfully. Test one QR voice message before announcing it."
