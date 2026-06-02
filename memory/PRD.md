# Wedding Photography Gallery - PRD

## Original Problem Statement
Self-hosted wedding photography client gallery management system. Full-featured admin panel with gallery management, chunked file uploads/downloads, robust sharing, password protection, print shop, and QR code generation.

## Core Architecture
- **Frontend:** React + Tailwind CSS + Shadcn/UI
- **Backend:** FastAPI + Motor (async MongoDB) + Pillow
- **Deployment:** Docker Compose on TrueNAS (user's own server)
- **Auth:** JWT + optional TOTP 2FA via pyotp

## Implemented Features

### Core Gallery System
- Admin-managed galleries with subfolders
- Chunked large file uploads/downloads
- Share links with password protection and expiry
- Guest upload capability
- Print shop with size selection

### Two-Factor Authentication (2FA)
- Google Authenticator TOTP via pyotp
- QR setup, recovery codes, admin settings UI

### Photographer Upload Mode
- Toggle `allow_all_file_types` on shares for second shooters
- Streaming uploads: chunks streamed directly to SSD (no memory buffering)
- RAW/XMP files visible in admin panel with FileText icon, hidden from guest shares

### QR Code Frame Generator (3 Designs)
- **Design 1 - Floral:** Botanical watercolor corners, camera icon, gold script couple name
- **Design 2 - Wavy:** Decorative wavy border with hearts, bold uppercase name
- **Design 3 - Minimal:** Clean "Share the Love" heading, centered script name
- Full AI-generated templates used as backgrounds
- Dynamic QR code, couple name, and date overlay
- Branded footer: "Designed and hosted by Weddings By Mark"
- Frontend design selector with thumbnail previews
- Endpoint: `GET /api/admin/shares/{share_id}/qr-frame?design=1|2|3`
- Preview: `GET /api/admin/qr-design-preview/{design_num}`

### Bug Fixes
- TrueNAS disaster recovery
- Hidden RAW files in admin UI
- Dockerfile: Added `fonts-liberation` for QR PDF generation in Docker

## Key API Endpoints
- `POST /api/admin/login` — Admin login (returns `requires_2fa` if enabled)
- `GET /api/admin/galleries` — List all galleries
- `POST /api/share/{token}/upload` — Streaming chunk upload
- `GET /api/admin/shares/{share_id}/qr-frame` — Generate printable QR frame PDF
- `GET /api/admin/qr-design-preview/{design_num}` — Thumbnail preview of QR design

## Key DB Schema
- `shares`: `allow_all_file_types: boolean`
- `admins`: `username, password (bcrypt hash), display_name`
- Settings stored in `settings` collection (2FA config)

## File Structure
```
/app
├── backend/
│   ├── assets/
│   │   ├── qr_templates/ (3 AI-generated design PNGs)
│   │   └── fonts/ (GreatVibes-Regular.ttf)
│   ├── Dockerfile (includes fonts-liberation)
│   ├── server.py
│   └── requirements.txt
├── frontend/src/
│   ├── lib/api.js
│   └── pages/
│       ├── AdminSettings.js (2FA)
│       ├── AdminLogin.js (2FA flow)
│       ├── AdminGalleryDetail.js (QR design selector)
│       ├── GuestUploadView.js (sequential uploads)
│       └── ShareView.js
└── memory/PRD.md
```

## Backlog / Future Tasks
- **P1:** Email Notifications when clients submit album favourites
- **P2:** Slideshow Mode for client gallery view
- **P3:** Client Comments on favourited photos
- **P4:** Watermark Previews (not affecting downloads)
- **P5:** Dark Mode for client gallery view
- **Refactoring:** Modularize server.py into route files, break down large React components

## Critical Rules
- NEVER modify `/s/{token}` URL structure (live physical QR codes exist)
- NEVER delete existing shares
- User deploys manually on TrueNAS via Docker Compose
- PayPal integration is MOCKED (paypal.me link redirect)

## Deployment Commands
```bash
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml down
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml build --no-cache
docker compose -f /mnt/apps/dockge/data/180226galleryrepo/compose.yaml up -d
```
