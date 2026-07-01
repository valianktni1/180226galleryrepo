# StudioApp — Full SaaS White-Label Handoff

## What This Is
I have a fully working, self-hosted wedding photography client gallery management system. I want to turn it into a **multi-tenant white-label SaaS product** called **StudioApp** that I sell to other wedding photographers for a monthly fee. The domain will be **studioapp.uk**. This is a **NEW repo** (`studioapp`) — completely separate from my personal gallery (`180226galleryrepo`).

**IMPORTANT**: The user will provide exact mount paths for their TrueNAS drives. Ask them when you get to the Docker Compose / volume mapping stage.

---

## My Infrastructure
- **Server**: Minisforum UM780XTX (AMD Ryzen 7 7840HS, Radeon 780M iGPU, 64GB RAM)
- **OS**: TrueNAS SCALE (Linux-based, ZFS storage)
- **Container Management**: Dockge (Docker Compose GUI)
- **GPU**: AMD Radeon 780M — VAAPI hardware transcoding confirmed working with `mesa-va-drivers`
- **Domain**: studioapp.uk

---

## What Already Exists (The Source Codebase)
The original single-tenant app is fully production-ready and battle-tested. Here is EVERYTHING it does — the SaaS version must include ALL of this plus the multi-tenancy layer on top.

### Tech Stack
- **Backend**: Python FastAPI, Motor (async MongoDB), Pillow, FFmpeg (VAAPI GPU + CPU fallback), smtplib for email
- **Frontend**: React 19, Tailwind CSS 3, Shadcn/UI components, video.js 8, Framer Motion, Axios
- **Database**: MongoDB 7
- **Infrastructure**: Docker Compose (4 containers: backend, frontend, nginx-video, mongodb)
- **Video Delivery**: NGINX container serves `.web.mp4` transcoded files directly from disk (bypasses Python)

### Backend Dependencies (requirements.txt)
```
fastapi==0.110.1
uvicorn==0.25.0
motor==3.3.1
pymongo==4.5.0
python-dotenv==1.2.1
python-multipart==0.0.22
python-jose==3.5.0
PyJWT==2.8.0
bcrypt==4.1.3
passlib==1.7.4
aiofiles==25.1.0
pillow==12.1.0
qrcode[pil]==8.2
pydantic==2.12.5
slowapi==0.1.9
pyotp==2.9.0
watchfiles==1.1.1
```

### Frontend Dependencies (key ones)
React 19, react-router-dom 7, axios, framer-motion 12, video.js 8, lucide-react, Shadcn/UI (Radix primitives), Tailwind CSS 3, sonner (toasts), recharts, react-day-picker, zod

