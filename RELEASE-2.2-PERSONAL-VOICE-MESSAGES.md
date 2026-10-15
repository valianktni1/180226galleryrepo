# Release 2.2 — Personal Voice Messages

Release 2.2 adds an optional voice-message journey to the existing guest QR page. The established photo and video upload route remains unchanged.

## Guest experience

- Guests choose **Upload Photos & Videos** or **Record Your Personal Message**.
- The choice and recorder follow the gallery light/dark preference.
- Recording includes a live timer, a warning at 3:30 and an automatic stop at 4:00.
- Guests can listen, re-record and must enter their name before sending.
- The server validates and converts the browser recording to a normalised stereo 192 kbps, 48 kHz MP3.
- Only the final MP3 is retained; the temporary browser upload is removed after conversion.

## Gallery and storage

- The first successful recording adds a gallery folder named **Personal Voice Messages**.
- Its physical path is nested safely under `Guest Uploads/Personal Voice Messages`.
- Voice messages show the guest name and duration in admin and couples' galleries.
- Couples can listen, download individual MP3s or use **Download All**.
- Existing gallery backup recursion includes the final MP3 files.
- The existing 90-day Guest Upload file cleanup does not target this separate database subfolder.

## Safety

- Voice recording is available only on guest-upload QR shares, not photographer file-upload shares.
- Authentication, gallery scoping and path-containment helpers are retained.
- Upload size, duration, content-type and per-token/IP rate limits are enforced.
- FFmpeg conversion runs off the API event loop and uses the shared heavy-work coordinator.
- A dedicated authenticated playback route does not grant general download permission.

## Rollback

The deployment script retains these images before switching containers:

- `wbm-backend:rollback-before-release-2.2`
- `wbm-frontend:rollback-before-release-2.2`

Existing images, videos, galleries and shares are not migrated or rewritten by this release.
