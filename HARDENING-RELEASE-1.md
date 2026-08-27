# Gallery Hardening Release 1

## R1.1 frontend resolver correction

The first live frontend smoke test showed that a freshly resolved `nginx:alpine`
image could select Docker's IPv6 address for the `backend` and `nginx-video`
service names, while those services listen on IPv4. Both Docker DNS resolver
directives now set `ipv6=off`. This preserves the existing IPv4 service routing
and prevents intermittent `connect() failed (111: Connection refused)` errors.

Baseline: the live notification-email hotfix at commit
`f324f51fcff21baaf9148f156a37e48b4a720bd6`.

This release is deliberately narrow. It preserves all 103 API routes, the
MongoDB schema, gallery/share records, media mounts, backup behaviour, email
workflow, frontend screens, GPU transcoding and the existing NGINX video path.

## What this release changes

- Proves gallery, subfolder, cache, backup and filename paths stay inside their
  configured storage roots before file operations are performed.
- Preserves ordinary photography names and punctuation while reducing browser
  `C:\fakepath\...` upload names to their basename.
- Streams guest uploads to a temporary disk file in 1 MiB chunks, enforces the
  existing 500 MiB limit without loading the file into RAM, and removes partial
  files if an upload fails or exceeds the limit.
- Applies safe filenames to photographer and admin uploads too.
- Revalidates every protected share session against the live MongoDB share.
  Disabled or expired shares therefore stop working on their next request.
- Refreshes permissions and subfolder scope from MongoDB instead of trusting
  stale JWT permissions.
- Constrains file-ID lookups to the share's gallery and, where applicable, its
  one allowed subfolder.
- Requires a valid admin/share token plus a matching database record before an
  original media file can be served.
- Stops new auto-generated gallery passwords being written to application and
  activity logs.
- Adds MongoDB indexes for live share revalidation and common file-ID lookups.
- Corrects the 90-day guest cleanup paths for thumbnails and previews.
- Removes internal handoff documents from `frontend/public`, redacts the
  tracked live-secret examples, and adds low-risk NGINX response headers.

## Verification completed

- Python compilation: passed.
- API route parity: all 103 routes unchanged and unique.
- Hardening unit tests: 13 passed.
- Notification-email hotfix regression checks: 2 passed.
- Secret scan: the previously exposed live signing value and StudioApp
  credential no longer exist in the release working tree.

The container image was not built in the preparation workspace because Docker
is not available there. Production must not be the first place this release is
tested; use a fictional/test gallery for the post-build browser checks.

## Files added

- `backend/security_paths.py`
- `backend/share_security.py`
- `backend/tests/test_hardening_structure_unit.py`
- `backend/tests/test_security_paths_unit.py`
- `backend/tests/test_share_security_unit.py`
- `HARDENING-RELEASE-1.md`

## Files changed

- `backend/server.py`
- `frontend/nginx.conf`
- `compose-for-dockge.txt` (documentation/example only; not the live Compose)
- `memory/studioapp-handoff-final.md`

## Files intentionally removed

- `frontend/public/studioapp-handoff.txt`
- `frontend/public/client-gallery-experience.txt`
- `memory/test_credentials.md`

## Deployment boundaries

Do not deploy directly from the GitHub remote URL while the repository is
private: the present Dockge Git build context cannot authenticate. Do not make
the repository public again because old Git history still contains secrets.
First switch the live Compose build contexts to a private authenticated or
local source checkout, review the resulting Compose diff, and preserve the
current image IDs.

Deploy in two separately verifiable steps:

1. Backend security: build and recreate only `backend`, then check startup
   logs, `/api/admin/check-setup`, admin login, one fictional share, one small
   upload/download, share disable/re-enable and video playback.
2. Public-file cleanup: build and recreate only `frontend`, then check admin,
   couple and QR upload screens on desktop and mobile. Confirm the two removed
   `.txt` URLs return 404.

Credential rotation is a third, separate operational step. Generate different
values for `JWT_SECRET` and `NGINX_VIDEO_SECRET`; the video value must match in
the backend and `nginx-video`. Recreating the backend after JWT rotation logs
out current sessions but does not change galleries or media.

## Rollback preparation

Before building, tag the currently running images with immutable rollback
names and record their IDs:

```bash
docker image inspect 180226galleryrepo-backend:latest --format '{{.Id}}'
docker image tag 180226galleryrepo-backend:latest wbm-backend:email-hotfix-f324f51
docker image inspect 180226galleryrepo-frontend:latest --format '{{.Id}}'
docker image tag 180226galleryrepo-frontend:latest wbm-frontend:before-hardening-r1
```

If the backend verification fails, re-point the Compose image name to the
saved backend image and recreate only that service:

```bash
docker image tag wbm-backend:email-hotfix-f324f51 180226galleryrepo-backend:latest
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml up -d --no-deps --force-recreate backend
```

Use the equivalent frontend tag only if the frontend step fails. A ZFS
snapshot remains the last-resort recovery route; routine rollback should use
the saved Docker image so gallery data and MongoDB are never rolled back.

## Deliberately deferred

- Disk-backed ZIP creation for very large gallery downloads.
- Frontend dependency lockfile and fully reproducible image tags.
- Encryption/redesign of plaintext share passwords required by the existing
  email and edit workflow.
- Signed/authenticated thumbnail and preview URLs.
- CORS tightening and coordinated live-secret rotation.
- MongoDB dump automation and a tested full restore drill.

Each deferred item should be its own measured release rather than being mixed
into this security patch.
