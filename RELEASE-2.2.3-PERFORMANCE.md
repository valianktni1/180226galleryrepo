# Release 2.2.3 — Admin Performance

This is a focused performance release. It does not change the couples' gallery design, album workflow, voice-message workflow, downloads, backups or stored gallery data.

## Improvements

- Personal voice messages, documents and other files that never receive thumbnails can no longer trigger repeated gallery refreshes.
- Thumbnail refreshes are restricted to photographs and videos and stop after a finite retry period if processing fails.
- Opening an admin gallery now makes one initial gallery request instead of loading the same gallery again when the first folder tab is selected.
- Dashboard share counts, covers and visitor statistics are collected in batched MongoDB queries instead of running database queries separately for every gallery.
- Existing dashboard response fields and cover-selection priority are preserved.

## Verification

- New backend structure tests prevent database calls from being reintroduced inside the per-gallery loops.
- New frontend checks protect the thumbnail-file filter, retry limit and stable gallery loader.
- The deployment script builds from the exact tested commit and replaces the live containers only after backend, frontend and regression checks succeed.

## Rollback

The deployment script retains the current images before switching containers:

- `wbm-backend:rollback-before-release-2.2.3`
- `wbm-frontend:rollback-before-release-2.2.3`

No database migration is performed and no original photographs, videos or voice messages are rewritten.
