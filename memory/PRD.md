# Wedding Photography Gallery - PRD

## Original Problem Statement
Self-hosted wedding photography client gallery management system with admin panel, sharing, downloads, print shop, slideshow, and QR codes.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn/UI + video.js
- **Backend:** FastAPI + Motor (async MongoDB) + Pillow + aiofiles
- **Deployment:** Docker Compose on TrueNAS

## Implemented Features

### Core: Galleries, uploads, sharing, password protection, print shop, 2FA, guest uploads

### Video Streaming (Optimized for multi-GB files)
- **Video playback token system**: Auth + DB lookup done ONCE on play, generates 2hr signed JWT with file path embedded
- **Direct streaming endpoint** (`/api/v/{token}`): Zero DB calls during playback — just JWT check + disk read
- **1MB chunks** for direct stream, async I/O via aiofiles
- **video.js** professional player with smart buffering, playback speed, fullscreen. Auto-fallback to native HTML5 on error
- Supports .mp4, .mov, .webm, .mkv, .avi, .mts
- Thumbnails on upload (ffmpeg), inline playback with Range streaming
- Cache-Control headers for CDN caching

### Cinematic Slideshow with Music Picker + Shareable Link
- Music picker: 3 MP3 tracks (Romantic, Cinematic, Eternity) with 12s preview snippets
- "Continue without music" option
- MP3s served from backend with Range support, loop continuously, fade in/out
- Dual-layer crossfade (2s), Ken Burns (9s, contain mode), 6s per slide
- **Share button**: Copies direct slideshow URL to clipboard
- **Direct slideshow route**: `/s/{token}/slideshow` — goes straight to music picker -> slideshow
- Auth-aware: redirects through ShareAccess if not authenticated, then back to slideshow

### Client Share Landing Page — Design A Classic
- Hero using Wedding Images cover photo as blurred background
- Elegant serif couple name, gold dividers, album cards with cover photo fills

### Dark Mode Toggle
- Moon/Sun toggle in share view header (persists via localStorage)
- Theme object `t` with dark (#1A1A1A) and light (#FDFCF8) palettes
- Applied across all share views: landing, album detail, favourites, delete dialog, thank you modal, footer

### QR Code Generator (3 designs), Activity Log, Photographer Mode

## Key Files
- `/app/frontend/src/pages/ShareView.js` — Share views with dark mode + video.js lightbox
- `/app/frontend/src/components/VideoPlayer.js` — video.js player with token resolution + native fallback
- `/app/frontend/src/lib/api.js` — getVideoPlaybackUrl() for token-based streaming
- `/app/backend/server.py` — `/api/share/{token}/video-token/{file_id}` + `/api/v/{vtoken}`

## Key API Endpoints
- `GET /api/share/{token}/video-token/{file_id}` — Generate 2hr playback token (one auth + DB call)
- `GET /api/v/{vtoken}` — Direct video streaming (zero DB calls, JWT-only auth)
- `GET /api/share/{token}/stream/{file_id}` — Legacy streaming endpoint (kept as fallback)

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
