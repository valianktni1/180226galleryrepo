# Wedding Photography Gallery Management System — PRD

## Original Problem Statement
Full-featured, self-hosted wedding photography client gallery management system with admin-managed galleries, chunked large file uploads/downloads, robust sharing, password protection, branded QR codes, cinematic slideshows, activity logging, and optimized video streaming.

## Architecture
- **Backend**: FastAPI, Motor (MongoDB), Pillow, FFmpeg (VAAPI Hardware encoding with CPU fallback), SMTP email
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
- [x] .gitignore cleanup (removed 114MB test video bloat)
- [x] VAAPI hardware-accelerated transcoding (Radeon 780M) with CPU fallback
- [x] Thumbnail generation before transcoding — instant UI feedback
- [x] Real-time per-file transcoding progress bar on video cards in admin panel
- [x] Toolbar transcoding status indicator for auto-upload transcodes
- [x] Separate thread pools — thumbnail_executor (4 workers) + transcode_executor (2 workers)
- [x] Activity page search bar — search by couple name across share labels, gallery names, details
- [x] Email notification system — SMTP settings page, couple's email on galleries, "Notify Couple" button
- [x] Branded HTML email template with gallery link, password, album instructions, and photographer sign-off

- [x] "Download All Images" bold CTA button on share album view
- [x] Progressive Image Loading (ProgressiveImage component) + Smart preloading in lightbox
- [x] Increased thumbnail_executor from 4→8 workers + 5s auto-refresh polling for thumb generation
- [x] Activity Log Auto-Archiving (>6 months), manual clear, Archive Tab
- [x] Live Visitors Panel on AdminDashboard (30s heartbeats from ShareView, real-time active session tracking)
- [x] BUG FIX: Temporal dead zone crash in ShareView.js — useEffect referenced displayFiles before declaration, breaking all share links (fixed 2026-06-30)
- [x] BUG FIX: ProgressiveImage blur in grid cards — FileCard now uses direct preview img tag, ProgressiveImage only in lightbox (fixed 2026-06-30)
- [x] Broadcast Email system — Dashboard button opens dialog with recipients preview, subject/body fields, sends branded HTML to all couples with emails (2026-06-30)
- [x] Automated Expiry Reminder Emails — Daily background task checks for main share links expiring within 7 days, auto-sends branded reminder email to couples (2026-06-30)
- [x] Reusable SMTP helper (send_smtp_email) and branded email template wrapper (build_branded_email)
- [x] Email Log tracking — all sent emails (broadcast, gallery-ready, expiry reminders) logged to db.email_log with "Emails" tab on Activity page (2026-06-30)
- [x] Backup-aware delete — Gallery and file deletion now shows confirmation dialog with "Also delete from backup?" checkbox (2026-06-30)

## In Progress
None

## Prioritized Backlog
- **P1**: Replace "Floral" QR design with "Minimal" variation
- **P2**: Client comments on favourited photos
- **P4**: Modularize server.py (~3000+ lines -> routes/)

## Future Ideas (Discussed with User)
- Magic Links (password-free access via email/SMS)
- Sneak Peek Mode (preview 10-15 photos before full gallery)
- Couple's Dual Favouriting (bride + groom each pick favourites, show matches)
- AI Face Grouping (guests find their photos by selfie)
- Anniversary Email (auto-email couple on anniversary with slideshow link)
- Phone Wallpaper Pack (pre-cropped downloads)
- Social Media Export (Instagram/Stories/Facebook crops)
- Wedding Day Timeline (EXIF-based photo chronology)

## White-Label Resale Version
User is building a separate white-label version for resale to other photographers. Details in `/app/memory/white-label-handoff.md`. Key requirements:
- Configurable branding (business name, logo, accent colour)
- Admin settings page per instance
- Super admin panel for platform owner (suspend/reactivate accounts)
- Per-customer Docker Compose stacks on TrueNAS (2x 8TB mirrored HDDs for customer data)

## Key Files
- `/app/backend/server.py` — All APIs, FFmpeg, SMTP email, NGINX signed URLs
- `/app/frontend/src/pages/AdminSettings.js` — Settings page with Email Settings tab
- `/app/frontend/src/pages/AdminGalleryDetail.js` — Gallery management, notify button, transcode progress
- `/app/frontend/src/pages/AdminDashboard.js` — Gallery creation with client email field
- `/app/frontend/src/pages/AdminActivity.js` — Activity log with name search
- `/app/frontend/src/pages/ShareView.js` — Client-facing view
- `/app/frontend/src/lib/api.js` — API client

## Key API Endpoints
- `GET /api/admin/settings/smtp` — Get SMTP config (password masked)
- `POST /api/admin/settings/smtp` — Save SMTP config
- `POST /api/admin/settings/smtp/test` — Send test email
- `POST /api/admin/galleries/{id}/notify` — Send gallery-ready email to couple
- `GET /api/admin/galleries/{id}/transcode-status` — Per-file transcoding progress
- `GET /api/admin/activity?search=name` — Search activity by name

## 3rd Party Integrations
- PayPal (Payments) — Direct link redirect (MOCKED)
- Google Authenticator (Auth) — pyotp local library
- SMTP (Email) — User's own Hostinger email (mark@perfectweddingsbymark.uk)

## Database Collections
- `admin` — Admin user (username, hashed password, TOTP secret)
- `galleries` — Gallery metadata (+ client_email, notification_sent_at)
- `files` — File records
- `shares` — Share links (+ password_raw for email notifications)
- `favourites` — Client favourited photos
- `activity_log` — View/download tracking
- `templates` — Gallery templates
- `settings` — App settings (key: "smtp", key: "compression")
