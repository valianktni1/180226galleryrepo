# White-Label Wedding Gallery App — New Agent Handoff Brief

## What This Project Is
I have a fully working, self-hosted wedding photography client gallery management system. I want to take this app and turn it into a **white-label resale product** that I can sell to other photographers and videographers. This new conversation is for building the **resale/white-label version** as a separate codebase — do NOT modify my personal version.

## The Existing App (Reference — Do NOT modify)
The original app lives in a separate Emergent conversation/repo. Here's everything the new agent needs to know about how it works:

### Tech Stack
- **Backend**: Python FastAPI, Motor (async MongoDB), Pillow (image processing), FFmpeg (video transcoding with VAAPI GPU acceleration + CPU fallback)
- **Frontend**: React, Tailwind CSS, Shadcn/UI components, video.js (video player), Framer Motion
- **Database**: MongoDB 7
- **Infrastructure**: Docker Compose (3 containers: backend, frontend, nginx-video), self-hosted on TrueNAS via Dockge
- **Video Delivery**: NGINX container serves `.web.mp4` transcoded files directly from disk (bypasses Python). Frontend proxies `/video/` requests to this container.

### Complete Feature List (All Working)
1. **Admin Dashboard** — Create/manage galleries, upload photos & videos (chunked large file support), organize into subfolders (Wedding Images, Video, SelfieBooth, Album Favourites, Guest Uploads)
2. **Share Links** — Password-protected shareable gallery links with configurable access levels (view/download/full), expiry dates, custom slugs
3. **QR Code PDFs** — Multi-design PDF generator with QR codes for share links (3 designs: Minimal, Classic, Botanical)
4. **Video Streaming** — Background FFmpeg transcoding creates 5Mbps 1080p `.web.mp4` versions for smooth browser playback. Originals preserved for download. Real-time transcoding progress bar on each video card in admin panel.
5. **VAAPI Hardware Transcoding** — GPU-accelerated encoding using AMD Radeon 780M iGPU with automatic CPU fallback
6. **Dark/Light Mode** — "Classic Timeless" theme with toggle on share views
7. **Cinematic Slideshow** — Ken Burns effect slideshow with custom audio track support, shareable slideshow links
8. **CSS Watermarks** — Logo overlay on photo previews (72% opacity), downloads are clean/unwatermarked
9. **Download Progress** — Visual percentage overlay for large file downloads using streamed Blob fetching
10. **Activity Logging** — Tracks exact files downloaded, views, with timestamps
11. **Guest Uploads** — Clients can upload their own photos/videos to designated folders, with size limits and optional compression
12. **Album Favourites** — Clients can favourite photos, admin can copy selections to an Album Favourites folder
13. **2FA Authentication** — TOTP-based (Google Authenticator) two-factor auth for admin login
14. **Thumbnail Generation** — Automatic background thumbnail/preview generation for photos and videos. Thumbnails generate before transcoding starts so they appear instantly in the UI.
15. **Bulk Operations** — Select mode for bulk delete, bulk copy to favourites, download all as ZIP

### Architecture
```
project/
├── backend/
│   ├── Dockerfile (Python 3.11-slim + FFmpeg + VAAPI drivers)
│   ├── requirements.txt
│   ├── server.py (~3000 lines — ALL routes, models, FFmpeg logic in one file)
│   └── assets/ (fonts, QR frame backgrounds)
├── frontend/
│   ├── Dockerfile (Node build + NGINX serve)
│   ├── nginx.conf (proxies /api/ to backend, /video/ to nginx-video)
│   └── src/
│       ├── components/
│       │   ├── VideoPlayer.js (video.js wrapper)
│       │   └── ui/ (Shadcn components)
│       ├── pages/
│       │   ├── AdminGalleryDetail.js (gallery management + transcode progress)
│       │   ├── AdminDashboard.js
│       │   ├── AdminLogin.js
│       │   └── ShareView.js (client-facing view with watermarks, dark mode, slideshow)
│       └── lib/
│           └── api.js (axios API client)
├── nginx/ (dedicated video streaming container)
│   ├── Dockerfile
│   └── nginx.conf (secure_link token verification, direct file serving)
└── compose.yaml
```

### Key API Endpoints
- `POST /api/admin/login` — Admin authentication (returns JWT)
- `POST /api/admin/galleries` — Create gallery
- `POST /api/admin/galleries/{id}/upload` — Chunked file upload
- `GET /api/admin/galleries/{id}/transcode-status` — Per-file transcoding progress
- `POST /api/admin/galleries/{id}/reprocess-videos` — Bulk re-transcode
- `GET /api/share/{token}` — Get shared gallery data
- `GET /api/share/{token}/files` — Get files for shared gallery
- `GET /api/share/{token}/video-token/{file_id}` — Generate signed URL for video streaming
- `POST /api/share/{token}/track-view` — Log activity
- `/video/...` — NGINX proxy to nginx-video container (bypasses Python)

