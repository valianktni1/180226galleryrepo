# Wedding Photography Gallery - PRD

## Original Problem Statement
Self-hosted wedding photography client gallery management system with admin panel, sharing, downloads, print shop, slideshow, and QR codes.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI + Motor (async MongoDB) + Pillow
- **Deployment:** Docker Compose on TrueNAS

## Implemented Features

### Core: Galleries, uploads, sharing, password protection, print shop, 2FA, guest uploads

### Video: Thumbnails on upload (ffmpeg), inline playback with Range streaming

### Cinematic Slideshow with Music Picker + Shareable Link
- Music picker: 3 MP3 tracks (Romantic, Cinematic, Eternity) with 12s preview snippets
- "Continue without music" option
- MP3s served from backend with Range support, loop continuously, fade in/out
- Dual-layer crossfade (2s), Ken Burns (9s, contain mode), 6s per slide
- **Share button**: Copies direct slideshow URL to clipboard
- **Direct slideshow route**: `/s/{token}/slideshow` — goes straight to music picker -> slideshow
- Auth-aware: redirects through ShareAccess if not authenticated, then back to slideshow
- Works with password-protected shares too

### Client Share Landing Page — Design A Classic
- Hero using Wedding Images cover photo as blurred background
- Elegant serif couple name, gold dividers, album cards with cover photo fills

### Dark Mode Toggle (Completed June 2026)
- Moon/Sun toggle in share view header (persists via localStorage)
- Theme object `t` with dark (#1A1A1A) and light (#FDFCF8) palettes
- Applied across: landing page, album detail, favourites, delete dialog, thank you modal, footer
- FileCard and ThankYouModal components receive theme as prop

### QR Code Generator (3 designs), Activity Log, Photographer Mode

## Key Files
- `/app/frontend/src/pages/ShareView.js` — Share views with dark mode toggle
- `/app/frontend/src/pages/Slideshow.js` — Music picker + slideshow + share button
- `/app/frontend/src/pages/SlideshowDirect.js` — Direct slideshow route handler
- `/app/frontend/src/pages/ShareAccess.js` — Auth with `?next=slideshow` redirect support
- `/app/frontend/src/App.js` — Route: `/s/:token/slideshow`
- `/app/backend/assets/slideshow_music/` — romantic.mp3, cinematic.mp3, eternity.mp3
- `/app/backend/server.py` — All API endpoints (>2600 lines)

## Backlog
- P1: Replace "Floral" QR design with decorated "Minimal" variation
- P1: Email notifications on album favourites submission
- P2: Client comments on favourited photos
- P3: Watermark previews
- P4: Modularize server.py into separate routers

## Deployment
```bash
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml down
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml build --no-cache
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml up -d
```
