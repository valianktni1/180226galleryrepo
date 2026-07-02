# StudioApp SaaS — Complete Build Handoff

## WHAT TO BUILD
Turn an existing fully-working single-tenant wedding photography gallery system into a **multi-tenant SaaS platform** called **StudioApp**. The domain is **studioapp.uk**. Every feature from the original app must be preserved and made tenant-aware. All "Weddings By Mark" branding must be completely removed and replaced with per-tenant configurable branding.

**IMPORTANT**: Respond in English only throughout the entire build.

---

## SUPER ADMIN CREDENTIALS
- **Username**: `superadmin`
- **Password**: `Stu!d10App_2026xQ`
- This is the platform owner (Mark). Create this account during first-run setup.
- Super admin sits ABOVE all tenant photographers. Separate auth tier.

---

## HOSTING & MOUNT PATHS (TrueNAS SCALE)

**Server**: Minisforum UM780XTX (AMD Ryzen 7 7840HS, Radeon 780M iGPU, 64GB RAM) running TrueNAS SCALE.
**Container Management**: Dockge (Docker Compose GUI)
**GPU**: AMD Radeon 780M — VAAPI hardware transcoding. Device path: `/dev/dri/renderD128`

### Mount Paths (EXACT — do not change):
```
Program Data:    /mnt/apps/multiple_photographers_app/studioapp_data
User Data:       /mnt/photographers_data/studioapp_userdata
```

### Directory Structure Under These Mounts:
```
/mnt/apps/multiple_photographers_app/studioapp_data/
├── mongodb/           # MongoDB data
├── compose.yaml       # Docker Compose file
├── backend/           # Backend source
├── frontend/          # Frontend source
└── nginx/             # NGINX video server

/mnt/photographers_data/studioapp_userdata/
├── uploads/           # All tenant files: uploads/{tenant_id}/gallery_folder/subfolder/files
└── backups/           # All tenant backups: backups/{tenant_id}/gallery_folder/
```

### Docker Compose Template:
```yaml
services:
  mongodb:
    image: mongo:7
    restart: unless-stopped
    volumes:
      - /mnt/apps/multiple_photographers_app/studioapp_data/mongodb:/data/db

  backend:
    build: ./backend
    restart: unless-stopped
    devices:
      - /dev/dri/renderD128:/dev/dri/renderD128
    environment:
      - MONGO_URL=mongodb://mongodb:27017
      - DB_NAME=studioapp
      - JWT_SECRET=<generate-random-secret>
      - SUPER_ADMIN_SECRET=<generate-separate-secret>
      - UPLOAD_DIR=/data/userfiles
      - BACKUP_DIR=/backup
      - NGINX_VIDEO_URL=enabled
      - NGINX_VIDEO_SECRET=<generate-matching-secret>
      - STRIPE_SECRET_KEY=<from-stripe>
      - STRIPE_WEBHOOK_SECRET=<from-stripe>
    volumes:
      - /mnt/photographers_data/studioapp_userdata/uploads:/data/userfiles
      - /mnt/photographers_data/studioapp_userdata/backups:/backup

  nginx-video:
    build: ./nginx
    restart: unless-stopped
    environment:
      - NGINX_VIDEO_SECRET=<must-match-backend>
    volumes:
      - /mnt/photographers_data/studioapp_userdata/uploads:/uploads:ro

  frontend:
    build:
      context: ./frontend
      args:
        REACT_APP_BACKEND_URL: ""
    restart: unless-stopped
    ports:
      - "3038:80"
```

### Deployment Commands (via Dockge):
```bash
docker compose -f /mnt/apps/multiple_photographers_app/studioapp_data/compose.yaml down
docker compose -f /mnt/apps/multiple_photographers_app/studioapp_data/compose.yaml build --no-cache backend frontend
docker compose -f /mnt/apps/multiple_photographers_app/studioapp_data/compose.yaml up -d
```

---

## TECH STACK (Preserve Exactly)

