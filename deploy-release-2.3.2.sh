#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="/mnt/apps/dockge/data/180226galleryrepo"
COMPOSE_FILE="$STACK_DIR/compose.yaml"
RELEASE_COMMIT="48c896ba502012040564e25e69b7a8ec978e356d"
RELEASE_COMPOSE="$(mktemp "$STACK_DIR/compose.release-2.3.2.XXXXXX")"

cleanup_release_compose() {
  rm -f "$RELEASE_COMPOSE"
}
trap cleanup_release_compose EXIT

cd "$STACK_DIR"

# Build the exact reviewed frontend commit without changing compose.yaml.
sed "s|180226galleryrepo.git#main:|180226galleryrepo.git#$RELEASE_COMMIT:|g" \
  "$COMPOSE_FILE" > "$RELEASE_COMPOSE"

grep -q "180226galleryrepo.git#$RELEASE_COMMIT:frontend" "$RELEASE_COMPOSE"

CURRENT_FRONTEND_IMAGE="$(docker inspect wbm-frontend --format '{{.Image}}')"
docker image tag "$CURRENT_FRONTEND_IMAGE" \
  wbm-frontend:rollback-before-release-2.3.2

# Frontend-only repair. The live frontend stays running during build and checks.
docker compose -f "$RELEASE_COMPOSE" build --no-cache frontend

docker run --rm --entrypoint sh 180226galleryrepo-frontend:latest -lc '
nginx -t &&
grep -R -q "overscroll-behavior-y:contain" /usr/share/nginx/html/static/css &&
grep -R -q "touch-action:pan-y" /usr/share/nginx/html/static/css &&
grep -R -q ".jpg,.jpeg,.png,.gif,.webp,.bmp,.tiff,.heic,.heif" /usr/share/nginx/html/static/js &&
grep -R -q "Create Share Link" /usr/share/nginx/html/static/js &&
grep -R -q "Create Gallery" /usr/share/nginx/html/static/js &&
echo "Release 2.3.2 mobile modal checks passed"
'

# Recreate from the normal compose file so Dockge keeps its normal stack metadata.
docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate frontend

release_health=0
for attempt in {1..30}; do
  if curl -fsS https://weddingsbymark.uk/api/admin/check-setup >/dev/null; then
    release_health=1
    break
  fi
  sleep 2
done

test "$release_health" -eq 1
echo "Release 2.3.2 is responding"

docker compose -f "$COMPOSE_FILE" ps frontend
docker inspect wbm-frontend \
  --format '{{.Name}} image={{.Image}} status={{.State.Status}} started={{.State.StartedAt}}'
curl -fsS https://weddingsbymark.uk/api/admin/check-setup && echo

docker logs --since 5m wbm-frontend 2>&1 |
  grep -Ei 'emerg|alert|crit' || echo "No serious frontend errors found"

echo "Release 2.3.2 deployed successfully. Mobile admin forms now scroll above the bottom navigation."
echo "Rollback if needed:"
echo "docker image tag wbm-frontend:rollback-before-release-2.3.2 180226galleryrepo-frontend:latest && docker compose -f $COMPOSE_FILE up -d --no-deps --force-recreate frontend"
