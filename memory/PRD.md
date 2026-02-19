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
- Print shop with PayPal.me checkout
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

## What's Been Implemented (Dec 2025 - Feb 2026)

### Core Features ✅
- Gallery CRUD with master folder templates
- File upload with streaming (40GB+ support)
- Background thumbnail generation (4 workers)
- Granular share permissions (View/Download/Upload/Full)
- Custom share URLs and QR codes
- Password protection and expiry dates
- Print shop with PayPal.me integration
- Custom branding with logo auto-inversion

### Recent Updates (Feb 19, 2026) ✅
**QR Code Frame Generator:**
- Elegant printable QR code frame with white roses and gold scrollwork design
- Dynamic couple name extraction from gallery folder name
- "❤ Weddings By Mark ❤" branding at bottom
- New endpoint: `GET /api/admin/shares/{share_id}/qr-frame`
- "Download Printable QR Frame" button in admin QR dialog
- Template stored at `/app/backend/assets/qr_frame_template.png`

**Guest Upload Mode:**
- New "Guest Upload Mode" checkbox when creating upload-enabled shares
- Simplified upload-only UI for wedding guests:
  - Welcome message with couple's name
  - Big prominent upload button
  - Optional name field for uploaders
  - Live counter showing total guest uploads
  - Success animation after upload
- No album browsing, no downloads, no favourites - just upload
- "GUEST MODE" badge indicator in admin shares list
- New files: `GuestUploadView.js`, field `guest_upload_mode` in shares collection
- New endpoint: `GET /api/share/{token}/guest-upload-count`

### Earlier Fixes (Feb 2026)
- Fixed yarn.lock Docker build error
- Fixed PyJWT missing dependency
- Fixed API 403 errors (token interceptor)
- Fixed empty folders not showing
- Added "Submit for Album" feature for clients
- Activity log with IP tracking
- Set Cover Image feature
- Bulk Select All/Delete All
- Thank You modal after album submission
- Persistent client sessions (Remember Me)

### Client Workflow
1. Access share link (e.g., weddingsbymark.uk/s/ebonyjonathan281025/view)
2. Browse galleries and heart favourite photos
3. Click "Favourites" to review selections
4. Click "Submit for Album" to copy to Album Favourites folder
5. Photographer downloads Album Favourites to create album

## Key API Endpoints
- `POST /api/admin/login` - Admin authentication
- `GET/POST /api/admin/galleries` - Gallery management
- `POST /api/admin/galleries/{id}/upload` - File upload
- `GET /api/admin/shares/{id}/qr` - Plain QR code
- `GET /api/admin/shares/{id}/qr-frame` - Printable QR frame with design
- `GET /api/share/{token}/files` - Get share files
- `POST /api/share/{token}/submit-favourites` - Submit favourites to album
- `GET /api/share/{token}/guest-upload-count` - Get guest upload count
- `GET/POST /api/admin/print-products` - Print shop management

## Database Collections
- users, galleries, files, shares, favourites, print_products, print_orders, activity_log

## Key Schema Fields (shares)
- `guest_upload_mode: boolean` - If true, shows simplified guest upload UI

## Backlog / Future Tasks
- P1: Slideshow mode for client gallery view
- P2: Email notifications when clients submit favourites
- P2: Client notes/comments on favourites
- P2: Batch operations in admin panel
- P3: Analytics dashboard for admin