### Backend
- **Python 3.11** + **FastAPI**
- **Motor** (async MongoDB driver)
- **Pillow** (image processing, QR PDF generation)
- **FFmpeg** with VAAPI GPU encoding (AMD Radeon 780M) + automatic CPU fallback
- **smtplib** + email.mime for SMTP
- **PyJWT** + **bcrypt** for auth
- **pyotp** for TOTP 2FA
- **slowapi** for rate limiting

### Frontend
- **React 19** + **React Router 7**
- **Tailwind CSS 3** + **Shadcn/UI** (Radix primitives)
- **video.js 8** for video playback
- **Framer Motion 12** for animations
- **Axios** for API calls
- **Lucide React** for icons
- **sonner** for toasts
- **Cormorant Garamond** (headings) + **Manrope** (body) fonts

### Infrastructure
- **MongoDB 7** — single shared instance, multi-tenant via `tenant_id`
- **NGINX** — dedicated container for direct video file serving with `secure_link` token verification
- **Docker Compose** — 4 containers (mongodb, backend, frontend, nginx-video)

### Dependencies (requirements.txt):
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

---

## COMPLETE FEATURE LIST (ALL MUST BE PRESERVED)

Every single feature below exists and works in the original app. The SaaS version must include ALL of them, made tenant-aware.

### 1. Authentication & Security
- Admin login with JWT tokens
- First-run setup wizard (creates admin account)
- Password change
- **TOTP 2FA** via Google Authenticator (pyotp) — setup, enable, disable, verify
- Rate limiting on login (slowapi)

### 2. Gallery Management
- Create galleries with folder names (e.g. "Eva & Ella 27.06.26")
- Gallery templates (preset subfolder structures)
- Default subfolders: Wedding Images, Video, SelfieBooth, Album Favourites, Guest Uploads
- **Chunked large file uploads** (supports 40GB+ files)
- Bulk file operations (select mode, bulk delete, bulk copy)
- Set subfolder cover images
- Delete subfolders
- Gallery-level client email field (for notifications)
- File types supported — Photos: JPEG, PNG, GIF, TIFF, WebP, BMP. Videos: MP4, MOV, AVI, MKV, WebM, MTS

### 3. Thumbnail & Preview Generation
- **Background thumbnail generation** via `thumbnail_executor` (ThreadPoolExecutor, 8 workers)
- Photo thumbnails (400px) + larger previews (1600px)
- Video thumbnails extracted via FFmpeg
- 5-second auto-polling on gallery detail page for newly generated thumbs
- Cache stored at `{UPLOAD_DIR}/.cache/thumbs/{gallery_id}/`

### 4. Video Transcoding
- **Background FFmpeg transcoding** via `transcode_executor` (ThreadPoolExecutor, 2 workers)
- Creates `.web.mp4` web-optimised versions (5Mbps 1080p H.264)
- **VAAPI GPU acceleration** via AMD Radeon 780M with automatic CPU fallback
- **Real-time transcoding progress** — FFmpeg Popen with live progress parsing
- Frontend polls transcode-status every 2s → progress bar on each video card
- `ensure_video_faststart` — ensures moov atom is at start for instant playback

**CRITICAL: DO NOT MERGE the two thread pools. `thumbnail_executor` (8 workers) and `transcode_executor` (2 workers) are intentionally separate because long transcode jobs (minutes) would block instant thumbnail generation (seconds).**

### 5. Video Streaming (NGINX Direct)
- Dedicated NGINX container serves `.web.mp4` files directly from disk
- **secure_link module** — signed URLs with MD5 hash + expiry timestamp
- Shared secret between backend and NGINX (injected via entrypoint.sh at container startup)
- Frontend requests signed URL from backend → redirected to NGINX → NGINX serves file
- Supports HTTP Range requests for seeking
- Downloads serve original full-quality files (not transcoded)

### 6. Share Links
- Create password-protected shareable gallery links
- Configurable access levels: view / download / full
- Optional expiry dates
- Custom slugs (vanity URLs)
- Toggle active/inactive
- Labels for identifying links (e.g. "Main Gallery Link", "Guest Upload Link")
- **Guest upload mode** — separate share type where clients upload their own photos
- Guest upload size limits and optional compression

