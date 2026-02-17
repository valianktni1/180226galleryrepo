# Weddings By Mark - Gallery Management System

A self-hosted wedding photography client gallery management system.

## Features

- **Admin Panel**: JWT-authenticated admin dashboard to manage galleries
- **Gallery Management**: Create, edit, delete galleries with cover photos
- **Photo/Video Upload**: Drag & drop upload with automatic thumbnail & preview generation
- **Client Access**: Password-protected gallery access for wedding couples
- **Photo Favouriting**: Couples can favourite/select their preferred photos
- **Downloads**: Individual photo download + bulk zip download
- **Responsive Design**: Premium editorial design optimized for mobile & desktop

## Self-Hosting with Docker

### Prerequisites
- Docker & Docker Compose
- TrueNAS or any host with persistent storage

### Directory Setup
```bash
# Create required directories
mkdir -p /mnt/apps/newweddingsbymarkgallery/mongodb
mkdir -p /mnt/nextcloud/newwedidngsbymarkuserfiles
```

### Docker Compose

The `docker-compose.yml` is ready to use. Update the `REACT_APP_BACKEND_URL` build arg in the frontend service to your server's IP/domain.

```bash
# Edit docker-compose.yml
# Change REACT_APP_BACKEND_URL to http://YOUR_SERVER_IP:3037

# Start the stack
docker compose up -d
```

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `MONGO_URL` | `mongodb://mongodb:27017` | MongoDB connection string |
| `DB_NAME` | `weddings_by_mark` | Database name |
| `JWT_SECRET` | - | **Change this** to a strong random string |
| `UPLOAD_DIR` | `/data/userfiles` | Upload directory inside container |
| `REACT_APP_BACKEND_URL` | `http://localhost:3037` | Backend URL for frontend API calls |

### First Run

1. Navigate to `http://YOUR_SERVER:3037/admin`
2. Create your admin account (first-time setup)
3. Create galleries, upload photos, share links with couples

### Sharing with Couples

Each gallery has a unique link: `http://YOUR_SERVER:3037/gallery/{slug}`
Couples enter the gallery password to access their photos.

## Architecture

- **Frontend**: React 19 + Tailwind CSS + shadcn/ui + Framer Motion
- **Backend**: FastAPI (Python) + MongoDB (Motor async driver)
- **Storage**: Local filesystem (mapped to TrueNAS volumes)
- **Auth**: JWT tokens (admin) + per-gallery passwords (clients)

## Port

The app runs on port **3037**.
