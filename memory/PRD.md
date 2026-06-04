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
- Guest upload capability, print shop with size selection

### Video Thumbnail Previews + Playback
- Extracts frame on upload via ffmpeg, shows in admin + share views
- Inline video player in lightbox with HTTP Range streaming

### Cinematic Slideshow with Music Picker
- Music picker screen: 3 tracks (Romantic, Cinematic, Eternity) with 12s preview snippets
- "Continue without music" option available
- MP3 tracks served from backend with range request support for streaming
- Music fades in during intro, loops continuously, fades out on close
- Dual-layer crossfade system, 6s display, 2s crossfade
- Ken Burns starts zoomed out (contain mode), slowly drifts in over 9s
- 8 random presets, keyboard controls (Esc/Space/M)
- Wedding Images subfolder only, main shares only

### Client Share Landing Page — Design A Classic
- Full-width hero using Wedding Images cover photo as blurred background
- Elegant serif couple name with gold diamond dividers
- Album cards with cover photos, gradient overlay, hover effects
- All functionality preserved: instructions, order prints, favourites, guest uploads

### QR Code Frame Generator (3 Designs)
- Botanical, Hearts, Minimal with dynamic QR/name/date overlay

### Activity Log (Enhanced Downloads)
- Detailed tracking in all download endpoints with frontend badges

### Other
- 2FA via pyotp, Photographer upload mode, RAW/XMP support
- Removed unused numpy (TrueNAS fix)

## Key API Endpoints
- `POST /api/admin/login` — Admin login
- `POST /api/admin/galleries/{gallery_id}/upload` — Upload with video thumbnail gen
- `GET /api/share/{token}/stream/{file_id}` — Video streaming
- `GET /api/slideshow/music/{filename}` — Serve slideshow MP3 tracks
- `GET /api/media/thumb|preview/{gallery_id}/{subfolder}/{filename}` — Media serving

## File Structure
```
/app/backend/
├── assets/
│   ├── slideshow_music/ (romantic.mp3, cinematic.mp3, eternity.mp3)
│   ├── qr_templates/
│   └── fonts/
├── server.py, Dockerfile, requirements.txt
/app/frontend/src/
├── lib/api.js (slideshowMusicUrl helper)
└── pages/
    ├── Slideshow.js (music picker + cinematic slideshow)
    ├── ShareView.js (redesigned landing, video playback)
    ├── AdminGalleryDetail.js, AdminActivity.js
```

## Backlog
- P1: New decorated QR design (Pillow-drawn)
- P1: Email notifications on album favourites submission
- P3: Client comments on favourited photos
- P4: Watermark previews
- P5: Dark mode
- Refactoring: Modularize server.py

## Deployment
```bash
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml down
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml build --no-cache
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml up -d
```
