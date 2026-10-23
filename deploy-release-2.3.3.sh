#!/usr/bin/env bash
set -euo pipefail

STACK_DIR="/mnt/apps/dockge/data/180226galleryrepo"
COMPOSE_FILE="$STACK_DIR/compose.yaml"
RELEASE_COMMIT="614c4794b4fbb9de3a806606711c6938b433f8b0"
RELEASE_COMPOSE="$(mktemp "$STACK_DIR/compose.release-2.3.3.XXXXXX")"

cleanup_release_compose() {
  rm -f "$RELEASE_COMPOSE"
}
trap cleanup_release_compose EXIT

cd "$STACK_DIR"

# Build the exact reviewed backend commit without changing compose.yaml.
sed "s|180226galleryrepo.git#main:|180226galleryrepo.git#$RELEASE_COMMIT:|g" \
  "$COMPOSE_FILE" > "$RELEASE_COMPOSE"

grep -q "180226galleryrepo.git#$RELEASE_COMMIT:backend" "$RELEASE_COMPOSE"

CURRENT_BACKEND_IMAGE="$(docker inspect wbm-backend --format '{{.Image}}')"
docker image tag "$CURRENT_BACKEND_IMAGE" \
  wbm-backend:rollback-before-release-2.3.3

# Backend-only artwork release. The live gallery stays running during build/checks.
docker compose -f "$RELEASE_COMPOSE" build --no-cache backend

docker run --rm --entrypoint sh 180226galleryrepo-backend:latest -lc '
python -m py_compile server.py &&
PYTHONPATH=/app pytest -q tests/test_awards_badge_asset_unit.py &&
python - <<'"'"'PY'"'"'
from pathlib import Path
from PIL import Image

asset = Path("/app/assets/awards-badges.png")
with Image.open(asset) as image:
    assert image.format == "PNG"
    assert image.size == (960, 640)
assert asset.stat().st_size < 200_000
print(f"Awards badge verified: {asset.stat().st_size} bytes")
PY
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
echo "Release 2.3.3 is responding"

docker compose -f "$COMPOSE_FILE" ps backend
docker inspect wbm-backend \
  --format '{{.Name}} image={{.Image}} status={{.State.Status}} started={{.State.StartedAt}}'

curl -fsS https://weddingsbymark.uk/api/admin/check-setup && echo

ASSET_BYTES="$(curl -fsS 'https://weddingsbymark.uk/api/public/email-assets/awards-badges.png?v=20261023' | wc -c)"
test "$ASSET_BYTES" -eq 129435
echo "New awards badge is live: $ASSET_BYTES bytes"

docker logs --since 5m wbm-backend 2>&1 |
  grep -Ei 'error|exception|traceback|failed' || echo "No backend errors found"

echo "Release 2.3.3 deployed successfully. Branded emails now use the updated awards badge."
echo "Rollback if needed:"
echo "docker image tag wbm-backend:rollback-before-release-2.3.3 180226galleryrepo-backend:latest && docker compose -f $COMPOSE_FILE up -d --no-deps --force-recreate backend"