### Complete Feature List (ALL must be preserved)
1. **Admin Dashboard** — Create/manage galleries, gallery cards with thumbnails, storage stats, live visitors panel
2. **Gallery Management** — Chunked large file uploads (40GB support), subfolders (Wedding Images, Video, SelfieBooth, Album Favourites, Guest Uploads), bulk operations
3. **Share Links** — Password-protected shareable gallery links, configurable access levels (view/download/full), expiry dates, custom slugs
4. **QR Code PDFs** — Multi-design PDF generator (3 designs: Minimal, Classic, Botanical) using Pillow
5. **Video Streaming** — Background FFmpeg transcoding creates 5Mbps 1080p `.web.mp4` web versions. NGINX serves them directly. Real-time transcoding progress bars per video card.
6. **VAAPI Hardware Transcoding** — GPU-accelerated H.264 encoding via AMD Radeon 780M with automatic CPU fallback
7. **Separate Thread Pools** — `thumbnail_executor` (8 workers) for fast thumbnail/preview generation, `transcode_executor` (2 workers) for slow FFmpeg jobs. DO NOT MERGE THESE.
8. **Dark/Light Mode** — "Classic Timeless" theme toggle on share views
9. **Cinematic Slideshow** — Ken Burns effect with custom audio tracks, shareable slideshow links
10. **CSS Watermarks** — Logo overlay on photo previews (72% opacity), downloads are clean/unwatermarked
11. **Progressive Image Loading** — Blur-to-sharp in lightbox, sharp thumbnails in grid
12. **Download Progress** — Visual percentage overlay for large file downloads
13. **Activity Logging** — Tracks exact files downloaded, views, favourites with timestamps. Search by name. Auto-archive after 6 months. Archive tab.
14. **Guest Uploads** — Clients upload their own photos/videos, with size limits and optional compression
15. **Album Favourites** — Clients favourite photos, admin copies selections to Album Favourites folder
16. **2FA Authentication** — TOTP-based (Google Authenticator / pyotp) for admin login
17. **Automatic Thumbnail Generation** — Background generation for photos and videos, 5s auto-polling for new thumbs
18. **Bulk Operations** — Select mode for bulk delete, bulk copy to favourites, download all as ZIP
19. **SMTP Email System** — Configurable SMTP settings (Hostinger compatible with `formataddr`), branded HTML email template
20. **Notify Couple** — One-click "Gallery Ready" email with gallery link, password, instructions
21. **Broadcast Email** — Mass email to all couples with gallery emails, from dashboard
22. **Email Templates** — Create reusable templates in Settings with `{couple_name}` and `{gallery_link}` tokens. "Send Email" on each gallery page picks a template, auto-fills, sends.
23. **Automated Expiry Reminders** — Daily background task sends email 7 days before main share link expires
24. **Email Log** — "Emails" tab on Activity page shows all sent emails (broadcast, gallery-ready, expiry, template) with type, subject, recipient, date
25. **Live Visitors Panel** — 30s heartbeats from share views, admin dashboard shows who's online, what gallery, what action (browsing/viewing photo/watching video), device type, duration
26. **Backup System** — One-click backup button, backup-aware deletion (checkbox "Also delete from backup?")
27. **Awards Badge in Emails** — Awards image served from public endpoint, displayed in all branded emails when `site_url` is set in SMTP settings
28. **Print Sizes & Orders** — Configurable print sizes, order tracking (this exists but is basic)

### Architecture
```
project/
├── backend/
│   ├── Dockerfile (Python 3.11-slim + FFmpeg + VAAPI drivers)
│   ├── requirements.txt
│   ├── server.py (~3800 lines — ALL routes in one file)
│   └── assets/ (fonts, QR frame backgrounds, awards-badges.png)
├── frontend/
│   ├── Dockerfile (Node 20 build + NGINX serve)
│   ├── nginx.conf (proxies /api/ to backend, /video/ to nginx-video)
│   ├── package.json
│   └── src/
│       ├── components/
│       │   ├── VideoPlayer.js (video.js wrapper)
│       │   ├── ProgressiveImage.js
│       │   └── ui/ (Shadcn components)
│       ├── pages/
│       │   ├── AdminDashboard.js (galleries, live visitors, broadcast email)
│       │   ├── AdminGalleryDetail.js (file management, transcode progress, notify couple, send email)
│       │   ├── AdminLogin.js
│       │   ├── AdminSettings.js (password, 2FA, SMTP, email templates, video compression, print sizes)
│       │   ├── AdminActivity.js (activity log, archive, email log)
│       │   └── ShareView.js (client-facing: progressive images, watermarks, dark mode, slideshow, heartbeats, download all)
│       └── lib/
│           └── api.js (axios API client)
├── nginx/ (dedicated video streaming container)
│   ├── Dockerfile (nginx:alpine)
│   ├── entrypoint.sh (replaces __NGINX_VIDEO_SECRET__ at runtime)
│   └── nginx.conf (secure_link token verification, direct file serving from /uploads/)
└── compose.yaml
```

### Docker Compose Structure (Original)
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
      - DB_NAME=gallery
      - CORS_ORIGINS=*
      - JWT_SECRET=<generated>
      - UPLOAD_DIR=/data/userfiles
      - NGINX_VIDEO_URL=enabled
      - NGINX_VIDEO_SECRET=<generated>
    volumes:
      - /path/to/uploads:/data/userfiles
      - /path/to/backups:/backup
  nginx-video:
    build: ./nginx
    environment:
      - NGINX_VIDEO_SECRET=<matching secret>
    volumes:
      - /path/to/uploads:/uploads:ro
  frontend:
    build: ./frontend
    ports:
      - "3037:80"
    build:
      args:
        REACT_APP_BACKEND_URL: ""  # empty for same-origin