### 7. QR Code PDFs
- 3 designs: Minimal, Classic, Botanical
- Generated using Pillow with custom fonts and frame backgrounds
- Design preview endpoint
- Returns PDF with QR code linking to share URL

### 8. Client-Facing Gallery (ShareView)
- **Progressive image loading** — sharp thumbnails in grid, blur-to-sharp in lightbox (ProgressiveImage component)
- **CSS watermarks** — logo overlay on previews (72% opacity), downloads are clean/unwatermarked
- **Dark/Light mode** toggle ("Classic Timeless" theme)
- **Cinematic slideshow** — Ken Burns effect with custom audio tracks, shareable slideshow links
- **Cover images** positioned at `center 25%` (shows faces, not flowers)
- **Album cards** with hover zoom effect and gradient overlays
- **Favouriting** — heart icon on photos, gold heart counter, submit favourites for album
- **Download All** button — bold CTA for downloading entire gallery as ZIP
- **Download progress** — visual percentage overlay for large files
- **Guest uploads** — clients upload their own photos/videos from the share view
- **Print ordering** — view print sizes, place orders, PayPal integration
- **Responsive** — mobile-first, instruction cards stack vertically on mobile (grid-cols-1 sm:grid-cols-3)

### 9. Album Instructions (Client-Facing)
Three elegant visual step cards:
1. Heart Your Favourites — "Open your Wedding Images folder and tap the heart on your 40 favourite photos"
2. Choose Your Cover — "Pick one special image for the front cover of your album"
3. Submit Your Album — "Tap the gold heart at the top, then press Submit for Album"

### 10. Live Visitor Tracking
- **30-second heartbeats** from ShareView (sends session_id, action, subfolder, detail)
- Backend stores active sessions, cleans up after 60s inactivity
- **Admin Dashboard panel**: "Live Gallery Visitors"
  - Empty: "No couples are currently viewing galleries"
  - Active: "Gallery Name — viewing Wedding Images" / "downloading Video" etc.
  - Shows device type (Mobile/Tablet/Desktop), duration, action icons
  - Dark header with pulsing green "Live" badge when visitors active

### 11. Activity Logging
- Tracks views, downloads (with exact filenames), favourites, submissions
- **Search** by name/gallery
- **Auto-archive** after 6 months (background startup hook)
- **Manual archive** button
- **Archive tab** — view archived logs
- **Clear logs** with confirmation
- Activity stats endpoint

### 12. Admin Dashboard Stats
5 stat cards at top:
- **Active Galleries** (gold tint)
- **Expiring Soon** — shares expiring within 14 days (amber tint)
- **Downloads This Week** (green tint)
- **Pending Albums** — galleries with no Album Favourites files (pink tint)
- **Storage Used** — auto-formats GB/TB (indigo tint)

### 13. SMTP Email System
- Configurable SMTP settings in admin Settings page
- Fields: server, port, email, password, sender name, **site_url** (for awards badge in emails)
- Test email button
- **CRITICAL**: `From` header MUST use `formataddr((sender_name, smtp_email))` — Hostinger returns 553 error otherwise

### 14. Email Features
- **Notify Couple** — one-click "Gallery Ready" branded email with gallery link, password, instructions
- **Broadcast Email** — mass email to all couples with gallery emails, from dashboard
- **Email Templates** — create reusable templates in Settings with `{couple_name}` and `{gallery_link}` tokens. "Send Email" button on each gallery page picks a template, auto-fills, sends in 3 clicks.
- **Automated Expiry Reminders** — daily background asyncio loop checks for main share links expiring within 7 days, sends branded reminder email. Marks `expiry_reminder_sent` to prevent duplicates.
- **Awards Badge** — public endpoint serves awards image, displayed in all branded emails when `site_url` is configured
- **Email Log** — "Emails" tab on Activity page shows ALL sent emails (type, subject, gallery name, recipient, date). Types: broadcast (blue), gallery_ready (green), expiry_reminder (amber), template (logged too).

