# Weddings By Mark - Gallery Management System PRD

## Original Problem Statement
Build a full working wedding photography client gallery system. Self-hosted on TrueNAS with Docker Compose.

## User Personas
1. **Mark (Admin/Photographer)**: Creates couple folders from templates, uploads photos to subfolders, creates share links with QR codes
2. **Wedding Couples (Clients)**: Access shared gallery via link/QR, browse photos, favourite, download
3. **Wedding Guests**: Scan QR code to upload their own photos/videos to Guest Uploads folder

## Core Requirements (v2 - Implemented Feb 2026)
- Master folder templates with subfolders (Wedding Images, Video, SelfieBooth, Album Favourites, Guest Uploads)
- Clone template to create couple folder (e.g. "Gina & Mark 30.11.22")
- Upload files to specific subfolders - ORIGINAL FILENAMES preserved
- Shares with optional password or no password
- Separate shares for gallery vs guest upload folder
- QR code generation for any share link
- Guest upload via share link
- Files stored on disk in clean folder structure (no hashes)
- Favouriting + download (single + bulk zip)
- **Granular Share Access Levels** (4 levels: View Only, Download, Upload, Full Access)

## Architecture
- Backend: FastAPI + MongoDB + Pillow (thumbnails) + qrcode
- Frontend: React 19 + Tailwind + shadcn/ui + Framer Motion
- Storage: Local filesystem → /mnt/nextcloud/newwedidngsbymarkuserfiles
- Thumbnails: .cache/thumbs/ directory (separate from originals)
- Auth: JWT admin + per-share session tokens with permission flags
- Docker: MongoDB + Backend + Frontend (Nginx) on port 3037

## What's Implemented
- [x] Template CRUD (default + custom)
- [x] Gallery CRUD (clone from template, rename, delete)
- [x] Subfolder-based file upload with original filenames
- [x] Thumbnail + preview generation for images
- [x] Share system (password optional, per-subfolder or whole gallery)
- [x] **Granular access levels for shares** (Feb 2026):
  - View Only: Can only view photos, no downloads
  - View & Download: Can view and download photos
  - View, Download & Upload: Can also upload files
  - Full Access: Can view, download, upload, AND delete files
- [x] **Share expiry system** (Feb 2026):
  - Optional expiry date when creating shares
  - Manual toggle to disable/expire shares
  - Calendar picker to set/change expiry dates on existing shares
  - Expired shares show 410 "Link Expired" page
- [x] **Custom share URLs** (Feb 2026):
  - Set custom slugs like `ginamark301122` instead of random tokens
  - URL format: `weddingsbymark.uk/s/ginamark301122`
  - Validation: only letters, numbers, hyphens allowed
  - Duplicate slug prevention
- [x] **Admin password change** (Feb 2026)
- [x] **Print Shop** (Feb 2026):
  - Admin can add/edit print sizes with prices per finish (Gloss, Luster, Silk)
  - £2.50 flat shipping (UK only)
  - Couples can browse photos and add to cart
  - Order management for admin (pending → processing → printed → shipped → completed)
  - PayPal payment flow (manual confirmation)
- [x] QR code generation
- [x] Guest upload endpoint
- [x] Favouriting system
- [x] Single + ZIP download
- [x] Docker Compose + Dockerfiles
- [x] Full frontend UI (admin + client + guest)
- [x] Permission-based UI (buttons hidden based on share access level)

## Share Access Level Implementation Details
- Backend stores `access_level` field in share documents
- JWT tokens include permission flags: `allow_downloads`, `allow_uploads`, `allow_delete`
- Backend enforces permissions on:
  - `/api/share/{token}/download/{file_id}` - checks allow_downloads
  - `/api/share/{token}/download-zip` - checks allow_downloads
  - `/api/share/{token}/upload` - checks allow_uploads
  - `/api/share/{token}/delete` - checks allow_delete (new endpoint)
- Frontend conditionally renders Download/Upload/Delete buttons based on permissions

## P1 Backlog
- Video thumbnail generation (ffmpeg)
- Slideshow view mode
- Admin password change
- Bulk share creation

## P2 Backlog
- Finalize docker-compose.yml for TrueNAS deployment
- Push repository to user's GitHub account

## Deployment Notes
- App will be deployed to weddingsbymark.uk when ready
- Self-hosted on TrueNAS server
