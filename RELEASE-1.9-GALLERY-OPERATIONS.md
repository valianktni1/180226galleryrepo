# Release 1.9 - Gallery operations safety

Release 1.9 adds three admin safeguards without changing the couple-facing
gallery experience.

## Gallery Ready check

- `Notify Couple` now opens a final checklist and previews the exact recipient,
  gallery URL and password.
- Critical problems block the email and are rechecked by the backend at send
  time.
- Backup or thumbnail delays are advisory warnings and do not block delivery.
- Videos are deliberately excluded. Mark can deliver photographs promptly and
  add video later.

## Video processing queue

- System Health shows queued and active video files with the gallery name,
  filename, processing method and live percentage.
- Existing thumbnail and transcoding behaviour is retained.

## Safe maintenance scan

- The scan runs only when requested from System Health.
- It reports missing originals, orphan thumbnails/previews, orphan web-video
  copies, interrupted temporary video files and stale download ZIPs.
- The scan is read-only: it cannot delete, rename, move or repair anything.