### 15. Backup System
- One-click backup from dashboard
- **Backup-aware deletion** — when deleting a gallery or file, confirmation dialog shows "Also delete from backup?" checkbox
- Backup path: `{BACKUP_DIR}/{tenant_id}/{gallery_folder}/`

### 16. Print Sizes & Orders
- Configurable print sizes (name, dimensions, price)
- Client-facing print order flow
- PayPal payment link integration
- Order status tracking (admin can update)

### 17. Video Compression Settings
- Admin can set target compression bitrate
- Stored in settings collection

---

## DATABASE COLLECTIONS (MongoDB)

All collections below need `tenant_id` field added for multi-tenancy (except `super_admins` and `tenants`).

### Existing (add tenant_id):
- `admins` — Tenant admin users (username, hashed password, TOTP secret, tenant_id)
- `galleries` — Gallery metadata (id, folder_name, subfolders, file_counts, covers, client_email, tenant_id)
- `files` — File records (id, gallery_id, subfolder, filename, file_type, file_size, has_thumb, has_preview, tenant_id)
- `shares` — Share links (id, gallery_id, token, subfolder, password_hash, access_level, is_active, expires_at, label, guest_upload_mode, custom_slug, expiry_reminder_sent, tenant_id)
- `favourites` — Client favourited photos (tenant_id)
- `activity_log` — View/download tracking (tenant_id)
- `activity_log_archive` — Auto-archived logs >6 months (tenant_id)
- `email_log` — All sent emails with type/subject/recipient/timestamp (tenant_id)
- `email_templates` — Reusable templates with {couple_name}/{gallery_link} tokens (tenant_id)
- `templates` — Gallery templates / subfolder presets (tenant_id)
- `settings` — Key-value store: smtp config, compression, site_url (tenant_id)
- `print_sizes` — Print size options (tenant_id)
- `print_orders` — Print orders (tenant_id)

### New collections:
- `super_admins` — Super admin account(s) (username, hashed password)
- `tenants` — Photographer accounts (id, business_name, email, logo_url, accent_color, plan, storage_limit_bytes, storage_used_bytes, subscription_status, stripe_customer_id, stripe_subscription_id, created_at, suspended, onboarding_complete)

---

## COMPLETE API ENDPOINT LIST (100+ endpoints)

### Auth
```
POST /api/admin/check-setup
POST /api/admin/setup
POST /api/admin/login
PUT  /api/admin/change-password
```

### 2FA
```
GET  /api/admin/2fa/status
POST /api/admin/2fa/setup
POST /api/admin/2fa/enable
POST /api/admin/2fa/disable
```

### Gallery Templates
```
GET    /api/admin/templates
POST   /api/admin/templates
PUT    /api/admin/templates/{id}
DELETE /api/admin/templates/{id}
```

### Galleries
```
POST   /api/admin/galleries
GET    /api/admin/galleries
GET    /api/admin/galleries/{id}
PUT    /api/admin/galleries/{id}
DELETE /api/admin/galleries/{id}?delete_backup=true|false
PUT    /api/admin/galleries/{id}/subfolders/{name}/cover
DELETE /api/admin/galleries/{id}/subfolders/{name}
```

### File Operations
```
POST   /api/admin/galleries/{id}/upload (chunked)
DELETE /api/admin/galleries/{id}/files/{file_id}?delete_backup=true|false
POST   /api/admin/galleries/{id}/copy-to-subfolder
GET    /api/admin/galleries/{id}/download-subfolder
GET    /api/admin/galleries/{id}/download-file/{file_id}
```

### Video
```
POST   /api/admin/galleries/{id}/reprocess-videos
GET    /api/admin/galleries/{id}/reprocess-progress
GET    /api/admin/galleries/{id}/transcode-status
```

