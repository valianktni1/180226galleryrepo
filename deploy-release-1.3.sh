#!/usr/bin/env bash
set -Eeuo pipefail

COMPOSE_FILE="/mnt/apps/dockge/data/180226galleryrepo/compose.yaml"
SERVICE="frontend"
CONTAINER="wbm-frontend"
LIVE_TAG="180226galleryrepo-frontend:latest"
TEST_TAG="wbm-frontend:release-1.3-test"
SOURCE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_SOURCE="${SOURCE_ROOT}/frontend"
TIMESTAMP="$(date -u +%Y%m%d-%H%M%S)"
ROLLBACK_TAG="wbm-frontend:rollback-before-release-1.3-${TIMESTAMP}"
DEPLOYED=0

rollback_on_error() {
  local exit_code=$?
  trap - ERR
  set +e
  if [[ "${DEPLOYED}" -eq 1 ]]; then
    echo "Release 1.3 verification failed. Restoring ${ROLLBACK_TAG}..."
    docker image tag "${ROLLBACK_TAG}" "${LIVE_TAG}"
    docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate "${SERVICE}"
    echo "Previous frontend restored. Gallery data was never touched."
  else
    echo "Release 1.3 stopped before live deployment. The running frontend is unchanged."
  fi
  exit "${exit_code}"
}
trap rollback_on_error ERR

if [[ "${EUID}" -ne 0 ]]; then
  echo "Please run this deployment with sudo."
  exit 1
fi

for command in docker curl grep; do
  command -v "${command}" >/dev/null || {
    echo "Required command not found: ${command}"
    exit 1
  }
done

test -f "${COMPOSE_FILE}"
test -f "${FRONTEND_SOURCE}/Dockerfile"
test -f "${FRONTEND_SOURCE}/src/pages/ShareView.js"

CURRENT_IMAGE="$(docker inspect "${CONTAINER}" --format '{{.Image}}')"
test -n "${CURRENT_IMAGE}"
test "$(docker inspect "${CONTAINER}" --format '{{.State.Status}}')" = "running"

echo "Saving the current frontend as ${ROLLBACK_TAG}..."
docker image tag "${CURRENT_IMAGE}" "${ROLLBACK_TAG}"

echo "Building Release 1.3 without changing the live container..."
docker build --no-cache -t "${TEST_TAG}" "${FRONTEND_SOURCE}"

echo "Checking the completed Release 1.3 image..."
docker run --rm --entrypoint sh "${TEST_TAG}" -lc '
  nginx -t &&
  test "$(grep -c "resolver 127.0.0.11 ipv6=off valid=10s;" /etc/nginx/conf.d/default.conf)" -eq 2 &&
  test ! -e /usr/share/nginx/html/studioapp-handoff.txt &&
  test ! -e /usr/share/nginx/html/client-gallery-experience.txt &&
  grep -R -q "Download All " /usr/share/nginx/html/static/js &&
  grep -R -q "All (" /usr/share/nginx/html/static/js &&
  echo "Release 1.3 image checks passed"
'

echo "Switching only the frontend to Release 1.3..."
docker image tag "${TEST_TAG}" "${LIVE_TAG}"
DEPLOYED=1
docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate "${SERVICE}"

HEALTHY=0
for _attempt in {1..15}; do
  if [[ "$(docker inspect "${CONTAINER}" --format '{{.State.Status}}' 2>/dev/null || true)" = "running" ]] &&
     curl -fsS "https://weddingsbymark.uk/api/admin/check-setup" >/dev/null &&
     curl -fsS "https://weddingsbymark.uk/" >/dev/null; then
    HEALTHY=1
    break
  fi
  sleep 2
done
test "${HEALTHY}" -eq 1

if docker logs --since 2m "${CONTAINER}" 2>&1 | grep -Ei '\[error\]|emerg|alert|crit|failed'; then
  echo "Frontend error found after deployment."
  false
fi

DEPLOYED=0
trap - ERR
echo "Release 1.3 deployed successfully."
echo "Rollback image retained as: ${ROLLBACK_TAG}"
