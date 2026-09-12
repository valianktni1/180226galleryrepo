#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE_FILE="/mnt/apps/dockge/data/180226galleryrepo/compose.yaml"
BACKEND_CONTAINER="wbm-backend"
BACKEND_LIVE_TAG="180226galleryrepo-backend:latest"
BACKEND_TEST_TAG="wbm-backend:release-1.4.1-test"
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
ROLLBACK_TAG="wbm-backend:rollback-before-release-1.4.1-${TIMESTAMP}"
DEPLOYED=0

rollback_on_error() {
  local exit_code=$?
  trap - ERR
  set +e
  if [[ "${DEPLOYED}" -eq 1 ]]; then
    echo "Release 1.4.1 verification failed. Restoring the previous backend..."
    docker image tag "${ROLLBACK_TAG}" "${BACKEND_LIVE_TAG}"
    docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate backend
    echo "Previous backend restored. Gallery data was never touched."
  fi
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

CURRENT_IMAGE="$(docker inspect "${BACKEND_CONTAINER}" --format '{{.Image}}')"
test -n "${CURRENT_IMAGE}"
test "$(docker inspect "${BACKEND_CONTAINER}" --format '{{.State.Status}}')" = "running"

echo "Saving the current backend as ${ROLLBACK_TAG}..."
docker image tag "${CURRENT_IMAGE}" "${ROLLBACK_TAG}"

echo "Building and testing Release 1.4.1 away from production..."
docker build --no-cache -t "${BACKEND_TEST_TAG}" "${SOURCE_ROOT}/backend"
docker run --rm --entrypoint sh "${BACKEND_TEST_TAG}" -lc '
  python -m py_compile server.py backup_service.py security_paths.py share_security.py share_selection.py &&
  PYTHONPATH=/app pytest -q \
    tests/test_guest_upload_cleanup_unit.py \
    tests/test_backup_service_unit.py \
    tests/test_backup_api_structure_unit.py \
    tests/test_hardening_structure_unit.py \
    tests/test_security_paths_unit.py \
    tests/test_share_security_unit.py \
    tests/test_gallery_ready_share_selection_unit.py
'

echo "Switching only the backend to Release 1.4.1..."
docker image tag "${BACKEND_TEST_TAG}" "${BACKEND_LIVE_TAG}"
DEPLOYED=1
docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate backend

HEALTHY=0
for _attempt in {1..15}; do
  if [[ "$(docker inspect "${BACKEND_CONTAINER}" --format '{{.State.Status}}' 2>/dev/null || true)" = "running" ]] &&
     curl -fsS "https://weddingsbymark.uk/api/admin/check-setup" >/dev/null; then
    HEALTHY=1
    break
  fi
  sleep 2
done
test "${HEALTHY}" -eq 1

if docker logs --since 2m "${BACKEND_CONTAINER}" 2>&1 | grep -Ei 'traceback|exception| - error -'; then
  echo "Backend error found after deployment."
  false
fi

DEPLOYED=0
trap - ERR
echo "Release 1.4.1 deployed successfully."
echo "Rollback image retained as: ${ROLLBACK_TAG}"
