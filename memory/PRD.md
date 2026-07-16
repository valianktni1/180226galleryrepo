# Wedding Photography Gallery Management System — PRD

## Original Problem Statement
Full-featured, self-hosted wedding photography client gallery management system with admin-managed galleries, chunked large file uploads/downloads, robust sharing, password protection, branded QR codes, cinematic slideshows, activity logging, and optimized video streaming.

## Architecture
- **Backend**: FastAPI, Motor (MongoDB), Pillow, FFmpeg (VAAPI Hardware encoding with CPU fallback), SMTP email, psutil (network monitoring)
- **Frontend**: React, Tailwind CSS, Shadcn/UI, video.js, Framer Motion, Fetch API streaming
- **Infrastructure**: Docker Compose on TrueNAS, NGINX direct video serving, Dockge management
- **Hardware**: Minisforum UM780XTX (AMD Radeon 780M iGPU) for GPU-accelerated transcoding

## Deployment
User deploys on TrueNAS via Dockge:
1. "Save to Github" in Emergent
2. `docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml down`
3. `docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml build --no-cache backend frontend`
4. `docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml up -d`

## Completed Features
- [x] Admin-managed galleries with chunked uploads
- [x] Share links with password protection
- [x] Dark/Light mode toggle (Classic Timeless theme)
- [x] Cinematic Ken Burns slideshow with custom audio
- [x] CSS-based watermarks on photo previews (clean downloads)
- [x] video.js integration for robust playback
- [x] Direct NGINX video serving (bypasses Python)
- [x] Background FFmpeg transcoding (5Mbps .web.mp4 streams)
- [x] "Optimise Videos for Web" admin button with progress polling
- [x] Visual download progress overlay for large files
- [x] Activity logging with exact file download tracking
- [x] Multi-design PDF QR code frame generator
- [x] VAAPI hardware-accelerated transcoding (Radeon 780M) with CPU fallback
- [x] Thumbnail generation before transcoding — instant UI feedback
- [x] Real-time per-file transcoding progress bar on video cards in admin panel
- [x] Toolbar transcoding status indicator for auto-upload transcodes
- [x] Separate thread pools — thumbnail_executor (8 workers) + transcode_executor (2 workers)
- [x] Activity page search bar
- [x] Email notification system — SMTP settings, "Notify Couple" button
- [x] Branded HTML email template with gallery link, password, album instructions
- [x] "Download All Images" bold CTA button on share album view
- [x] Progressive Image Loading (ProgressiveImage component) + Smart preloading in lightbox
- [x] Activity Log Auto-Archiving (>6 months), manual clear, Archive Tab
- [x] Live Visitors Panel on AdminDashboard (30s heartbeats, real-time session tracking)
- [x] Broadcast Email system
- [x] Automated Expiry Reminder Emails (daily background task)
- [x] Email Log tracking with "Emails" tab on Activity page
- [x] Backup-aware delete with confirmation dialog
- [x] Email Templates system with {couple_name} and {gallery_link} tokens
- [x] Awards badge in all branded emails
- [x] Dashboard stats redesign — 5 cards
- [x] Live visitors wording improved
- [x] Network & Storage Monitor panel — Total storage (GB/TB), Daily & Weekly bandwidth, Video streaming bandwidth, Download bandwidth (2026-07-06)
- [x] Application-level bandwidth tracking — logs video stream file sizes and download sizes (2026-07-06)
- [x] Background network snapshot task (every 15 minutes) with auto-cleanup (2026-07-06)
- [x] **Gallery Visual Themes** — 5 presets: Classic Gold, Modern Minimal, Dark Elegance, Soft Romantic, Earthy Botanical (2026-07-06)
  - Theme picker in Create Gallery dialog (5 colour-dot buttons)
  - Theme picker dropdown on Gallery Detail page header
  - ShareView dynamically renders using selected theme (colours, fonts, accents)
  - All themes have full light + dark mode palettes
  - Existing galleries default to Classic Gold (backwards compatible)

## In Progress
None

## Recently Completed (2026-07-08)
- [x] **Font Preloading** — Moved Google Fonts (Cormorant Garamond + Manrope) from render-blocking CSS `@import` to `<link rel="stylesheet">` in HTML `<head>` with `preconnect` hints. Removed unused Inter font. Faster text rendering on first visit.
- [x] **React.lazy() Code Splitting** — Lazy-loaded Slideshow, VideoPlayer, and GuestUploadView components in ShareView.js. Reduces initial JS bundle for couples, loading heavy components only when needed.
- [x] **Preconnect Hints** — Already existed for Google Fonts CDN (confirmed and kept).
- [x] **Database Indexes** — Already existed for all key collections (confirmed: files, favourites, shares, activity_log, etc.).

