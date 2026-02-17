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

## Architecture
- Backend: FastAPI + MongoDB + Pillow (thumbnails) + qrcode
- Frontend: React 19 + Tailwind + shadcn/ui + Framer Motion
- Storage: Local filesystem → /mnt/nextcloud/newwedidngsbymarkuserfiles
- Thumbnails: .cache/thumbs/ directory (separate from originals)
- Auth: JWT admin + per-share session tokens
- Docker: MongoDB + Backend + Frontend (Nginx) on port 3037

## What's Implemented
- [x] Template CRUD (default + custom)
- [x] Gallery CRUD (clone from template, rename, delete)
- [x] Subfolder-based file upload with original filenames
- [x] Thumbnail + preview generation for images
- [x] Share system (password optional, per-subfolder or whole gallery)
- [x] QR code generation
- [x] Guest upload endpoint
- [x] Favouriting system
- [x] Single + ZIP download
- [x] Docker Compose + Dockerfiles
- [x] Full frontend UI (admin + client + guest)

## P1 Backlog
- Video thumbnail generation (ffmpeg)
- Gallery link expiry dates
- Slideshow view mode
- Admin password change
- Bulk share creation
