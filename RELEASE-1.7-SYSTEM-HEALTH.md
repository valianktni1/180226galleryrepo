# Release 1.7 - Read-only System Health

This release adds an admin-only System Health screen without changing any couple-facing gallery behaviour.

## What it shows

- Gallery API and MongoDB connection status.
- Gallery storage usage and free capacity.
- Whether email is configured (without exposing any SMTP details).
- Whether the AMD render device and FFmpeg are available.
- Current video optimisation, folder-download, backup and visitor activity.
- The last in-app gallery backup result, retained across backend restarts.
- Clear labels for MongoDB and off-site backups that are managed externally by TrueNAS and are not inspected by this app.

## Safety

- The endpoint requires normal administrator authentication.
- No secrets, tokens, client names, file paths or job owners are returned.
- The screen contains no restart, delete, repair or configuration controls.
- It refreshes every 15 seconds using lightweight checks and does not send test email or start GPU work.
- Storage status becomes amber at 85% used and red at 95% used.

## Deployment scope

Both backend and frontend images must be rebuilt and recreated. MongoDB and gallery files are not migrated or modified.
