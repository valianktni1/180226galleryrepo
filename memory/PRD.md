# Wedding Photography Gallery Management System

## Original Problem Statement
Build a full-featured, self-hosted wedding photography client gallery management system similar to `weddingsbymark.uk`. Core requirements include admin management of galleries, master folder templates, large file uploads (40GB+) with original filenames preserved, on-the-fly ZIP downloads, granular share permissions, share expiry, custom share URLs, QR code generation, print shop with PayPal integration, and complete removal of "Emergent" branding.

## User Personas
- **Admin (Photographer):** Manages galleries, uploads photos, creates shares, manages print orders
- **Clients (Couples):** View galleries, favourite photos, submit album selections, order prints, upload guest photos

## Core Requirements
- Admin-managed client galleries with clonable master folder template
- Large file uploads (streaming) with preserved filenames
- ZIP downloads for albums
- 4 granular access levels (View, Download, Upload, Full Access)
- Password protection, share expiry, custom URL slugs
- QR code generation for shares
- Print shop with PayPal.me checkout (£15 minimum order)
- Custom branding (logo, no external branding)
- Human-readable file storage structure

## Tech Stack
- **Backend:** FastAPI, Motor (async MongoDB), PyJWT, Pillow, ffmpeg, qrcode
- **Frontend:** React, Tailwind CSS, Shadcn/UI, Framer Motion
- **Database:** MongoDB
- **Deployment:** Docker, Docker Compose (Dockge), Nginx

## Deployment Configuration
- **TrueNAS IP:** 192.168.24.10
- **Port:** 3037
- **MongoDB Volume:** /mnt/apps/newweddingsbymarkgallery/mongodb
- **User Files:** /mnt/nextcloud/newwedidngsbymarkuserfiles
- **GitHub Repo:** https://github.com/valianktni1/180226galleryrepo
- **Compose File:** /mnt/apps/dockge/data/180226galleryrepo/compose.yaml

### TrueNAS Deploy Commands (3-step)
```bash
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml down
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml build --no-cache
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml up -d
```

## What's Been Implemented (Dec 2025 - Mar 2026)

### Core Features
- Gallery CRUD with master folder templates
- File upload with streaming (40GB+ support)
- Background thumbnail generation (4 workers)
- Granular share permissions (View/Download/Upload/Full)
- Custom share URLs and QR codes
- Password protection and expiry dates
- Print shop with PayPal.me integration (£15 minimum order)
- Custom branding with logo auto-inversion
- Branded footer "Site Designed & Maintained by Weddings By Mark"

### Gallery Stats Dashboard (Feb 2026)
- Total views, unique visitors, total downloads per gallery
- Album Submitted badge on dashboard cards
- Backend endpoints: `/api/admin/galleries-stats` and `/api/admin/galleries/{id}/stats`

### QR Code Frame Generator
- Elegant printable QR code frame with design
- Dynamic couple name extraction from gallery folder name
- Endpoint: `GET /api/admin/shares/{share_id}/qr-frame`

### Guest Upload Mode
- Simplified upload-only UI for wedding guests
- 500MB file size limit for guest uploads
- Optional background video compression (FFmpeg, off by default)

### Print Shop
- £15 minimum order with disabled checkout until threshold met
- Size/finish (Gloss/Luster/Silk) selection
- Cart with PayPal.me redirect for payment
- Mobile-friendly floating cart button

### Incremental Backup System
- rsync-like backup to user-defined volume
- Endpoint: `POST /api/admin/backup`

### Security
- Login rate limiting (5 attempts/5 minutes)
- 24-hour admin session timeout (JWT)
- Password-protected shares (bug fix for blank screen)

### Activity & Tracking
- Activity log with IP tracking
- View tracking per gallery
- Download tracking

## Key API Endpoints
- `POST /api/admin/login` - Admin authentication
- `GET/POST /api/admin/galleries` - Gallery management
- `GET /api/admin/galleries-stats` - All galleries summary stats
- `GET /api/admin/galleries/{id}/stats` - Single gallery detailed stats
- `POST /api/admin/galleries/{id}/upload` - File upload
- `GET /api/admin/shares/{id}/qr` - Plain QR code
- `GET /api/admin/shares/{id}/qr-frame` - Printable QR frame
- `POST /api/admin/backup` - Incremental backup
- `GET /api/admin/settings/compression` - Compression status
- `GET /api/share/{token}` - Share info
- `POST /api/share/{token}/access` - Access share
- `GET /api/share/{token}/files` - Get share files
- `POST /api/share/{token}/submit-favourites` - Submit favourites
- `POST /api/share/{token}/upload` - Guest upload
- `GET /api/share/{token}/guest-upload-count` - Guest upload count
- `GET /api/share/{token}/print-sizes` - Print sizes for share
- `POST /api/share/{token}/print-order` - Create print order

## Database Collections
- users, galleries, files, shares, favourites, print_products, print_orders, activity_log, activity, settings

## Key Schema Fields
- **shares:** `guest_upload_mode: boolean`
- **settings:** `{ "key": "guest_video_compression", "enabled": boolean }`
- **galleries:** `total_views`, `total_downloads` fields for stats

## Frontend Routes
- `/admin` - Admin login
- `/admin/dashboard` - Admin dashboard
- `/admin/gallery/:id` - Gallery detail
- `/admin/settings` - Settings (Password, Compression, Print Sizes, Print Orders)
- `/admin/activity` - Activity log
- `/s/:token` - Share access (client-facing entry)
- `/s/:token/view` - Share view (client gallery)
- `/s/:token/prints` - Print shop

## Backlog / Future Tasks
- **P0:** QR Code Design Selector - 4 different QR frame designs at 8"x6"
- **P1:** Email Notifications when clients submit album favourites
- **P2:** Slideshow Mode for client gallery view
- **P3:** Client Comments on favourited photos
- **P4:** Watermark Previews (preview only, not downloads)
- **P5:** Dark Mode for client gallery view

## PayPal Integration
MOCKED - Uses paypal.me link redirect, not full API integration

## Verified Working (Mar 6, 2026)
All features tested and verified working after fork:
- Admin login, dashboard, gallery management
- Gallery stats (views, visitors, downloads, album submitted)
- Share access and client gallery view
- Print shop with £15 minimum
- Settings (all 5 tabs including 2FA)
- Branded footer on client pages
- All backend APIs responding correctly

### Two-Factor Authentication (May 2026)
- TOTP-based 2FA using Google Authenticator
- QR code setup flow in Settings
- 8 recovery codes (single-use, uppercase hex)
- Rate limiting: 3 attempts / 30 minute lockout
- Backend endpoints: `/api/admin/2fa/status`, `/api/admin/2fa/setup`, `/api/admin/2fa/enable`, `/api/admin/2fa/disable`

### Photographer Upload Mode (Jun 2026)
- New "Allow all file types" checkbox when creating upload/full shares
- Allows RAW files (.NEF, .CR2, .CR3, .ARW etc) and any other file type
- Existing guest upload shares unaffected (still restricted to image/video)
- "ALL FILES" badge shown on share cards in admin
- Updated UI text for photographer uploads