### Shares
```
POST   /api/admin/galleries/{id}/shares
GET    /api/admin/galleries/{id}/shares
DELETE /api/admin/shares/{id}
PUT    /api/admin/shares/{id}/toggle
PUT    /api/admin/shares/{id}/expiry
GET    /api/admin/shares/{id}/qr
GET    /api/admin/shares/{id}/qr-frame
GET    /api/admin/qr-design-preview/{design_num}
```

### Public Share Access (no admin auth)
```
GET    /api/share/{token}
POST   /api/share/{token}/access
GET    /api/share/{token}/open-access
GET    /api/share/{token}/files
POST   /api/share/{token}/favourite
POST   /api/share/{token}/submit-favourites
GET    /api/share/{token}/video-token/{file_id}
GET    /api/v/{vtoken}
GET    /api/share/{token}/stream/{file_id}
GET    /api/share/{token}/download/{file_id}
POST   /api/share/{token}/download-zip
GET    /api/share/{token}/download-album
GET    /api/share/{token}/download-favourites
POST   /api/share/{token}/upload (guest uploads)
GET    /api/share/{token}/guest-upload-count
POST   /api/share/{token}/delete (guest upload deletion)
POST   /api/share/{token}/track-view
POST   /api/share/{token}/track-download
POST   /api/share/{token}/heartbeat
```

### Print System
```
GET    /api/admin/print-sizes
POST   /api/admin/print-sizes
PUT    /api/admin/print-sizes/{id}
DELETE /api/admin/print-sizes/{id}
GET    /api/admin/print-orders
PUT    /api/admin/print-orders/{id}/status
GET    /api/share/{token}/print-sizes
POST   /api/share/{token}/print-order
PUT    /api/share/{token}/print-order/{id}/paypal
GET    /api/share/{token}/print-orders
```

### Monitoring & Activity
```
GET    /api/admin/live-visitors
GET    /api/admin/activity
GET    /api/admin/activity/archived
DELETE /api/admin/activity/clear
POST   /api/admin/activity/archive-now
GET    /api/admin/activity/stats
GET    /api/admin/galleries/{id}/stats
GET    /api/admin/dashboard-stats
GET    /api/admin/galleries-stats
```

### Backup
```
POST   /api/admin/backup
```

### Settings
```
GET    /api/admin/settings/compression
POST   /api/admin/settings/compression
GET    /api/admin/settings/smtp
POST   /api/admin/settings/smtp
POST   /api/admin/settings/smtp/test
```

### Email
```
POST   /api/admin/galleries/{id}/notify
GET    /api/admin/broadcast-preview
POST   /api/admin/broadcast-email
GET    /api/admin/email-log
GET    /api/admin/email-templates
POST   /api/admin/email-templates
PUT    /api/admin/email-templates/{id}
DELETE /api/admin/email-templates/{id}
POST   /api/admin/galleries/{id}/send-template-email
```

### Media Serving
```
GET    /api/media/thumb/{gallery_id}/{subfolder_slug}/{filename}
GET    /api/media/preview/{gallery_id}/{subfolder_slug}/{filename}
GET    /api/media/original/{gallery_id}/{subfolder}/{filename}
GET    /api/slideshow/music/{filename}
GET    /api/public/email-assets/{filename}
```

---

## WHAT MUST BE ADDED (SaaS Layer)

### 1. Super Admin System
- **Separate auth tier** — `superadmin` / `Stu!d10App_2026xQ`
- **Super Admin Dashboard** at `/super-admin/`:
  - List all tenants with: business name, email, plan, storage used/limit, status (active/suspended/cancelled), created date
  - **Create Tenant** manually
  - **Suspend / Unsuspend** — suspended users see "Account suspended, contact support"
  - **Delete Tenant** — removes everything (DB data, files, backups) with confirmation
  - **Storage overview** — total usage across all tenants vs server capacity
  - **Revenue dashboard** — MRR, active subscriptions, churn
  - **Impersonate** — login as any tenant for support purposes

