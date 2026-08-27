# Gallery-ready email hotfix

## Problem

The **Notify Couple** endpoint selected the first active share for a gallery.
When a QR guest-upload share existed, that share could be selected instead of
the password-protected main client gallery.

## Fix

The endpoint now requires an active share that is:

- not a guest-upload/QR share;
- for the whole gallery, not one subfolder; and
- configured for `download` or `full` access.

If no matching main share exists, the email is not sent and the admin receives
a clear error. The email continues to include the main share password.

## Deployment scope

Only the backend changed. Existing galleries, media, passwords, share links,
MongoDB data, backups, frontend code and GPU video processing are untouched.

From the Dockge host, rebuild only the backend service for the existing stack,
then verify its logs before sending the client email again.
