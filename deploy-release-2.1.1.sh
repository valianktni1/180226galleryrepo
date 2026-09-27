#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="/mnt/apps/dockge/data/180226galleryrepo"
COMPOSE_FILE="$STACK_DIR/compose.yaml"

cd "$STACK_DIR"

docker image tag "$(docker inspect wbm-backend --format '{{.Image}}')" \
  wbm-backend:rollback-before-release-2.1.1

docker compose -f "$COMPOSE_FILE" build --no-cache backend

docker run --rm --entrypoint sh 180226galleryrepo-backend:latest -lc '
python -m py_compile server.py album_downloads.py album_selection.py backup_service.py database_backup_service.py download_job_service.py heavy_job_queue.py security_paths.py share_security.py share_selection.py system_health.py broadcast_service.py &&
PYTHONPATH=/app pytest -q \
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

docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate backend

release_health=0
for attempt in {1..30}; do
  if curl -fsS https://weddingsbymark.uk/api/admin/check-setup >/dev/null; then
    release_health=1
    break
  fi
  sleep 2
done

test "$release_health" -eq 1
echo "Release 2.1.1 is responding"

docker inspect wbm-backend \
  --format 'image={{.Image}} status={{.State.Status}} started={{.State.StartedAt}}'
curl -fsS https://weddingsbymark.uk/api/admin/check-setup && echo
docker logs --since 5m wbm-backend 2>&1 |
  grep -Ei 'error|exception|traceback|failed' || echo "No backend errors found"

echo "Release 2.1.1 deployed successfully. Run Backup Now once to verify the database snapshot."