## Recently Completed (2026-07-16)
- [x] **Email Attachment Bug Fix** — Fixed file picker in Send Email dialog (AdminGalleryDetail.js) and Broadcast Email dialog (AdminDashboard.js). Replaced `<label>` wrapping hidden `<input type="file">` with explicit `<button>` + `useRef` pattern to bypass Radix Dialog focus-trapping issue. Attachments now show filename + size as visual pills before sending. Backend multipart endpoint verified working.
- [x] **PWA (Progressive Web App)** — Added manifest.json, service worker, Apple meta tags, and generated app icons from the WBM logo. Couples can now "Add to Home Screen" on iPhone/Android for a native app-like experience (full-screen, no browser bar, custom icon). Service worker caches fonts and static assets for faster repeat visits.

## Recently Completed (2026-07-07)
- [x] P0 Download Bug Investigation — Code logic verified correct, all downloads work in preview (13/13 backend tests pass). Issue is environment-specific to TrueNAS production.
- [x] Added comprehensive diagnostic logging to ALL download endpoints (album ZIP, POST ZIP, admin ZIP, favourites ZIP, single file) — logs file counts, missing files, parent directory contents
- [x] Added `GET /api/admin/diagnose-gallery/{gallery_id}` diagnostic endpoint — compares DB file records vs actual disk files, shows mismatches
- [x] Added startup logging showing UPLOAD_DIR and gallery directories on disk
- [x] Fixed photo overlay pointer-events blocking image clicks in ShareView

## Backlog
None — all previous backlog items cancelled per user request.

## Key Files
- `/app/backend/server.py` — All APIs, FFmpeg, SMTP email, NGINX signed URLs, network monitoring
- `/app/frontend/src/lib/themes.js` — Gallery theme presets (5 themes with light/dark modes)
- `/app/frontend/src/pages/AdminDashboard.js` — Dashboard with stats, network monitor, live visitors, theme picker in create dialog
- `/app/frontend/src/pages/AdminGalleryDetail.js` — Gallery management, theme picker dropdown, notify, transcode
- `/app/frontend/src/pages/AdminSettings.js` — Settings page with Email Settings tab
- `/app/frontend/src/pages/AdminActivity.js` — Activity log with name search
- `/app/frontend/src/pages/ShareView.js` — Client-facing view (theme-driven colours/fonts)
- `/app/frontend/src/lib/api.js` — API client

## Key API Endpoints
- `GET /api/admin/dashboard-stats` — 5 key stats
- `GET /api/admin/network-stats` — Network bandwidth (daily/weekly/video/downloads)
- `GET /api/admin/diagnose-gallery/{gallery_id}` — **NEW** Diagnostic: compare DB files vs disk files for a gallery
- `POST /api/admin/broadcast-email` — Mass email
- `GET/POST/PUT/DELETE /api/admin/email-templates` — Template CRUD
- `GET /api/admin/email-log` — Email history
- `PUT /api/admin/galleries/{id}` — Accepts `theme` field for gallery theme updates

## Database Collections
- `admin`, `galleries` (now includes `theme` field), `files`, `shares`, `favourites`, `activity_log`, `activity_log_archive`
- `email_log`, `email_templates` (custom email templates), `templates` (gallery templates)
- `settings` (SMTP, compression, site_url)
- `print_sizes`, `print_orders`
- `network_snapshots` — periodic network counter readings for bandwidth calculation
- `bandwidth_log` — application-level bandwidth events (video streams, file downloads)

## Gallery Themes
| Theme | Accent | Heading Font | Body Font |
|-------|--------|-------------|-----------|
| Classic Gold | #D4AF37 | Cormorant Garamond | Manrope |
| Modern Minimal | #0A0A0A | Manrope | Manrope |
| Dark Elegance | #C9A96E | Cormorant Garamond | Manrope |
| Soft Romantic | #C77D8A | Cormorant Garamond | Manrope |
| Earthy Botanical | #6B8F71 | Cormorant Garamond | Manrope |

## 3rd Party Integrations
- PayPal (Payments) — Direct link redirect
- Google Authenticator (Auth) — pyotp local library
- SMTP (Email) — User's own Hostinger email
