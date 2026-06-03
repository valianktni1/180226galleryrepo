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
- RAW/XMP files visible in admin panel with FileText icon, hidden from guest shares

### Video Thumbnail Previews (June 2026)
- Extracts a frame from each uploaded video using ffmpeg on upload
- Shows video thumbnail with play icon overlay in both admin and client/share views
- Filename remains visible on video cards
- Works for both admin uploads and guest uploads
- Background processing via ThreadPoolExecutor (non-blocking)

### Video Playback in Share View (June 2026)
- Inline video player in lightbox (replaces black screen)
- Streaming endpoint with HTTP Range request support for seeking
- Native browser video controls (play, pause, volume, fullscreen, scrub)
- Endpoint: `GET /api/share/{token}/stream/{file_id}?t={jwt}`

### QR Code Frame Generator (3 Designs)
- **Design 1 - Botanical:** Gold botanical corners background, Minimal text layout
- **Design 2 - Hearts:** Decorative hearts border, Wavy text layout
- **Design 3 - Minimal:** Clean "Share the Love" heading, centered script name
- Dynamic QR code, couple name, and date overlay
- Branded footer: "Designed and hosted by Weddings By Mark"
- Frontend design selector with thumbnail previews

### Activity Log (Enhanced Downloads)
- Detailed download tracking in all download endpoints (single, zip, album, favourites)
- Logs: exact filenames, download count, completeness (full/partial/single), IP, share label
- Frontend: expandable file lists, colour-coded badges, action filter dropdown

### Bug Fixes
- TrueNAS disaster recovery
- Hidden RAW files in admin UI
- Dockerfile: Added `fonts-liberation` for QR PDF generation in Docker
- Removed unused numpy dependency (was crashing Docker builds on TrueNAS)
- Fixed missing Play icon import in ShareView.js

## Key API Endpoints
- `POST /api/admin/login` — Admin login
- `GET /api/admin/galleries` — List all galleries
- `POST /api/admin/galleries/{gallery_id}/upload` — Upload files (with video thumbnail gen)
- `GET /api/admin/shares/{share_id}/qr-frame` — Generate printable QR frame PDF
- `GET /api/share/{token}/stream/{file_id}` — Stream video with range support
- `GET /api/media/thumb/{gallery_id}/{subfolder}/{filename}` — Serve thumbnail
- `GET /api/media/preview/{gallery_id}/{subfolder}/{filename}` — Serve preview

## Backlog / Future Tasks
- **P1:** New decorated QR code design (replace Botanical with Pillow-drawn elegant design)
- **P1:** Email Notifications when clients submit album favourites
- **P2:** Slideshow Mode for client gallery view
- **P3:** Client Comments on favourited photos
- **P4:** Watermark Previews (not affecting downloads)
- **P5:** Dark Mode for client gallery view
- **Refactoring:** Modularize server.py into route files (2600+ lines)

## Critical Rules
- NEVER modify `/s/{token}` URL structure (live physical QR codes exist)
- NEVER delete existing shares
- User deploys manually on TrueNAS via Docker Compose
- PayPal integration is MOCKED (paypal.me link redirect)

## Deployment Commands
```bash
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml down
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml build --no-cache
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml up -d
```
