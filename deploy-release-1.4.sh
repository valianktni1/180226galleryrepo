#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE_FILE="/mnt/apps/dockge/data/180226galleryrepo/compose.yaml"
BACKEND_CONTAINER="wbm-backend"
FRONTEND_CONTAINER="wbm-frontend"
BACKEND_LIVE_TAG="180226galleryrepo-backend:latest"
FRONTEND_LIVE_TAG="180226galleryrepo-frontend:latest"
BACKEND_TEST_TAG="wbm-backend:release-1.4-test"
FRONTEND_TEST_TAG="wbm-frontend:release-1.4-test"
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
BACKEND_ROLLBACK_TAG="wbm-backend:rollback-before-release-1.4-${TIMESTAMP}"
FRONTEND_ROLLBACK_TAG="wbm-frontend:rollback-before-release-1.4-${TIMESTAMP}"
BACKEND_DEPLOYED=0
FRONTEND_DEPLOYED=0

rollback_on_error() {
  local exit_code=$?
  trap - ERR
  set +e
  echo "Release 1.4 verification failed. Restoring previous images..."
  if [[ "${BACKEND_DEPLOYED}" -eq 1 ]]; then
    docker image tag "${BACKEND_ROLLBACK_TAG}" "${BACKEND_LIVE_TAG}"
    docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate backend
  fi
  if [[ "${FRONTEND_DEPLOYED}" -eq 1 ]]; then
    docker image tag "${FRONTEND_ROLLBACK_TAG}" "${FRONTEND_LIVE_TAG}"
    docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate frontend
  fi
  echo "Previous application images restored. Gallery data was never touched."
  exit "${exit_code}"
}
trap rollback_on_error ERR

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run this deployment with sudo or from a root shell."
  exit 1
fi

for command in docker curl grep; do
  command -v "${command}" >/dev/null || {
    echo "Required command not found: ${command}"
    exit 1
  }
done

test -f "${COMPOSE_FILE}"
test -f "${SOURCE_ROOT}/backend/Dockerfile"
test -f "${SOURCE_ROOT}/backend/backup_service.py"
test -f "${SOURCE_ROOT}/frontend/Dockerfile"

BACKEND_CURRENT_IMAGE="$(docker inspect "${BACKEND_CONTAINER}" --format '{{.Image}}')"
FRONTEND_CURRENT_IMAGE="$(docker inspect "${FRONTEND_CONTAINER}" --format '{{.Image}}')"
test -n "${BACKEND_CURRENT_IMAGE}"
test -n "${FRONTEND_CURRENT_IMAGE}"
test "$(docker inspect "${BACKEND_CONTAINER}" --format '{{.State.Status}}')" = "running"
test "$(docker inspect "${FRONTEND_CONTAINER}" --format '{{.State.Status}}')" = "running"

echo "Saving the current backend and frontend rollback images..."
docker image tag "${BACKEND_CURRENT_IMAGE}" "${BACKEND_ROLLBACK_TAG}"
docker image tag "${FRONTEND_CURRENT_IMAGE}" "${FRONTEND_ROLLBACK_TAG}"

echo "Building and testing the Release 1.4 backend away from production..."
docker build --no-cache -t "${BACKEND_TEST_TAG}" "${SOURCE_ROOT}/backend"
docker run --rm --entrypoint sh "${BACKEND_TEST_TAG}" -lc '
  python -m py_compile server.py backup_service.py security_paths.py share_security.py share_selection.py &&
  PYTHONPATH=/app pytest -q \
    tests/test_backup_service_unit.py \
    tests/test_backup_api_structure_unit.py \
    tests/test_hardening_structure_unit.py \
    tests/test_security_paths_unit.py \
    tests/test_share_security_unit.py \
    tests/test_gallery_ready_share_selection_unit.py
'

echo "Building and testing the Release 1.4 frontend away from production..."
docker build --no-cache -t "${FRONTEND_TEST_TAG}" "${SOURCE_ROOT}/frontend"
docker run --rm --entrypoint sh "${FRONTEND_TEST_TAG}" -lc '
  nginx -t &&
  test "$(grep -c "resolver 127.0.0.11 ipv6=off valid=10s;" /etc/nginx/conf.d/default.conf)" -eq 2 &&
  test ! -e /usr/share/nginx/html/studioapp-handoff.txt &&
  test ! -e /usr/share/nginx/html/client-gallery-experience.txt &&
  grep -R -q "admin/backup/status" /usr/share/nginx/html/static/js &&
  grep -R -q "Back up gallery originals" /usr/share/nginx/html/static/js &&
  grep -R -q "Download All " /usr/share/nginx/html/static/js &&
  echo "Release 1.4 frontend image checks passed"
'

echo "Switching the backend to Release 1.4..."
docker image tag "${BACKEND_TEST_TAG}" "${BACKEND_LIVE_TAG}"
BACKEND_DEPLOYED=1
docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate backend

BACKEND_HEALTHY=0
for _attempt in {1..15}; do
  if [[ "$(docker inspect "${BACKEND_CONTAINER}" --format '{{.State.Status}}' 2>/dev/null || true)" = "running" ]] &&
     curl -fsS "https://weddingsbymark.uk/api/admin/check-setup" >/dev/null; then
    BACKEND_HEALTHY=1
    break
  fi
  sleep 2
done
test "${BACKEND_HEALTHY}" -eq 1

echo "Switching the frontend to Release 1.4..."
docker image tag "${FRONTEND_TEST_TAG}" "${FRONTEND_LIVE_TAG}"
FRONTEND_DEPLOYED=1
docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate frontend

SITE_HEALTHY=0
for _attempt in {1..15}; do
  if [[ "$(docker inspect "${FRONTEND_CONTAINER}" --format '{{.State.Status}}' 2>/dev/null || true)" = "running" ]] &&
     curl -fsS "https://weddingsbymark.uk/api/admin/check-setup" >/dev/null &&
     curl -fsS "https://weddingsbymark.uk/" >/dev/null; then
    SITE_HEALTHY=1
    break
  fi
  sleep 2
done
test "${SITE_HEALTHY}" -eq 1

if docker logs --since 2m "${FRONTEND_CONTAINER}" 2>&1 | grep -Ei '\[error\]|emerg|alert|crit'; then
  echo "Frontend error found after deployment."
  false
fi
if docker logs --since 2m "${BACKEND_CONTAINER}" 2>&1 | grep -Ei 'traceback|exception| - error -'; then
  echo "Backend error found after deployment."
  false
fi

BACKEND_DEPLOYED=0
FRONTEND_DEPLOYED=0
trap - ERR
echo "Release 1.4 deployed successfully."
echo "Backend rollback image: ${BACKEND_ROLLBACK_TAG}"
echo "Frontend rollback image: ${FRONTEND_ROLLBACK_TAG}"
