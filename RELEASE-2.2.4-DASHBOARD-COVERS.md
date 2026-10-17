# Release 2.2.4 — Lazy Dashboard Covers

This is a small frontend-only performance release. It does not change the backend, database, couples' galleries, gallery files, downloads, backups, album choices or voice messages.

## Improvement

- Admin dashboard cover photographs now use native browser lazy loading.
- Covers near the visible part of the dashboard load normally; covers further down wait until the administrator scrolls towards them.
- Cover decoding is asynchronous so image decoding does not unnecessarily block the dashboard interface.
- The dashboard layout, ordering, search, statistics and gallery navigation remain unchanged.

## Verification

- A focused Release 2.2.4 check protects the lazy-loading and asynchronous-decoding attributes.
- The existing Release 2.2, 2.2.2 and 2.2.3 frontend checks continue to run.
- The production frontend build must succeed before the live frontend container is replaced.

## Rollback

The deployment script retains the current frontend image as:

- `wbm-frontend:rollback-before-release-2.2.4`

Only the frontend container is replaced. No database migration is performed and no photographs, videos or voice messages are rewritten.
