# Wedding Photography Gallery Management System — PRD

## Original Problem Statement
Full-featured, self-hosted wedding photography client gallery management system with admin-managed galleries, chunked large file uploads/downloads, robust sharing, password protection, branded QR codes, cinematic slideshows, activity logging, and optimized video streaming.

## Architecture
- **Backend**: FastAPI, Motor (MongoDB), Pillow, FFmpeg (VAAPI Hardware encoding)
- **Frontend**: React, Tailwind CSS, video.js, Fetch API streaming
- **Infrastructure**: Docker Compose on TrueNAS, NGINX direct video serving, Dockge management
- **Hardware**: Minisforum UM780XTX (Radeon 780M iGPU) for GPU-accelerated transcoding

## Deployment
User deploys on TrueNAS via Dockge. Steps:
1. "Save to Github" in Emergent
2. `docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml down`
3. `docker compose build --no-cache backend`
4. `docker compose up -d`

## Completed Features
- [x] Admin-managed galleries with chunked uploads
- [x] Share links with password protection
- [x] Dark/Light mode toggle (Classic Timeless theme)
- [x] Cinematic Ken Burns slideshow
- [x] CSS-based watermarks on photo previews (clean downloads)
- [x] video.js integration for robust playback
- [x] Direct NGINX video serving (bypasses Python)
- [x] Background FFmpeg transcoding (5Mbps .web.mp4 streams)
- [x] "Optimise Videos for Web" admin button with progress polling
- [x] Visual download progress overlay for large files
- [x] Activity logging with exact file download tracking
- [x] Multi-design PDF QR code frame generator
- [x] .gitignore cleanup (removed 114MB test video bloat)
- [x] VAAPI hardware-accelerated transcoding (Radeon 780M) with CPU fallback (Jun 22, 2026)
- [x] Thumbnail generation before transcoding — instant UI feedback (Jun 22, 2026)

## In Progress
None

## Prioritized Backlog
- **P1**: Real-time transcoding progress bar in admin panel (per-file after upload + optimise button)
- **P1**: Replace "Floral" QR design with "Minimal" variation
- **P1**: Email notifications when client submits album favourites
- **P2**: Client comments on favourited photos
- **P4**: Modularize server.py (~2930 lines -> routes/galleries.py, routes/shares.py, routes/qr.py)

## Key Files
- `/app/backend/Dockerfile` — VAAPI drivers installed
- `/app/backend/server.py` — All APIs, FFmpeg logic, NGINX signed URLs
- `/app/frontend/src/pages/ShareView.js` — Watermarks, download progress, dark mode
- `/app/frontend/src/pages/AdminGalleryDetail.js` — Gallery management
- `/app/frontend/src/components/VideoPlayer.js` — video.js wrapper
- `/app/frontend/nginx.conf` — Proxy for /video/ to nginx-video container
- `/app/nginx/nginx.conf` — Direct file serving config

## Key API Endpoints
- `GET /api/share/{token}/video-token/{file_id}` — Signed streaming URLs
- `POST /api/admin/galleries/{gallery_id}/reprocess-videos` — Manual web-optimization trigger
- `GET /api/admin/galleries/reprocess-progress` — Transcoding status polling
- `/video/...` — NGINX proxy for streaming

## 3rd Party Integrations
- PayPal (Payments) — Direct link redirect (MOCKED)
- Google Authenticator (Auth) — pyotp local library

## Critical Notes
- Watermarks are CSS-only overlays in ShareView.js — never burn into images
- Video delivery: .web.mp4 for streaming, original for downloads
- UPLOAD_DIR env var = /data/userfiles in production (compose.yaml)
- NGINX video container mounts same volume read-only at /uploads
