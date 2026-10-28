#!/usr/bin/env bash
# Focused WBM booking index fix. Preserve the running image and all gallery data.
set -Eeuo pipefail
umask 077
[[ "$(id -u)" == 0 ]] || { echo 'Run this script with sudo bash.'; exit 1; }
stack=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project.working_dir"}}' wbm-backend)
[[ -d "$stack" && -f "$stack/compose.yaml" ]] || { echo 'Cannot identify compose.yaml; nothing changed.'; exit 1; }
project=$(docker inspect --format '{{index .Config.Labels "com.docker.compose.project"}}' wbm-backend)
[[ -n "$project" && "$project" != "<no value>" ]] || { echo 'Cannot identify Compose project; nothing changed.'; exit 1; }
stamp=$(date +%Y%m%d-%H%M%S)
backup="$stack/deployment-backups/booking-index-fix-$stamp"
mkdir -p "$backup"
docker cp wbm-backend:/app/booking_connection.py "$backup/original-booking_connection.py"
python3 - "$backup/original-booking_connection.py" <<'PY'
import hashlib, pathlib, sys
data=pathlib.Path(sys.argv[1]).read_bytes()
blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
if blob != '07f44889de50950c0a133914c2bbc833a37c3568':
    raise SystemExit('Running connection file differs from the reviewed version. Nothing changed; send this message to Mark\'s support chat.')
PY
curl -fsSL --max-time 60 https://raw.githubusercontent.com/valianktni1/180226galleryrepo/8ddd10a17a58e4caf12d0f9f42e87d65fbc5ab9f/backend/booking_connection.py -o "$backup/booking_connection.py"
echo "89de5c18f7c7051f5ba7aed1d407827e207cd87f1656f961b83828de14dd09e2  $backup/booking_connection.py" | sha256sum -c -
echo 'Backing up the gallery database...'
docker exec wbm-mongodb mongodump --archive --gzip > "$backup/gallery-mongodb.archive.gz"
test -s "$backup/gallery-mongodb.archive.gz"
gzip -t "$backup/gallery-mongodb.archive.gz"
cp "$stack/compose.yaml" "$backup/original-compose.yaml"
old="wbm-backend:before-booking-index-fix-$stamp"
new="wbm-backend:booking-index-fix-$stamp"
docker image tag "$(docker inspect --format '{{.Image}}' wbm-backend)" "$old"
cat > "$backup/rollback.yaml" <<EOF
services:
  backend:
    image: $old
    pull_policy: never
EOF
cat > "$backup/fix.yaml" <<EOF
services:
  backend:
    image: $new
    pull_policy: never
EOF
cat > "$backup/Dockerfile" <<EOF
FROM $old
COPY booking_connection.py /app/booking_connection.py
RUN python -m py_compile /app/booking_connection.py
EOF
compose=(docker compose --project-name "$project" --project-directory "$stack" -f "$stack/compose.yaml")
rollback() {
  echo 'Restoring the previous backend image...'
  "${compose[@]}" -f "$backup/rollback.yaml" up -d --no-deps --no-build --pull never backend
}
echo 'Building the one-file fix from the existing backend image...'
docker build --network none -t "$new" "$backup"
docker run --rm --network none --entrypoint python "$new" -c 'import booking_connection; print("Connection module import passed")'
"${compose[@]}" -f "$backup/fix.yaml" config --quiet
printf 'Rollback: sudo docker compose --project-name %q --project-directory %q -f %q -f %q up -d --no-deps --no-build --pull never backend\n' "$project" "$stack" "$stack/compose.yaml" "$backup/rollback.yaml"
if ! "${compose[@]}" -f "$backup/fix.yaml" up -d --no-deps --no-build --pull never backend; then
  rollback
  exit 1
fi
ready=0
for attempt in {1..20}; do
  if docker exec wbm-backend python -c 'import urllib.request; urllib.request.urlopen("http://127.0.0.1:8001/api/admin/check-setup", timeout=3)' >/dev/null 2>&1; then
    ready=1
    break
  fi
  sleep 2
done
if [[ "$ready" != 1 ]]; then
  rollback
  echo 'Health check failed; previous backend restored.'
  exit 1
fi
echo "Backend fix installed. Database backup: $backup/gallery-mongodb.archive.gz"
echo 'Existing booking jobs can now retry. Gallery creation still needs verification in the booking app.'