```

### Frontend NGINX Config (Critical)
```nginx
server {
    listen 80;
    location / { try_files $uri $uri/ /index.html; }
    location /api/ {
        proxy_pass http://backend:8001;
        client_max_body_size 40G;
        proxy_request_buffering off;
        proxy_buffering off;
        proxy_send_timeout 3600;
        proxy_read_timeout 3600;
    }
    location /video/ {
        proxy_pass http://nginx-video:8090;
        proxy_set_header Range $http_range;
        proxy_buffering off;
    }
}
```

### NGINX Video Container Config (Critical — secure_link)
```nginx
server {
    listen 8090;
    set $video_secret "__NGINX_VIDEO_SECRET__";  # replaced at runtime by entrypoint.sh
    location /video/ {
        secure_link $arg_md5,$arg_expires;
        secure_link_md5 "$video_secret$uri$arg_expires";
        if ($secure_link = "") { return 403; }
        if ($secure_link = "0") { return 410; }
        alias /uploads/;
        sendfile on; tcp_nopush on; tcp_nodelay on;
        add_header Accept-Ranges bytes always;
    }
}
```

### Database Collections (MongoDB)
- `admins` — Admin users (username, hashed password, TOTP secret)
- `galleries` — Gallery metadata (id, folder_name, subfolders, file_counts, covers, client_email, notification_sent_at)
- `files` — File records (id, gallery_id, subfolder, filename, file_type, file_size, has_thumb, has_preview)
- `shares` — Share links (id, gallery_id, token, subfolder, password_hash, access_level, is_active, expires_at, label, guest_upload_mode, custom_slug, expiry_reminder_sent)
- `favourites` — Client favourited photos
- `activity_log` — View/download tracking
- `activity_log_archive` — Auto-archived logs (>6 months)
- `email_log` — All sent emails (type, subject, gallery_name, recipient, timestamp, template_name)
- `email_templates` — Reusable email templates (name, subject, body with {couple_name}/{gallery_link} tokens)
- `templates` — Gallery templates (name + subfolder presets)
- `settings` — Key-value store (smtp config with site_url, compression settings)
- `print_sizes` — Print size options
- `print_orders` — Print orders

### Key API Endpoints
```
# Auth
POST /api/admin/login — Login (returns JWT)
POST /api/admin/setup — First-run admin creation
GET  /api/admin/check-setup — Check if setup needed

# Galleries
POST   /api/admin/galleries — Create gallery
GET    /api/admin/galleries — List all galleries
DELETE /api/admin/galleries/{id}?delete_backup=true|false — Delete gallery
POST   /api/admin/galleries/{id}/upload — Chunked file upload
DELETE /api/admin/galleries/{id}/files/{file_id}?delete_backup=true|false — Delete file

# Shares
POST   /api/admin/galleries/{id}/shares — Create share link
DELETE /api/admin/shares/{id} — Delete share
PUT    /api/admin/shares/{id}/toggle — Enable/disable share

# Email
GET    /api/admin/settings/smtp — Get SMTP config
POST   /api/admin/settings/smtp — Save SMTP config (includes site_url for awards badge)
POST   /api/admin/settings/smtp/test — Send test email
POST   /api/admin/galleries/{id}/notify — Send "Gallery Ready" email
POST   /api/admin/broadcast-email — Mass email to all couples
GET    /api/admin/broadcast-preview — Preview broadcast recipients
GET    /api/admin/email-log — Get sent email log
CRUD   /api/admin/email-templates — Email template management
POST   /api/admin/galleries/{id}/send-template-email — Send template to couple

# Monitoring
GET    /api/admin/live-visitors — Live viewer sessions
GET    /api/admin/activity — Activity log with search
POST   /api/admin/activity/archive — Manual archive trigger

