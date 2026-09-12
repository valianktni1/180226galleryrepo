# Release 1.4 - Responsive, Original-Only Backups

## Purpose

This release keeps the production gallery responsive while the in-app Backup
button is running and stops generated web-playback videos from being copied to
the backup dataset.

## What changes

- The existing incremental backup now runs in one dedicated background worker
  instead of blocking FastAPI's only web worker.
- A second backup cannot start while one is already running.
- The admin Backup button shows gallery-level progress and continues tracking a
  backup after the dashboard is refreshed.
- Original photographs and original videos are still copied exactly as before.
- Generated `*.web.mp4` and in-progress `*.web.tmp.mp4` playback copies are
  excluded. They can be regenerated from the original video with the existing
  video optimisation controls.
- Existing thumbnail and preview exclusions remain unchanged.

## Deliberate non-destructive behaviour

This release does **not** delete any `*.web.mp4` files that are already present
in `/backup` or Backblaze B2. It only prevents future backup runs from copying or
updating those generated files. Any later cleanup of old generated backup copies
must be inspected, approved and performed separately.

## Unchanged

- Gallery folders, photographs, original videos and MongoDB records.
- The live and backup mount paths.
- Video transcoding, GPU acceleration and NGINX video delivery.
- Share links, passwords, downloads, favourites, album selections and emails.
- Backup deletion rules and the 90-day Guest Upload cleanup.

## Verification included

- Original video copies successfully while its generated web video is excluded.
- Existing generated files in the backup destination are not deleted.
- Unchanged originals remain incremental and are skipped on the next run.
- A backup starts asynchronously and overlapping runs are rejected.
- The FastAPI route starts only the background manager and performs no copying
  in the request handler.
- The frontend polls the status endpoint and disables duplicate Backup clicks.

The included `deploy-release-1.4.sh` builds and tests both replacement images,
saves exact rollback tags, recreates only backend and frontend, verifies the live
site, and automatically restores both previous images if deployment checks fail.
