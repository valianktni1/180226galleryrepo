# Release 1.3 - Clear Folder Downloads

This frontend-only release makes the existing bulk-download option easier for
couples to find without changing how any files are downloaded.

## What changes

- Opening or leaving a folder reliably resets the page to the top, including
  after the new view has been painted.
- Every downloadable, non-empty folder receives the same prominent button
  above its files.
- The button explains exactly what it downloads, for example **Download All
  740 Images**, **Download All 3 Videos**, or **Download All 44 Guest Uploads**.
- The existing sticky folder header keeps a compact download control. On small
  screens it displays only the download icon and **All (count)** so it does not
  cover or distract from the gallery.
- The slideshow control is icon-only on small screens, leaving the compact
  download control enough room to remain visible.

## What does not change

- The existing `handleDownloadAlbum` download path and API endpoint.
- Individual downloads, favourites, album submission or cover selection.
- Guest uploads, video streaming or GPU transcoding.
- Backend code, API routes, MongoDB, media files, backups or permissions.

Only the frontend image needs to be built and recreated for this release.

## Protected deployment

`deploy-release-1.3.sh` performs the release as one protected frontend-only
deployment. It:

1. Confirms the current frontend is running.
2. Tags its exact image with a timestamped rollback name.
3. Builds Release 1.3 as an isolated test image.
4. Checks NGINX, the existing IPv4 resolver fix, removed public handoff files,
   and the new download-control text inside the finished image.
5. Recreates only `wbm-frontend`.
6. Checks the public application and recent frontend logs.
7. Automatically restores the previous image if a post-deployment check fails.

The backend, MongoDB and video NGINX containers are not recreated. The script
does not read, write or remove any gallery media or database records.