# Public (no auth)
GET    /api/share/{token} — Get share info
GET    /api/share/{token}/files — Get files for share
POST   /api/share/{token}/heartbeat — Register viewer heartbeat
GET    /api/public/email-assets/{filename} — Serve email images (awards badge)

# Video
GET    /api/share/{token}/video-token/{file_id} — Generate signed URL for NGINX streaming
GET    /api/admin/transcode-status — Real-time FFmpeg progress

# Backup
POST   /api/admin/backup — Run backup
```

### SMTP Critical Note
The user uses Hostinger. The `From` header MUST be formatted as `formataddr((sender_name, smtp_email))` or Hostinger returns 553 Sender Address Rejected.

### Thread Pools (DO NOT MERGE)
- `thumbnail_executor` = ThreadPoolExecutor(max_workers=8) — fast photo/video thumbnail jobs
- `transcode_executor` = ThreadPoolExecutor(max_workers=2) — slow FFmpeg video transcoding
- They are separate because long transcode jobs (minutes) would block instant thumbnail generation (seconds) if merged.

### Video Flow
1. Upload → saved to disk → thumbnail generated immediately → DB updated
2. `transcode_executor` creates `.web.mp4` (5Mbps 1080p H.264) with real-time progress via Popen
3. Frontend polls transcode-status every 2s → progress bar on video card
4. Playback: frontend requests signed URL → redirected to NGINX container → serves .web.mp4 directly
5. Download: serves original full-quality file

---

## What Needs to Be Built (The SaaS Layer)

### 1. Super Admin (Platform Owner — Mark)
- **Super Admin account** — Created during platform first-run setup
- **Super Admin Dashboard** at `/super-admin/`:
  - List all tenants (photographers) with: business name, email, plan, storage used/limit, subscription status (active/suspended/cancelled), created date
  - **Create Tenant** — manually add a photographer
  - **Suspend/Unsuspend** — toggle access (suspended users see "Account suspended, contact support")
  - **Delete Tenant** — removes everything (galleries, DB data, files) with confirmation
  - **Storage overview** — total usage across all tenants vs server capacity
- Super admin can impersonate any tenant (login as them for support)
- Super admin sees revenue dashboard (MRR, active subs, churn)

### 2. Multi-Tenancy
- **Single deployment**, single MongoDB, shared containers — NOT separate stacks per tenant
- Every database collection gets a `tenant_id` field
- Every API endpoint filters by the logged-in tenant's ID
- File storage: `/data/userfiles/{tenant_id}/` — each tenant's galleries in their own folder
- Backup storage: `/backup/{tenant_id}/`
- **Complete isolation** — Tenant A cannot see Tenant B's anything

### 3. Tenant Onboarding (First-Run Setup Wizard)
When a new tenant logs in for the first time, they see a setup wizard:
1. **Business Details** — Business name, contact email, phone, website
2. **Logo Upload** — Used for watermarks, share page headers, login page
3. **Branding** — Primary accent colour (default #D4AF37 gold), secondary colour
4. **SMTP Setup** — Their own email server details (optional, can skip and set later)

All "Weddings By Mark" hardcoded references become `{tenant.business_name}`.

### 4. Subscription Plans & Storage Limits
Three tiers:
- **Starter** — 250GB storage
- **Pro** — 500GB storage
- **Studio** — 1TB storage

Pricing TBD by Mark (he sets it in super admin).

- **Storage enforcement**: Upload endpoint checks `current_usage + file_size <= plan_limit` before accepting
- **Storage dashboard**: Each tenant sees a usage bar (e.g. "187GB / 250GB")
- **Stripe integration** for monthly billing, auto-suspend on failed payment
- Super admin can manually override/extend limits

### 5. Branding
- **Every page footer** on both admin and client galleries: `Site Designed & Hosted by StudioApp`
- All emails: `Powered by StudioApp` in footer
- Tenant's own business name, logo, and colours throughout THEIR galleries
- Awards badge in emails is PER-TENANT (they upload their own or leave blank)

### 6. Authentication Hierarchy
```
Super Admin (Mark) → can see/manage all tenants
  └── Tenant Admin (Photographer) → can only see their own galleries/settings
       └── Share Links (Clients) → password-protected gallery access
