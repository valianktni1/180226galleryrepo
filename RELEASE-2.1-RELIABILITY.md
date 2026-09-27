# Release 2.1 — Backup and Workload Reliability

Release 2.1 strengthens the working production gallery without changing gallery
content, share links, passwords, favourites, album choices or email settings.

## Verified database backups

The existing **Backup Now** action now protects both sides of the gallery:

- original photographs and videos continue to be copied incrementally;
- generated thumbnails, previews and `.web.mp4` files remain excluded;
- MongoDB metadata is written to an atomic BSON snapshot ZIP;
- the new snapshot is opened, checksummed and restored into a uniquely named
  temporary database;
- document counts, document fingerprints and indexes are compared; and
- the temporary verification database is always removed afterwards.

The live database is never overwritten by the verification process. A snapshot
is only reported as verified after the temporary restore succeeds. The newest
14 verified snapshots are retained by default in:

`/mnt/couplesgalleriesbackup/180226/.database`

The admin **System Health** page reports the latest verified restore, record
count, collection count and age. Immediately after deployment it will ask for
one in-app backup; this is expected because no Release 2.1 verification has yet
been recorded.

## Safer large downloads

The four old routes that assembled an entire ZIP in server memory have been
removed. Admin folder downloads, couple folder downloads and favourites now all
use the existing disk-backed download-job service, with progress reporting and
short-lived access tickets.

Single-image and single-video downloads are unchanged.

## Shared heavy-work queue

ZIP preparation, video processing and backups now coordinate through one fair
queue:

- at most two normal heavy jobs run together by default;
- a backup waits for current heavy jobs to finish and then receives an
  exclusive turn;
- jobs already waiting are served in order; and
- normal browsing, favourites and lightweight API requests do not enter this
  queue.

The System Health page shows running and queued heavy work without exposing
paths, access tickets or customer data.

## First verification after deployment

1. Open the admin dashboard and press **Backup Now** once.
2. Allow the gallery and database checks to complete.
3. Open **System Health**.
4. Confirm **Database restore verified** appears under Data Protection.

The first backup may wait briefly if a ZIP or video job is already running.
Couples can continue browsing the gallery while it waits.

## Rollback boundary

The deployment commands retain the previous backend and frontend images as:

- `wbm-backend:rollback-before-release-2.1`
- `wbm-frontend:rollback-before-release-2.1`

Release 2.1 does not migrate or delete live MongoDB records. Rolling the
containers back does not require a database rollback.
