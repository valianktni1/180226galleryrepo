# Wedding Photography Gallery - PRD

## Original Problem Statement
Self-hosted wedding photography client gallery management system with admin panel, sharing, downloads, print shop, slideshow, and QR codes.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn/UI + video.js
- **Backend:** FastAPI + Motor (async MongoDB) + Pillow + aiofiles
- **Video Serving:** nginx (optional, for multi-GB files) + Python fallback
- **Deployment:** Docker Compose on TrueNAS

## Implemented Features

### Core: Galleries, uploads, sharing, password protection, print shop, 2FA, guest uploads

### Video Streaming (Optimized for multi-GB files)
- **Faststart processing**: Auto-runs `ffmpeg -movflags +faststart` on video upload (moves moov atom to beginning for instant playback)
- **Reprocess endpoint**: `POST /api/admin/galleries/{id}/reprocess-videos` for existing videos
- **nginx direct serving** (optional): Zero-copy sendfile, signed URLs with secure_link module
- **Python fallback**: JWT-based playback tokens with zero DB calls during streaming
- **video.js player** with smart buffering, playback speed, fullscreen, native fallback
- Supports .mp4, .mov, .webm, .mkv, .avi, .mts

### Cinematic Slideshow with Music Picker + Shareable Link
- Music picker: 3 MP3 tracks (Romantic, Cinematic, Eternity)
- Ken Burns effect, crossfade, shareable direct link

### Client Share Landing Page — Design A Classic
- Hero with blurred cover photo, elegant serif typography, gold accents

### Dark Mode Toggle
- Persists via localStorage, applied across all share views

### QR Code Generator (3 designs), Activity Log, Photographer Mode

## Key API Endpoints
- `GET /api/share/{token}/video-token/{file_id}` — Get playback URL (nginx or Python)
- `GET /api/v/{vtoken}` — Direct Python streaming (zero DB calls)
- `POST /api/admin/galleries/{id}/reprocess-videos` — Fix existing videos for streaming

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
