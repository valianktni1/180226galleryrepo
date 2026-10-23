#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="/mnt/apps/dockge/data/180226galleryrepo"
COMPOSE_FILE="$STACK_DIR/compose.yaml"
RELEASE_COMMIT="5d2d19d159f0b792edef5f812355622cb7d22a26"
SITE_URL="https://weddingsbymark.uk"
cd "$STACK_DIR"
test -f "$COMPOSE_FILE"

RELEASE_COMPOSE="$(mktemp "$STACK_DIR/compose.release-2.3.4.XXXXXX")"
LIVE_JS="$(mktemp /tmp/wbm-release-2.3.4-js.XXXXXX)"
AUTH_COMPOSE="$(mktemp "$STACK_DIR/compose.release-2.3.4-auth.XXXXXX")"
trap 'rm -f "$RELEASE_COMPOSE" "$LIVE_JS" "$AUTH_COMPOSE"; unset WBM_GITHUB_TOKEN' EXIT

# Pin this frontend build without changing Dockge's normal compose file.
sed "s|180226galleryrepo.git#main:|180226galleryrepo.git#$RELEASE_COMMIT:|g" \
  "$COMPOSE_FILE" > "$RELEASE_COMPOSE"
grep -q "180226galleryrepo.git#$RELEASE_COMMIT:frontend" "$RELEASE_COMPOSE"

BACKEND_BEFORE="$(docker inspect wbm-backend --format '{{.Id}}')"
CURRENT_IMAGE="$(docker inspect wbm-frontend --format '{{.Image}}')"
docker image tag "$CURRENT_IMAGE" wbm-frontend:rollback-before-release-2.3.4

BUILD_FILES=(-f "$RELEASE_COMPOSE")
if ! curl -fsS --max-time 15 \
  "https://raw.githubusercontent.com/valianktni1/180226galleryrepo/$RELEASE_COMMIT/frontend/package.json" >/dev/null 2>&1; then
  if [ -z "${WBM_GITHUB_TOKEN:-}" ]; then
    printf 'GitHub repository is private. Paste a token with repository read access: ' >/dev/tty
    IFS= read -rs WBM_GITHUB_TOKEN </dev/tty
    printf '\n' >/dev/tty
  fi
  test -n "$WBM_GITHUB_TOKEN"
  export WBM_GITHUB_TOKEN
  cat > "$AUTH_COMPOSE" <<'AUTH_YAML'
services:
  frontend:
    build:
      secrets:
        - source: wbm_github_auth
          target: GIT_AUTH_TOKEN
secrets:
  wbm_github_auth:
    environment: WBM_GITHUB_TOKEN
AUTH_YAML
  BUILD_FILES+=(-f "$AUTH_COMPOSE")
fi

echo "Building the GPU/video monitor. The live gallery remains running during the build..."
docker compose "${BUILD_FILES[@]}" build --no-cache frontend
unset WBM_GITHUB_TOKEN

echo "Checking the new frontend..."
docker run --rm --entrypoint sh 180226galleryrepo-frontend:latest -lc '
nginx -t &&
grep -R -q "gpu-encoding-monitor" /usr/share/nginx/html/static/js &&
grep -R -q "CPU fallback" /usr/share/nginx/html/static/js &&
echo "GPU/video monitor found in the production build"
'
EXPECTED_IMAGE="$(docker image inspect 180226galleryrepo-frontend:latest --format '{{.Id}}')"

echo "Restarting only the frontend..."
docker compose -f "$COMPOSE_FILE" up -d --no-deps --force-recreate frontend
test "$(docker inspect wbm-frontend --format '{{.Image}}')" = "$EXPECTED_IMAGE"
test "$(docker inspect wbm-backend --format '{{.Id}}')" = "$BACKEND_BEFORE"

echo "Checking the live frontend..."
RELEASE_OK=0
for attempt in {1..30}; do
  if MAIN_JS="$(curl -fsS --max-time 10 "$SITE_URL/" | grep -oE '/static/js/main\.[[:alnum:]]+\.js')"; then
    if curl -fsS --max-time 20 "$SITE_URL$MAIN_JS" -o "$LIVE_JS" &&
       grep -q "gpu-encoding-monitor" "$LIVE_JS"; then
      RELEASE_OK=1
      break
    fi
  fi
  sleep 2
done

if [ "$RELEASE_OK" -ne 1 ]; then
  echo "The live frontend could not be verified. Please share this output."
  echo "Rollback: docker image tag wbm-frontend:rollback-before-release-2.3.4 180226galleryrepo-frontend:latest && docker compose -f $COMPOSE_FILE up -d --no-deps --force-recreate frontend"
  exit 1
fi

curl -fsS --max-time 10 "$SITE_URL/api/admin/check-setup"
echo
docker compose -f "$COMPOSE_FILE" ps frontend backend
echo "SUCCESS: Release 2.3.4 is live. Refresh the admin dashboard to see GPU / Video."
echo "The backend container was not restarted."
echo "Rollback: docker image tag wbm-frontend:rollback-before-release-2.3.4 180226galleryrepo-frontend:latest && docker compose -f $COMPOSE_FILE up -d --no-deps --force-recreate frontend"
