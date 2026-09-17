# Release 1.9.1 - Updated Awards Badge

This small backend-only release replaces the awards artwork used in branded
emails with the combined 2023-2027 Weddings By Mark awards panel.

## What changed

- Replaced `backend/assets/awards-badges.png` with the supplied artwork.
- Optimised the asset as a genuine 960 x 640 PNG at under 200 KB.
- Kept the existing responsive 480-pixel email presentation unchanged.
- Added a version marker to the public image URL so long-lived email proxy
  caches fetch the new artwork.
- Added focused checks for the PNG type, dimensions, file-size limit, and
  versioned email URL.

## Deployment scope

Only the backend image needs rebuilding and recreating. Gallery data, MongoDB,
the frontend, live share links, favourites, downloads, and videos are not
changed by this release.