### 2. Multi-Tenancy
- **Single deployment**, single MongoDB — NOT separate stacks per tenant
- Every collection gets `tenant_id` field
- Every API endpoint filters by logged-in tenant's ID
- File storage: `/data/userfiles/{tenant_id}/{gallery_folder}/{subfolder}/`
- Backup storage: `/backup/{tenant_id}/{gallery_folder}/`
- NGINX video serving must handle tenant subdirectories
- **Complete isolation** — Tenant A cannot see anything from Tenant B

### 3. Tenant Authentication Hierarchy
```
Super Admin (Mark) → can see/manage all tenants, impersonate
  └── Tenant Admin (Photographer) → only sees their own galleries/settings/emails
       └── Share Links (Clients) → password-protected gallery access
```

### 4. Tenant Onboarding Wizard
When a new tenant admin logs in for the first time (onboarding_complete = false):
1. **Business Details** — Business name, contact email, phone, website
2. **Logo Upload** — Used for watermarks on share pages, login page branding, email headers
3. **Branding** — Primary accent colour (default gold #D4AF37), secondary colour
4. **SMTP Setup** — Their own email server (optional, can skip and set later)
5. Marks `onboarding_complete = true` when finished

### 5. Subscription Plans & Storage
Three tiers (prices set by Mark in super admin):
- **Starter** — 250GB
- **Pro** — 500GB
- **Studio** — 1TB

Implementation:
- Storage enforcement: upload endpoint checks `tenant.storage_used_bytes + file_size <= tenant.storage_limit_bytes`
- Storage dashboard: each tenant sees usage bar (e.g. "187GB / 250GB")
- Stripe monthly billing with auto-suspend on failed payment
- Super admin can manually override/extend limits
- Webhook endpoint for Stripe events (payment_succeeded, payment_failed, subscription_cancelled)

### 6. Branding (CRITICAL)

**REMOVE ALL "Weddings By Mark" references.** Every instance must be replaced:
- Page titles, headers → `{tenant.business_name}`
- Email templates → `{tenant.business_name}` with their accent colour
- Watermark → tenant's uploaded logo
- Share page hero → tenant's branding
- QR PDFs → tenant's business name
- Login page → tenant's logo and business name
- Notify couple email → tenant's branding
- Awards badge in emails → per-tenant (they upload their own or leave blank)
- Album instructions → use tenant's email address, not mark@perfectweddingsbymark.uk

**ADD to every page (admin AND client-facing), in the footer:**
```
Site Designed & Hosted by StudioApp
```
This appears on ALL pages for ALL tenants. It's the platform branding.

**ADD to every email footer:**
```
Powered by StudioApp
```

### 7. Modularize Backend
Since building from scratch for the SaaS version, break the ~3900 line `server.py` into proper modules:
```
backend/
├── server.py (app setup, middleware, startup hooks only)
├── routes/
│   ├── auth.py
│   ├── galleries.py
│   ├── shares.py
│   ├── email.py
│   ├── video.py
│   ├── activity.py
│   ├── settings.py
│   ├── print.py
│   ├── backup.py
│   └── super_admin.py
├── services/
│   ├── thumbnail.py
│   ├── transcode.py
│   └── smtp.py
├── models/
│   └── schemas.py
├── middleware/
│   └── tenant.py (tenant_id injection from JWT)
└── utils/
    └── helpers.py
```

---

## FRONTEND ARCHITECTURE

### Pages (Current):
- `AdminLogin.js` — Login page
- `AdminDashboard.js` — Dashboard with 5 stat cards, live visitors, gallery list, broadcast email
- `AdminGalleryDetail.js` — Gallery management (files, shares, transcode, notify, send email)
- `AdminSettings.js` — Tabs: Password, 2FA, Email Settings, Email Templates, Video Compression, Print Sizes, Orders
- `AdminActivity.js` — Tabs: Active logs, Archive, Emails
- `ShareView.js` — Client-facing gallery (progressive images, lightbox, slideshow, favourites, downloads, heartbeats, dark mode)

### New Pages Needed:
- `SuperAdminLogin.js` — Super admin login at `/super-admin`
- `SuperAdminDashboard.js` — Tenant management, revenue, storage overview
- `TenantOnboarding.js` — First-run wizard for new photographers

### Components:
- `VideoPlayer.js` — video.js wrapper
- `ProgressiveImage.js` — blur-to-sharp image loading
- `ui/` — Full Shadcn/UI component library (already installed)

### Critical Frontend Config:
- `REACT_APP_BACKEND_URL` — empty string for same-origin in production
- All API calls go through `lib/api.js` via Axios with JWT Bearer token
- Frontend NGINX proxies `/api/` to backend:8001, `/video/` to nginx-video:8090

---

## NGINX VIDEO SERVER (Critical Detail)

### How It Works:
1. Backend generates a signed URL: `md5(secret + uri + expires)` → base64
2. Frontend redirects to `https://domain/video/{tenant_id}/{gallery}/{subfolder}/{file}.web.mp4?md5=xxx&expires=xxx`
3. NGINX `secure_link` module verifies the signature
4. If valid → serves file directly from disk with `sendfile`, `tcp_nopush`, `tcp_nodelay`
5. Supports `Range` headers for video seeking

### NGINX Config:
```nginx
server {
    listen 8090;
    set $video_secret "__NGINX_VIDEO_SECRET__";
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

### entrypoint.sh:
```sh
#!/bin/sh
sed -i "s|__NGINX_VIDEO_SECRET__|${NGINX_VIDEO_SECRET}|g" /etc/nginx/conf.d/default.conf
exec "$@"
```

---

## CRITICAL IMPLEMENTATION NOTES

1. **SMTP From Header**: MUST use `formataddr((sender_name, smtp_email))` — Hostinger rejects otherwise with 553
2. **Thread Pools**: NEVER merge `thumbnail_executor` (8 workers) and `transcode_executor` (2 workers)
3. **VAAPI Transcoding**: GPU device `/dev/dri/renderD128` must be passed through. Always try GPU first, fall back to CPU
4. **Video Faststart**: Run `ensure_video_faststart` on upload to move moov atom to start
5. **Cover Image Positioning**: Use `background-position: center 25%` and `object-position: center 25%` — shows faces, not flowers
6. **Instruction Cards**: Must be responsive — `grid-cols-1 sm:grid-cols-3`
7. **Expiry Reminders**: Background asyncio loop, runs daily, only sends to main links (not guest upload links), marks `expiry_reminder_sent` to prevent duplicates
8. **Frontend**: `REACT_APP_BACKEND_URL` = empty string for same-origin production
9. **File Upload**: Chunked uploads supporting 40GB+ — `client_max_body_size 40G` in frontend NGINX config
10. **Backup-Aware Delete**: Both gallery and file delete endpoints accept `?delete_backup=true` query param

---

## BUILD PRIORITY ORDER

1. **Set up project structure** — Modular backend, React frontend, Docker Compose with the exact mount paths above
2. **Port all features** — Every feature from the list above, working in single-tenant mode first
3. **Multi-tenancy layer** — Add `tenant_id` to all collections and queries, tenant-aware JWT middleware
4. **Super Admin** — Dashboard, tenant CRUD, suspend/unsuspend, impersonation, storage overview
5. **Tenant onboarding wizard** — Business name, logo, colours, SMTP
6. **Per-tenant branding** — Replace all hardcoded "Weddings By Mark" with tenant config. Add "Site Designed & Hosted by StudioApp" footer everywhere.
7. **Storage quotas** — 250GB/500GB/1TB plans, enforcement on upload, usage tracking
8. **Stripe billing** — Monthly subscriptions, webhooks, auto-suspend on failed payment
9. **Testing** — Full end-to-end testing of multi-tenant isolation, billing, all features

---

## SOURCE CODE REFERENCE

The complete working single-tenant codebase is in GitHub repo `180226galleryrepo` under Mark's account. Use it as reference for all feature implementations. The new `studioapp` repo should be built as a clean modular architecture from the start, not a direct copy-paste.