### Database Collections (MongoDB)
- `admin` — Single admin user document (username, hashed password, TOTP secret, display_name)
- `galleries` — Gallery metadata (id, name, folder_name, subfolders, file_counts, covers, created_at)
- `files` — File records (id, gallery_id, subfolder, filename, file_type, file_size, has_thumb, has_preview, uploaded_by, uploaded_at)
- `shares` — Share links (id, gallery_id, token, subfolder, password_hash, access_level, is_active, expires_at, label, guest_upload_mode)
- `favourites` — Client favourited photos (file_id, gallery_id, share_id)
- `activity_log` — View/download tracking (gallery_id, share_id, action, filename, timestamp, ip)
- `templates` — Gallery templates (name, subfolders list)

### Docker Compose Structure
```yaml
services:
  mongodb:
    image: mongo:7
    volumes:
      - ./mongodb:/data/db
  backend:
    build: ./backend
    devices:
      - /dev/dri/renderD128:/dev/dri/renderD128  # GPU passthrough for VAAPI
    environment:
      - MONGO_URL=mongodb://mongodb:27017
      - DB_NAME=weddings_by_mark
      - CORS_ORIGINS=*
      - JWT_SECRET=<generated>
      - UPLOAD_DIR=/data/userfiles
      - NGINX_VIDEO_URL=enabled
      - NGINX_VIDEO_SECRET=<generated>
    volumes:
      - /path/to/customer/uploads:/data/userfiles
      - /path/to/backups:/backup
  nginx-video:
    build: ./nginx
    environment:
      - NGINX_VIDEO_SECRET=<matching secret>
    volumes:
      - /path/to/customer/uploads:/uploads:ro
  frontend:
    build: ./frontend
    ports:
      - "3037:80"
```

### Thread Pool Architecture
- `thumbnail_executor` (4 workers) — Fast tasks: photo/video thumbnail generation
- `transcode_executor` (2 workers) — Slow tasks: FFmpeg video transcoding only
- This separation ensures video transcoding never blocks image thumbnail generation

### Video Delivery Flow
1. Upload → file saved to disk → thumbnail generated immediately → DB updated
2. `transcode_executor` picks up the video → FFmpeg creates `.web.mp4` (5Mbps 1080p) with real-time progress tracking
3. Frontend polls `/api/.../transcode-status` every 2 seconds → shows progress bar on video card
4. Playback: frontend requests signed URL via `/api/share/{token}/video-token/{file_id}` → redirected to NGINX container which serves the `.web.mp4` directly from disk
5. Download: fetches the original full-quality file via `/api/share/{token}/download/{file_id}`

---

## What Needs to Change for the White-Label Version

### 1. Remove My Personal Branding
- Remove all "Weddings By Mark" hardcoded references
- Replace with configurable business name from admin settings
- Keep a small footer credit: "App designed & hosted by Weddings By Mark" (this is MY branding as the platform provider)

### 2. Admin Settings Page (NEW)
- Business name (used throughout the app)
- Logo upload (used for watermarks, share view headers, login page)
- Accent colour picker (currently hardcoded gold #D4AF37)
- Contact email/website (shown on share views)
- First-run setup wizard already exists for username/password — extend it to include branding

### 3. Multi-Instance Deployment Model
- Each customer gets their OWN Docker Compose stack (separate containers, separate MongoDB, separate uploads directory)
- NOT multi-tenant (no shared database)
- My TrueNAS storage layout:
  - **Apps SSD**: Docker containers + MongoDB per customer (`/mnt/apps/customer-galleries/<customer-name>/`)
  - **2x 8TB mirrored HDDs**: Customer upload data (`/mnt/customer-data/<customer-name>/userfiles/`)
- I need a simple way to spin up new customer instances (script or template)

### 4. Keep Everything Else
- All existing features stay exactly as they are
- 2FA, share links, QR codes, video streaming, VAAPI transcoding, dark mode, slideshows — all keep working
- The codebase is a fork/copy that I can develop independently from my personal version

---

## My Infrastructure
- **Server**: Minisforum UM780XTX (AMD Ryzen 7 7840HS, Radeon 780M iGPU, 64GB RAM)
- **OS**: TrueNAS SCALE (Linux-based, ZFS storage)
- **Container Management**: Dockge (Docker Compose GUI)
- **Current Storage**: Apps SSD for containers, planning 2x 8TB mirrored vdev for customer data
- **GPU**: AMD Radeon 780M — VAAPI hardware transcoding confirmed working with `mesa-va-drivers`

## Priority Order
1. Fork the codebase and make branding configurable (admin settings page with logo upload, business name, accent colour)
2. Create a deployment script/template for spinning up new customer instances
3. Test the full flow: new instance → admin setup → branding configured → gallery created → shared with client

## Important Notes
- The backend `server.py` is ~3000 lines in a single file. If you're going to refactor, now is the time to modularize into routes/ before adding features.
- The app uses `pyotp` for TOTP 2FA — this is local, no third-party auth service.
- Passwords are hashed with `bcrypt`.
- JWTs are used for admin sessions and share link verification.
- The frontend uses `process.env.REACT_APP_BACKEND_URL` for API calls (set at build time, empty string for same-origin).
