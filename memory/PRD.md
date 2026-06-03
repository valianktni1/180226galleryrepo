# Wedding Photography Gallery - PRD

## Original Problem Statement
Self-hosted wedding photography client gallery management system. Full-featured admin panel with gallery management, chunked file uploads/downloads, robust sharing, password protection, print shop, and QR code generation.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI + Motor (async MongoDB) + Pillow
- **Deployment:** Docker Compose on TrueNAS (user's own server)
- **Auth:** JWT + optional TOTP 2FA via pyotp

## Implemented Features

### Core Gallery System
- Admin-managed galleries with subfolders
- Chunked large file uploads/downloads
- Share links with password protection and expiry
- Guest upload capability
- Print shop with size selection

### Two-Factor Authentication (2FA)
- Google Authenticator TOTP via pyotp
- QR setup, recovery codes, admin settings UI

### Photographer Upload Mode
- Toggle `allow_all_file_types` on shares for second shooters
- Streaming uploads: chunks streamed directly to SSD (no memory buffering)
- RAW/XMP files visible in admin panel, hidden from guest shares

### Video Thumbnail Previews (June 2026)
- Extracts a frame from each uploaded video using ffmpeg on upload
- Shows video thumbnail with play icon overlay in both admin and client/share views
- Filename remains visible on video cards

### Video Playback in Share View (June 2026)
- Inline video player in lightbox (replaces previous black screen)
- Streaming endpoint with HTTP Range request support for seeking
- Native browser video controls (play, pause, volume, fullscreen, scrub)
- Endpoint: `GET /api/share/{token}/stream/{file_id}?t={jwt}`

### Cinematic Slideshow Mode (June 2026)
- Wedding Images subfolder only, main shares only (not guest upload shares)
- Cinematic intro card with couple name, gold accents, "X moments" count
- Random 2-4 second slide duration
- 2 random transition types: crossfade + softSlide (0.7s transition time)
- Random Ken Burns zoom/pan from 8 preset variants
- Ambient romantic piano music via Web Audio API (chord progression: Cmaj7→Am7→Fmaj7→Gsus4→Em7→Am→Dm7→G7)
- Controls: music toggle, play/pause, close — frosted glass circles, auto-hide after 3s
- Keyboard shortcuts: Escape=close, Space=pause/resume, M=toggle music
- Progress dots (for ≤30 photos) or counter (for >30)
- Couple name watermark at bottom, "Weddings By Mark" branding top-left
- Cinematic gradient overlays and vignette effect

### QR Code Frame Generator (3 Designs)
- Design 1 - Botanical, Design 2 - Hearts, Design 3 - Minimal
- Dynamic QR code, couple name, and date overlay
- Branded footer

### Activity Log (Enhanced Downloads)
- Detailed download tracking in all download endpoints
- Logs: exact filenames, download count, completeness, IP, share label
- Frontend: expandable file lists, colour-coded badges, action filter dropdown

## Key API Endpoints
- `POST /api/admin/login` — Admin login
- `GET /api/admin/galleries` — List all galleries
- `POST /api/admin/galleries/{gallery_id}/upload` — Upload files
- `GET /api/admin/shares/{share_id}/qr-frame` — Generate QR frame PDF
- `GET /api/share/{token}/stream/{file_id}` — Stream video with range support
- `GET /api/media/thumb/{gallery_id}/{subfolder}/{filename}` — Serve thumbnail
- `GET /api/media/preview/{gallery_id}/{subfolder}/{filename}` — Serve preview

## File Structure
```
/app
├── backend/
│   ├── assets/ (qr_templates, fonts)
│   ├── server.py
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/src/
│   ├── lib/api.js (videoStreamUrl helper)
│   └── pages/
│       ├── Slideshow.js (NEW - cinematic slideshow component)
│       ├── AdminGalleryDetail.js (video thumbnails)
│       ├── AdminActivity.js (download logs)
│       └── ShareView.js (video playback, slideshow integration)
└── memory/PRD.md
```

## Backlog / Future Tasks
- **P1:** New decorated QR code design (replace Botanical with Pillow-drawn elegant design)
- **P1:** Email Notifications when clients submit album favourites
- **P3:** Client Comments on favourited photos
- **P4:** Watermark Previews (not affecting downloads)
- **P5:** Dark Mode for client gallery view
- **Refactoring:** Modularize server.py into route files (2600+ lines)

## Critical Rules
- NEVER modify `/s/{token}` URL structure (live physical QR codes exist)
- NEVER delete existing shares
- User deploys on TrueNAS via Docker Compose
- PayPal integration is MOCKED (paypal.me link redirect)

## Deployment Commands
```bash
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml down
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml build --no-cache
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml up -d
```
