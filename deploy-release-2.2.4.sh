#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="/mnt/apps/dockge/data/180226galleryrepo"
COMPOSE_FILE="$STACK_DIR/compose.yaml"
RELEASE_COMMIT="6ac3dc051926c738da71a77c91288c93d80deae2"
RELEASE_COMPOSE="$(mktemp "$STACK_DIR/compose.release-2.2.4.XXXXXX")"

cleanup_release_compose() {
  rm -f "$RELEASE_COMPOSE"
}
trap cleanup_release_compose EXIT

cd "$STACK_DIR"

# Pin the remote build context to the exact tested source commit. A later
# change to main therefore cannot alter what this deployment builds.
sed "s|180226galleryrepo.git#main:|180226galleryrepo.git#$RELEASE_COMMIT:|g" \
  "$COMPOSE_FILE" > "$RELEASE_COMPOSE"

grep -q "180226galleryrepo.git#$RELEASE_COMMIT:frontend" "$RELEASE_COMPOSE"

docker image tag "$(docker inspect wbm-frontend --format '{{.Image}}')" \
  wbm-frontend:rollback-before-release-2.2.4

# This release is frontend-only. The live frontend is replaced only after the
# new image has built and all of its checks have succeeded.
docker compose -f "$RELEASE_COMPOSE" build --no-cache frontend

docker run --rm --entrypoint sh 180226galleryrepo-frontend:latest -lc '
nginx -t &&
grep -R -q "Record Your Personal Message" /usr/share/nginx/html/static/js &&
grep -R -q "Wedding Album Choices" /usr/share/nginx/html/static/js &&
grep -R -q "decoding:\"async\"" /usr/share/nginx/html/static/js &&
grep -R -q "loading:\"lazy\"" /usr/share/nginx/html/static/js &&
echo "Release 2.2.4 frontend checks passed"
'

docker compose -f "$RELEASE_COMPOSE" up -d --no-deps --force-recreate frontend

release_health=0
for attempt in {1..30}; do
  if curl -fsS https://weddingsbymark.uk/api/admin/check-setup >/dev/null; then
    release_health=1
    break
  fi
  sleep 2
done

test "$release_health" -eq 1
echo "Release 2.2.4 is responding"

docker compose -f "$RELEASE_COMPOSE" ps frontend
docker inspect wbm-frontend \
  --format '{{.Name}} image={{.Image}} status={{.State.Status}} started={{.State.StartedAt}}'
curl -fsS https://weddingsbymark.uk/api/admin/check-setup && echo
docker logs --since 5m wbm-frontend 2>&1 |
  grep -Ei 'emerg|alert|crit' || echo "No serious frontend errors found"

echo "Release 2.2.4 deployed successfully. Dashboard covers now load as you approach them."
