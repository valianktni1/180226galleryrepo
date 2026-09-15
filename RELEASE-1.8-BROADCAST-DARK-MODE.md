# Release 1.8 - Paced Broadcasts and Admin Dark Mode

This release makes bulk couple emails safer for the configured mail account and adds a persistent dark theme to every authenticated admin screen. Couple galleries and one-to-one emails are unchanged.

## Paced broadcasts

- Broadcasts are queued durably in MongoDB instead of being sent inside one long web request.
- At most 10 recipients are processed per batch, followed by a two-minute gap.
- Duplicate email addresses are contacted only once, even if they appear on multiple galleries.
- The admin dialog shows live sent, waiting and failed totals plus the next-batch countdown.
- A campaign can be paused, resumed or cancelled without contacting its remaining recipients.
- Queue progress survives a page refresh and normal backend restart.
- A recipient whose delivery state is uncertain after an unexpected restart is not automatically resent.
- Attachments are limited to 15 MB in total, stored in the hidden application cache and removed when the campaign finishes, fails or is cancelled.
- Subjects and attachment names are protected against email-header injection, and editor text is HTML-escaped.
- Individual gallery-ready, cover-selection, QR and expiry emails continue to send normally.

Email-provider plan limits and acceptable-use rules still apply. Pacing prevents one large burst but does not turn the gallery into a marketing-mail platform.

## Admin dark mode

- A Light/Dark switch is available on Dashboard, Gallery Detail, Settings, Activity and System Health.
- The preference is retained in that browser.
- Admin backgrounds, panels, dialogs, menus, forms, tables and neutral text use a coordinated dark palette.
- Status colours, photographs and previews retain their intended appearance.
- The dark class is removed when leaving the admin application, so client gallery themes cannot be affected.

## Health and deployment

- System Health includes an active paced broadcast in its background-work total and shows campaign progress without exposing recipients or message content.
- Both backend and frontend images must be rebuilt and recreated.
- No gallery files, shares, favourites or existing email records are migrated or deleted.
