# Release 1.4.1 - Guest Upload Web-Copy Cleanup

## Purpose

This small backend-only release closes a gap in the existing 90-day Guest
Uploads cleanup. When an expired guest-uploaded video is removed, its generated
web-playback copy is now removed at the same time.

## What changes

- Deletes the expired Guest Upload video's live sibling `*.web.mp4`.
- Deletes the same generated `*.web.mp4` from the mounted backup dataset.
- Continues deleting the original Guest Upload, thumbnail, preview and database
  record exactly as before.

## Strict scope

The cleanup query and all constructed paths remain fixed to the exact
`Guest Uploads` subfolder. This release does not scan or remove generated videos
from `Video`, `Wedding Images`, custom folders or any other gallery location.

It does not alter:

- the existing 90-day retention period;
- guest-upload link expiry;
- video transcoding or GPU acceleration;
- the Release 1.4 original-only backup process;
- photographs, main gallery videos, shares, favourites, selections or emails.

## Existing unmatched backup files

This release handles future database-driven expiry cleanups. It deliberately
does not bulk-delete the 33 unmatched `*.web.mp4` files already identified in
the backup dataset. Those remain untouched for separate, carefully scoped
review.

## Verification

The included regression test proves that the cleanup:

- still queries only `subfolder: Guest Uploads`;
- derives and deletes the live generated web copy;
- derives and deletes the backup generated web copy;
- keeps both original-file paths fixed to `Guest Uploads`.
