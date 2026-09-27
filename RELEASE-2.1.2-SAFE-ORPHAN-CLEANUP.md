# Release 2.1.2 — Safe Orphan Cleanup

Release 2.1.2 turns the existing read-only maintenance report into an explicit,
previewed cleanup for generated housekeeping files.

## Safety boundary

The cleanup can remove only:

- thumbnails and previews that have no matching database file;
- generated `.web.mp4` playback copies when a matching original video exists;
- generated Guest Upload playback copies older than the existing 90-day guest
  retention period;
- interrupted `.web.tmp.mp4` files older than six hours; and
- expired temporary download ZIP files.

Original photographs, original videos, backup originals and MongoDB records are
not candidates and are never deleted by this cleanup.

An orphan web video without a matching original is shown separately as
**Protected orphan web videos**. It remains on disk for manual review.

The server performs a fresh scan after the administrator confirms the cleanup.
Every candidate must still be located inside its permitted cache, upload or
download-cache root and must have the exact generated-file suffix. Cleanup also
runs as an exclusive heavy job so it does not overlap a backup, download ZIP or
video transcode.

## Prevention

Deleting an individual video from the admin gallery or from an authorised full
access share now also removes its `.web.mp4` and interrupted `.web.tmp.mp4`
companions. If **delete from backup** is selected in the admin, any historical
generated companions beside that backup original are removed too.

## Items deliberately left for review

Database rows whose original file cannot be found are reported exactly as
before. Release 2.1.2 does not change or delete those records.
