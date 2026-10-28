#!/usr/bin/env bash
# Gallery intake first. No galleries are created until both apps are enabled.
set -Eeuo pipefail
umask 077
STACK_DIR="${WBM_GALLERY_STACK_DIR:-/mnt/apps/dockge/data/180226galleryrepo}"
RELEASE_COMMIT="cd142ed69f7f01668240a5214390354e7d2d0dc2"
cd "$STACK_DIR"
test -f compose.yaml
RELEASE_COMPOSE=$(mktemp "$PWD/compose.release-2.4.XXXXXX")
AUTH_COMPOSE=$(mktemp "$PWD/compose.release-2.4-auth.XXXXXX")
trap 'rm -f "$RELEASE_COMPOSE" "$AUTH_COMPOSE"; unset WBM_GITHUB_TOKEN' EXIT
sed "s|180226galleryrepo.git#main:|180226galleryrepo.git#$RELEASE_COMMIT:|g" compose.yaml > "$RELEASE_COMPOSE"
grep -Fq "180226galleryrepo.git#$RELEASE_COMMIT:backend" "$RELEASE_COMPOSE"
grep -Fq "180226galleryrepo.git#$RELEASE_COMMIT:frontend" "$RELEASE_COMPOSE"
live=(docker compose -f compose.yaml)
build=(docker compose -f "$RELEASE_COMPOSE")
"${live[@]}" config --quiet
"${build[@]}" config --quiet
backup_dir="$PWD/deployment-backups/before-release-2.4-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$backup_dir"
echo '1/5 Backing up the gallery database...'
"${live[@]}" exec -T mongodb mongodump --archive --gzip > "$backup_dir/gallery-mongodb.archive.gz"
test -s "$backup_dir/gallery-mongodb.archive.gz"
gzip -t "$backup_dir/gallery-mongodb.archive.gz"
cp compose.yaml "$backup_dir/compose.yaml"
if [[ -f .env ]]; then cp .env "$backup_dir/app.env"; fi
stamp=$(date +%Y%m%d-%H%M%S)
for service in backend frontend; do
  container=$("${live[@]}" ps -q "$service")
  test -n "$container"
  image=$(docker inspect --format '{{.Image}}' "$container")
  docker image tag "$image" "wbm-$service:rollback-before-release-2.4-$stamp"
done
cat > "$backup_dir/rollback.yaml" <<EOF
services:
  backend:
    image: wbm-backend:rollback-before-release-2.4-$stamp
    pull_policy: never
  frontend:
    image: wbm-frontend:rollback-before-release-2.4-$stamp
    pull_policy: never
EOF
echo "Backup saved: $backup_dir/gallery-mongodb.archive.gz"
printf '\nRollback command:\nsudo docker compose -f %q -f %q up -d --no-deps --no-build backend frontend\n' "$PWD/compose.yaml" "$backup_dir/rollback.yaml"
if ! curl -fsS --max-time 15 "https://raw.githubusercontent.com/valianktni1/180226galleryrepo/$RELEASE_COMMIT/frontend/package.json" >/dev/null 2>&1; then
  if [[ -z "${WBM_GITHUB_TOKEN:-}" ]]; then
    printf 'Gallery repository is private. Paste a GitHub token with repository read access: ' >/dev/tty
    IFS= read -rs WBM_GITHUB_TOKEN </dev/tty
    printf '\n' >/dev/tty
  fi
  test -n "$WBM_GITHUB_TOKEN"
  export WBM_GITHUB_TOKEN
  cat > "$AUTH_COMPOSE" <<'AUTH_YAML'
services:
  backend:
    build:
      secrets:
        - source: wbm_github_auth
          target: GIT_AUTH_TOKEN
  frontend:
    build:
      secrets:
        - source: wbm_github_auth
          target: GIT_AUTH_TOKEN
secrets:
  wbm_github_auth:
    environment: WBM_GITHUB_TOKEN
AUTH_YAML
  build+=(-f "$AUTH_COMPOSE")
fi
echo '2/5 Building both images while the gallery keeps running...'
"${build[@]}" build --no-cache backend frontend
unset WBM_GITHUB_TOKEN
check=(docker compose -f "$RELEASE_COMPOSE")
echo '3/5 Checking the new images before restarting...'
"${check[@]}" run --rm --no-deps --entrypoint python backend -c '
import server, booking_connection
assert any(route.path == "/api/integrations/wbm/galleries" for route in server.app.routes)
assert booking_connection.KEY == "wbm_booking_connection"
print("Gallery 2.4 backend import and route checks passed")
'
"${check[@]}" run --rm --no-deps --entrypoint sh frontend -c '
nginx -t && grep -R -q "Wedding booking connection" /usr/share/nginx/html/static/js
'
echo '4/5 Restarting backend and frontend only...'
"${live[@]}" up -d --no-deps backend frontend
echo '5/5 Checking the gallery...'
ready=0
for attempt in {1..30}; do
  if curl -fsS --max-time 5 https://weddingsbymark.uk/api/admin/check-setup >/dev/null &&
    "${live[@]}" exec -T backend python -c 'from pathlib import Path; assert "register_booking_connection" in Path("server.py").read_text()' >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
"${live[@]}" ps backend frontend
printf '\nRollback command:\nsudo docker compose -f %q -f %q up -d --no-deps --no-build backend frontend\n' "$PWD/compose.yaml" "$backup_dir/rollback.yaml"
if [[ "$ready" != 1 ]]; then
  echo 'Gallery check failed. Use the rollback command above.'
  exit 1
fi
echo 'Gallery 2.4 is responding. Booking connection stays OFF until enabled in gallery Settings.'
