# Weddings By Mark - Gallery Management System PRD

## Original Problem Statement
Build a full working web app like weddingsbymark.uk - a wedding photography client gallery management system. Self-hosted on TrueNAS. No Emergent references. Needs Docker Compose YAML and GitHub-pushable repo.

## User Personas
1. **Mark (Admin/Photographer)**: Manages galleries, uploads photos/videos, shares links with couples
2. **Wedding Couples (Clients)**: Access password-protected galleries, browse photos, favourite selections, download photos

## Core Requirements
- Admin authentication (JWT)
- Gallery CRUD with per-gallery passwords
- Photo/video upload with automatic thumbnails + previews
- Client password-protected gallery access
- Photo favouriting system
- Individual + bulk zip downloads
- Docker Compose for self-hosting on TrueNAS
- Port 3037, app data at /mnt/apps/newweddingsbymarkgallery, user files at /mnt/nextcloud/newwedidngsbymarkuserfiles

## What's Been Implemented (Feb 2026)
- [x] Full FastAPI backend with all CRUD endpoints
- [x] MongoDB models for admins, galleries, photos, favourites
- [x] JWT authentication for admin + session tokens for clients
- [x] Photo upload with Pillow thumbnail/preview generation
- [x] Local filesystem storage with configurable UPLOAD_DIR
- [x] React frontend with editorial "Cinematic Wedding" design
- [x] Admin: Login, Dashboard, Gallery Detail pages
- [x] Client: Gallery Access, Gallery View with masonry layout + lightbox
- [x] Favouriting system with heart icons
- [x] Single photo + bulk zip download
- [x] Docker Compose with MongoDB, backend, frontend services
- [x] Dockerfiles for backend (Python) and frontend (Node build -> Nginx)
- [x] Nginx config for SPA routing + API proxy

## Architecture
- Backend: FastAPI on port 8001
- Frontend: React (served by Nginx on port 80, mapped to 3037)
- Database: MongoDB 7
- Storage: Local filesystem (Docker volume mapped)

## Prioritized Backlog
### P0 (Critical)
- All core features implemented ✓

### P1 (Important)
- Gallery link expiry dates
- Watermarking support for previews
- Slideshow view mode
- Admin password change

### P2 (Nice to Have)
- Email notifications to couples
- Gallery view analytics/stats
- Custom branding per gallery
- Video thumbnail generation
- Drag-to-reorder photos

## Next Tasks
- User to test on TrueNAS with actual photos
- Configure JWT_SECRET in production compose file
- Set REACT_APP_BACKEND_URL to actual server domain/IP