```

### 7. Docker Compose for Production (studioapp.uk)
Single compose with:
- `mongodb` — One shared MongoDB
- `backend` — Single FastAPI backend (multi-tenant aware)
- `frontend` — Single React frontend
- `nginx-video` — Single NGINX video server (serves files from tenant subdirectories)

Volumes — **ASK THE USER for exact TrueNAS mount paths**. They will provide:
- The path for upload storage (their HDD pool)
- The path for backup storage
- The path for MongoDB data (their SSD)

```yaml
# TEMPLATE — user provides exact /mnt/ paths
services:
  mongodb:
    image: mongo:7
    volumes:
      - <USER_PROVIDES_SSD_PATH>/studioapp/mongodb:/data/db
  backend:
    build: ./backend
    devices:
      - /dev/dri/renderD128:/dev/dri/renderD128
    environment:
      - MONGO_URL=mongodb://mongodb:27017
      - DB_NAME=studioapp
      - JWT_SECRET=<generate>
      - SUPER_ADMIN_SECRET=<generate>
      - UPLOAD_DIR=/data/userfiles
      - BACKUP_DIR=/backup
      - NGINX_VIDEO_URL=enabled
      - NGINX_VIDEO_SECRET=<generate>
      - STRIPE_SECRET_KEY=<from stripe>
      - STRIPE_WEBHOOK_SECRET=<from stripe>
    volumes:
      - <USER_PROVIDES_HDD_PATH>/studioapp/uploads:/data/userfiles
      - <USER_PROVIDES_HDD_PATH>/studioapp/backups:/backup
  nginx-video:
    build: ./nginx
    environment:
      - NGINX_VIDEO_SECRET=<matching>
    volumes:
      - <USER_PROVIDES_HDD_PATH>/studioapp/uploads:/uploads:ro
  frontend:
    build: ./frontend
    ports:
      - "3038:80"
    build:
      args:
        REACT_APP_BACKEND_URL: ""
```

### 8. Deployment
- Hosted on TrueNAS via Dockge at studioapp.uk
- Reverse proxy (Traefik or NGINX Proxy Manager) routes studioapp.uk to port 3038
- SSL via Let's Encrypt
- User manages via Dockge GUI

---

## Priority Build Order
1. **Fork codebase** — Copy all features, strip "Weddings By Mark", replace with configurable tenant branding
2. **Multi-tenancy layer** — Add `tenant_id` to all collections and queries, tenant-aware auth middleware
3. **Super Admin** — Dashboard, tenant CRUD, suspend/unsuspend, impersonation
4. **Tenant onboarding wizard** — Business name, logo, colours, SMTP
5. **Storage quotas** — Plan limits (250GB/500GB/1TB), usage tracking, enforcement on upload
6. **Stripe billing** — Monthly subscriptions, auto-suspend on failed payment, webhook handling
7. **StudioApp branding** — Footer on all pages and emails: "Site Designed & Hosted by StudioApp"
8. **Modularize server.py** — Since we're building from scratch, break the ~3800 line server.py into proper route modules (routes/galleries.py, routes/shares.py, routes/email.py, routes/admin.py, routes/super_admin.py)

---

## Critical Implementation Notes
- The `From` email header MUST use `formataddr((sender_name, smtp_email))` for Hostinger compatibility
- Thread pools MUST stay separate: `thumbnail_executor` (8 workers) + `transcode_executor` (2 workers)
- NGINX video container uses `secure_link` module with shared secret — the secret is injected via `entrypoint.sh` at container startup
- Frontend uses `REACT_APP_BACKEND_URL` env var (empty string for same-origin production)
- All video streaming goes through the NGINX video container, NOT through Python
- The GPU device `/dev/dri/renderD128` must be passed through to the backend container for VAAPI transcoding
- Expiry reminder background task runs as an `asyncio` loop, checking daily

---

## Files Available in Original Repo
The entire original codebase is in GitHub repo `180226galleryrepo`. The new agent should use this as reference but build `studioapp` as its own clean repo with proper modular architecture from the start.
