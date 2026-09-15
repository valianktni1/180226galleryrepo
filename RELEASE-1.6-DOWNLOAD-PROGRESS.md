# Release 1.6 — Real folder download progress

This release replaces the folder **Download All** path used by the admin and
couples with an authenticated, disk-backed download job.

## What changes

- A compact progress panel appears immediately below **Download All**.
- ZIP preparation reports real files, bytes and percentage progress.
- Browser delivery reports bytes sent and percentage progress.
- The completed ZIP is streamed from disk rather than loaded into backend or
  browser memory.
- Temporary ZIP files are stored below `/data/userfiles/.cache/downloads`, a
  hidden cache path already excluded by the gallery backup scanner.
- Completed archives are removed immediately. Abandoned archives expire after
  four hours and are removed automatically.
- Each file download uses an unguessable short-lived ticket; admin and share
  session tokens are not placed in the file URL.
- Only one active job per viewer is allowed, with a small global concurrency
  limit and a free-space check before preparation.

## What does not change

- Original gallery files, MongoDB records, share links and passwords.
- Individual file downloads, favourites, cover selection, uploads, video
  playback or backup behaviour.
- The existing legacy ZIP routes remain available for compatibility; the live
  admin and client interfaces use the new progress-aware route.

## Rollback

Retag the backend and frontend rollback images created before deployment, then
force-recreate only those two services. No data migration is required.
