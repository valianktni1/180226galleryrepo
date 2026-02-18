# Weddings By Mark - TrueNAS Deployment Guide

## Quick Start (Dockge)

### Step 1: Push to GitHub
Use the "Save to Github" button in Emergent to push this repository to your GitHub account.

### Step 2: Clone on TrueNAS
```bash
cd /mnt/apps/newweddingsbymarkgallery
git clone https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git app
cd app
```

### Step 3: Configure
Edit `docker-compose.yml` and update:
- Line 58: Change `YOUR_TRUENAS_IP` to your actual TrueNAS IP (e.g., `192.168.1.100`)

Generate a secure JWT secret:
```bash
openssl rand -hex 32
```
Then update line 44 with your generated secret.

### Step 4: Deploy with Dockge
1. Open Dockge web interface
2. Click "Compose" → "Add Stack"
3. Name it: `weddingsbymark`
4. Set the compose path to: `/mnt/apps/newweddingsbymarkgallery/app`
5. Click "Deploy"

### Step 5: Test
Open your browser: `http://YOUR_TRUENAS_IP:3037`

---

## File Storage Structure

Your wedding photos/videos will be stored at:
```
/mnt/nextcloud/newwedidngsbymarkuserfiles/
├── Gina & Mark 30.11.22/
│   ├── Wedding Images/
│   │   ├── IMG_0001.jpg
│   │   └── IMG_0002.jpg
│   ├── Video/
│   │   └── ceremony.mp4
│   ├── Album Favourites/
│   ├── Guest Uploads/
│   └── SelfieBooth/
├── Another Couple 15.03.23/
│   └── ...
└── .cache/
    └── thumbs/  (auto-generated thumbnails)
```

This folder will be accessible via your SMB share with the original filenames preserved!

---

## Production Setup (weddingsbymark.uk)

Once tested locally:

1. Update `docker-compose.yml`:
   - Change `REACT_APP_BACKEND_URL` to `https://weddingsbymark.uk`

2. Rebuild the frontend:
   ```bash
   docker-compose build frontend
   docker-compose up -d
   ```

3. Set up your reverse proxy (Cloudflare/nginx) to point to port 3037

---

## Updating the App

To pull updates from GitHub:
```bash
cd /mnt/apps/newweddingsbymarkgallery/app
git pull
docker-compose build
docker-compose up -d
```

---

## Backup

Important data locations:
- **MongoDB**: `/mnt/apps/newweddingsbymarkgallery/mongodb/`
- **User Files**: `/mnt/nextcloud/newwedidngsbymarkuserfiles/`

Both should be included in your TrueNAS backup schedule.

---

## Troubleshooting

### Check logs
```bash
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f mongodb
```

### Restart services
```bash
docker-compose restart
```

### Full rebuild
```bash
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

---

## Default Admin Setup

When you first access the app, you'll be prompted to create an admin account.
- Choose a strong password
- This is used to manage all galleries and settings

---

## Features Included

✅ Gallery management with templates
✅ Custom share URLs (e.g., weddingsbymark.uk/s/ginamark301122)
✅ 4 access levels (View, Download, Upload, Full Access)
✅ Share expiry dates
✅ QR code generation
✅ Print shop with PayPal checkout
✅ Video thumbnail generation
✅ Activity tracking (views/downloads)
✅ Rate limiting on login (security)
✅ 40GB upload support for 4K videos
✅ Original filenames preserved
✅ SMB-friendly folder structure
