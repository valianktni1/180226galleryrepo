# Release 1.8.1 - Clear album cover filename

This backend-only release makes the couple's chosen album cover immediately
obvious when the **Album Favourites** folder is downloaded.

## What changes

- The selected cover appears inside the downloaded ZIP as
  `COVER - original-filename.jpg`.
- Every other downloaded filename remains unchanged.
- The behaviour applies to both the admin and couple folder-download buttons.

## Safety

- The live gallery file is not renamed or moved.
- Database records, thumbnails and previews are not changed.
- Choosing a different cover automatically marks the new choice in the next
  download.
- Galleries without a cover choice behave exactly as before.

Only the backend image needs to be rebuilt and recreated for this release.
