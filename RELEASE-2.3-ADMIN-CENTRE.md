# Release 2.3 — Admin Centre

Release 2.3 keeps the existing couple experience unchanged and gives the admin side three connected improvements.

## Notification Centre

- Groups new guest photographs and clips by gallery and day.
- Shows personal voice messages, album submissions, expiring links and completed couple downloads.
- Provides unread counts, filters, mark-all-read and dismiss controls.
- Links every update directly to the relevant gallery.
- Notification failures never block a guest upload, voice message, album submission or download.

## Gallery Journey

Every gallery now has a simple status:

1. Uploading
2. Ready
3. Delivered
4. Album Choices Received (only when an album is enabled)
5. Archived

Ready and Archived are manual admin choices. Delivered advances automatically when the gallery-ready email succeeds. Album Choices Received advances automatically when the couple submits a valid album. Existing galleries infer their correct starting status without a migration.

## Mobile Admin Navigation

A fixed phone-sized menu provides instant access to Galleries, Uploads, Activity, Health and Settings. Uploads displays an unread badge and respects phone safe areas.

## Safety and compatibility

- Existing gallery, share, download, backup, email, album and guest-upload workflows remain intact.
- Gallery deletion also removes its admin notifications.
- Notification and workflow collections use targeted MongoDB indexes.
- Desktop navigation remains unchanged.
