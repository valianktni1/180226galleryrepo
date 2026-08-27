from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Depends, Form, Query, Header, Request, Body
from fastapi.responses import FileResponse, StreamingResponse, Response
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import logging
import shutil
import zipfile
import secrets
import subprocess
from pathlib import Path
from pydantic import BaseModel, Field
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
from collections import defaultdict
import time
import jwt
import psutil
import bcrypt
from PIL import Image
import pillow_heif
pillow_heif.register_heif_opener()
import aiofiles
import qrcode
import asyncio
import threading
from concurrent.futures import ThreadPoolExecutor
import pyotp
import base64
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from share_selection import main_gallery_share_query
from share_security import ShareSessionError, refresh_share_claims, share_is_expired
from security_paths import (
    UnsafePathError,
    contained_path,
    sanitise_upload_filename,
    validate_path_component,
)

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', '/app/uploads'))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
CACHE_DIR = UPLOAD_DIR / ".cache" / "thumbs"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_hex(32))

# Nginx video serving (optional — dramatically improves streaming for multi-GB files)
NGINX_VIDEO_URL = os.environ.get('NGINX_VIDEO_URL', '')  # set to any value to enable nginx video serving
NGINX_VIDEO_SECRET = os.environ.get('NGINX_VIDEO_SECRET', JWT_SECRET)  # shared secret with nginx

def generate_nginx_video_url(gallery_folder: str, subfolder: str, filename: str, expires_seconds: int = 7200) -> str:
    """Generate a signed nginx URL for direct video serving. Returns relative path."""
    expires = int(time.time()) + expires_seconds
    relative_path = f"{gallery_folder}/{subfolder}/{filename}"
    uri = f"/video/{relative_path}"
    # Hash is computed on the decoded URI (nginx decodes before checking)
    hash_input = f"{NGINX_VIDEO_SECRET}{uri}{expires}"
    md5_hash = hashlib.md5(hash_input.encode()).digest()
    b64_hash = base64.urlsafe_b64encode(md5_hash).rstrip(b'=').decode()
    # URL-encode spaces and special chars in the path for the browser
    from urllib.parse import quote
    encoded_uri = quote(uri, safe='/')
    return f"{encoded_uri}?md5={b64_hash}&expires={expires}"

# Rate limiting for login attempts
login_attempts = defaultdict(list)  # IP -> list of timestamps
MAX_LOGIN_ATTEMPTS = 3
LOGIN_WINDOW_SECONDS = 1800  # 30 minutes

# Session timeout (24 hours for admin, 72 hours for share access)
ADMIN_SESSION_HOURS = 24
SHARE_SESSION_HOURS = 72
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 48
MAX_UPLOAD_SIZE = 40 * 1024 * 1024 * 1024  # 40GB for admin
MAX_GUEST_UPLOAD_SIZE = 500 * 1024 * 1024  # 500MB per file for guests

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Startup diagnostic: log UPLOAD_DIR contents so file path issues are visible in Docker logs
logger.info(f"STARTUP: UPLOAD_DIR={UPLOAD_DIR} exists={UPLOAD_DIR.exists()}")
try:
    top_dirs = [d.name for d in UPLOAD_DIR.iterdir() if d.is_dir() and not d.name.startswith('.')]
    logger.info(f"STARTUP: Galleries on disk: {top_dirs}")
except Exception as e:
    logger.error(f"STARTUP: Could not list UPLOAD_DIR: {e}")

DEFAULT_SUBFOLDERS = ["Wedding Images", "Video", "SelfieBooth", "Album Favourites", "Guest Uploads"]

# ─── Models ───
class AdminLogin(BaseModel):
    username: str
    password: str
    totp_code: Optional[str] = None

class AdminSetup(BaseModel):
    username: str
    password: str
    display_name: str = "Weddings By Mark"

class TemplateCreate(BaseModel):
    name: str
    subfolders: List[str] = Field(default_factory=lambda: list(DEFAULT_SUBFOLDERS))

class TemplateUpdate(BaseModel):
    name: Optional[str] = None
    subfolders: Optional[List[str]] = None

class GalleryCreate(BaseModel):
    folder_name: str  # e.g. "Gina & Mark 30.11.22"
    template_id: Optional[str] = None
    client_email: Optional[str] = None
    theme: Optional[str] = "classic_gold"

class GalleryUpdate(BaseModel):
    folder_name: Optional[str] = None
    client_email: Optional[str] = None
    theme: Optional[str] = None

class ShareCreate(BaseModel):
    gallery_id: str
    subfolder: Optional[str] = None  # None = whole gallery, or specific subfolder
    password: Optional[str] = None  # None = no password
    access_level: str = "download"  # view, download, upload, full
    label: Optional[str] = None
    expires_at: Optional[str] = None  # ISO date string, None = never expires
    custom_slug: Optional[str] = None  # Custom URL slug like "ginamark301122"
    guest_upload_mode: bool = False  # If True, shows simplified guest upload UI
    allow_all_file_types: bool = False  # If True, allows RAW/any file type (photographer upload)

class FavouriteToggle(BaseModel):
    file_id: str

class ShareAccessBody(BaseModel):
    password: str = None
    viewer_id: str = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

# ─── Print Shop Models ───
class PrintSize(BaseModel):
    name: str  # e.g. "6x4", "7x5", "10x8"
    prices: dict  # {"gloss": 5.00, "luster": 6.00, "silk": 6.50}

class PrintSizeCreate(BaseModel):
    name: str
    gloss_price: float
    luster_price: float
    silk_price: float

class PrintSizeUpdate(BaseModel):
    name: Optional[str] = None
    gloss_price: Optional[float] = None
    luster_price: Optional[float] = None
    silk_price: Optional[float] = None

class PrintOrderItem(BaseModel):
    file_id: str
    size_id: str
    finish: str  # gloss, luster, silk
    quantity: int = 1

class PrintOrderCreate(BaseModel):
    gallery_id: str
    items: List[PrintOrderItem]
    customer_email: str

SHIPPING_COST = 2.50  # UK flat rate

# ─── Rate Limiting Helper ───
def check_rate_limit(ip: str) -> bool:
    """Check if IP has exceeded login attempts. Returns True if blocked."""
    now = time.time()
    # Clean old attempts
    login_attempts[ip] = [t for t in login_attempts[ip] if now - t < LOGIN_WINDOW_SECONDS]
    return len(login_attempts[ip]) >= MAX_LOGIN_ATTEMPTS

def record_login_attempt(ip: str):
    """Record a failed login attempt."""
    login_attempts[ip].append(time.time())

def clear_login_attempts(ip: str):
    """Clear login attempts on successful login."""
    login_attempts.pop(ip, None)

# ─── Auth Helpers ───
def create_jwt(data: dict, expires_hours: int = ADMIN_SESSION_HOURS) -> str:
    payload = {**data, "exp": datetime.now(timezone.utc) + timedelta(hours=expires_hours)}
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

def verify_jwt(token: str) -> dict:
    try:
        return jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_admin(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    payload = verify_jwt(token)
    if payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Not admin")
    return payload

async def get_share_session(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    payload = verify_jwt(token)
    if payload.get("role") != "share":
        raise HTTPException(status_code=403, detail="Invalid session")
    return await validate_live_share_session(payload)

# ─── File Helpers ───
def is_image(filename: str) -> bool:
    return filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff', '.heic', '.heif'))

def is_video(filename: str) -> bool:
    return filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.mts'))

def is_share_expired(share: dict) -> bool:
    """Check if a share has expired based on expires_at date."""
    return share_is_expired(share)

async def validate_live_share_session(payload: dict, expected_token: str = None) -> dict:
    """Revalidate a share JWT against MongoDB so revocation is immediate."""
    if payload.get("role") != "share" or not payload.get("share_id"):
        raise HTTPException(status_code=403, detail="Invalid session")

    share = await db.shares.find_one({"id": payload["share_id"]}, {"_id": 0})
    try:
        return refresh_share_claims(payload, share, expected_token=expected_token)
    except ShareSessionError as exc:
        status_code = 401 if str(exc) == "Share session is no longer active" else 403
        raise HTTPException(status_code=status_code, detail=str(exc)) from exc

def share_file_query(session: dict, **extra) -> dict:
    """Build a file query constrained to the live share's gallery and folder."""
    query = {"gallery_id": session["gallery_id"], **extra}
    if session.get("subfolder"):
        query["subfolder"] = session["subfolder"]
    return query

def slugify(text: str) -> str:
    return text.lower().strip().replace(' ', '-').replace('&', 'and')

def require_safe_component(value: str, label: str) -> str:
    """Translate filesystem validation failures into a safe client response."""
    try:
        return validate_path_component(value, label)
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def make_thumbnail(input_path: Path, output_path: Path, size=(400, 400)):
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail(size, Image.LANCZOS)
            img.save(output_path, "JPEG", quality=85)
        return True
    except Exception as e:
        logger.error(f"Thumbnail error for {input_path}: {e}")
        return False

def make_preview(input_path: Path, output_path: Path, size=(1600, 1600)):
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail(size, Image.LANCZOS)
            img.save(output_path, "JPEG", quality=90)
        return True
    except Exception as e:
        logger.error(f"Preview error for {input_path}: {e}")
        return False

def make_video_thumbnail(input_path: Path, output_path: Path, size=(400, 400)):
    """Generate thumbnail from video using ffmpeg."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        temp_frame = output_path.parent / f"{output_path.stem}_temp.jpg"
        
        # Extract frame at 1 second (or first frame if video is shorter)
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-ss', '00:00:01', '-vframes', '1',
            '-vf', f'scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease',
            '-q:v', '2', str(temp_frame)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if result.returncode != 0 or not temp_frame.exists():
            # Try extracting first frame if 1s failed
            cmd[4] = '00:00:00'
            subprocess.run(cmd, capture_output=True, timeout=30)
        
        if temp_frame.exists():
            # Resize to exact thumbnail size
            with Image.open(temp_frame) as img:
                img.thumbnail(size, Image.LANCZOS)
                img.save(output_path, "JPEG", quality=85)
            temp_frame.unlink()
            return True
        return False
    except Exception as e:
        logger.error(f"Video thumbnail error for {input_path}: {e}")
        return False

def make_video_preview(input_path: Path, output_path: Path, size=(1600, 900)):
    """Generate larger preview from video using ffmpeg."""
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-ss', '00:00:01', '-vframes', '1',
            '-vf', f'scale={size[0]}:{size[1]}:force_original_aspect_ratio=decrease',
            '-q:v', '2', str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=30)
        
        if result.returncode != 0 or not output_path.exists():
            cmd[4] = '00:00:00'
            subprocess.run(cmd, capture_output=True, timeout=30)
        
        return output_path.exists()
    except Exception as e:
        logger.error(f"Video preview error for {input_path}: {e}")
        return False

def get_gallery_path(folder_name: str) -> Path:
    try:
        return contained_path(UPLOAD_DIR, folder_name, labels=("gallery folder name",))
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_gallery_subfolder_path(folder_name: str, subfolder: str) -> Path:
    try:
        return contained_path(
            UPLOAD_DIR,
            folder_name,
            subfolder,
            labels=("gallery folder name", "subfolder"),
        )
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_gallery_file_path(folder_name: str, subfolder: str, filename: str) -> Path:
    try:
        return contained_path(
            UPLOAD_DIR,
            folder_name,
            subfolder,
            filename,
            labels=("gallery folder name", "subfolder", "filename"),
        )
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_thumb_path(gallery_id: str, subfolder: str, filename: str) -> Path:
    safe_filename = require_safe_component(filename, "filename")
    try:
        return contained_path(
            CACHE_DIR,
            gallery_id,
            slugify(require_safe_component(subfolder, "subfolder")),
            f"{Path(safe_filename).stem}.thumb.jpg",
            labels=("gallery id", "subfolder cache key", "thumbnail filename"),
        )
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_preview_path(gallery_id: str, subfolder: str, filename: str) -> Path:
    safe_filename = require_safe_component(filename, "filename")
    try:
        return contained_path(
            CACHE_DIR,
            gallery_id,
            slugify(require_safe_component(subfolder, "subfolder")),
            f"{Path(safe_filename).stem}.preview.jpg",
            labels=("gallery id", "subfolder cache key", "preview filename"),
        )
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_cache_gallery_path(gallery_id: str) -> Path:
    try:
        return contained_path(CACHE_DIR, gallery_id, labels=("gallery id",))
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_cache_subfolder_path(gallery_id: str, subfolder: str) -> Path:
    try:
        return contained_path(
            CACHE_DIR,
            gallery_id,
            slugify(require_safe_component(subfolder, "subfolder")),
            labels=("gallery id", "subfolder cache key"),
        )
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_backup_gallery_path(folder_name: str) -> Path:
    try:
        return contained_path(BACKUP_DIR, folder_name, labels=("backup gallery folder name",))
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def get_backup_file_path(folder_name: str, subfolder: str, filename: str) -> Path:
    try:
        return contained_path(
            BACKUP_DIR,
            folder_name,
            subfolder,
            filename,
            labels=("backup gallery folder name", "backup subfolder", "backup filename"),
        )
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

def safe_filename(filename: str, existing_dir: Path) -> str:
    """Keep original filename, append (1), (2) etc if duplicate."""
    try:
        filename = sanitise_upload_filename(filename)
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    target = existing_dir / filename
    if not target.exists():
        return filename
    stem = Path(filename).stem
    ext = Path(filename).suffix
    counter = 1
    while (existing_dir / f"{stem} ({counter}){ext}").exists():
        counter += 1
    return f"{stem} ({counter}){ext}"

# ─── Background Thumbnail Generation ───
thumbnail_executor = ThreadPoolExecutor(max_workers=8)
transcode_executor = ThreadPoolExecutor(max_workers=2)

# Video optimisation progress tracking
video_optimise_progress = {}  # gallery_id -> {total, done, current_file, step}

# Per-file transcoding progress tracking
file_transcode_progress = {}  # file_id -> {gallery_id, filename, percent, status, method}

# Live visitor tracking (in-memory, ephemeral)
active_visitors = {}  # session_id -> {gallery_id, gallery_name, action, subfolder, detail, device, last_seen, ip}
VISITOR_TIMEOUT = 60  # seconds before a visitor is considered gone

def get_video_duration(file_path: Path) -> float:
    """Get video duration in seconds using ffprobe."""
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1', str(file_path)],
            capture_output=True, text=True, timeout=30
        )
        return float(result.stdout.strip())
    except Exception:
        return 0

def get_web_version_path(file_path: Path) -> Path:
    """Get the path for the web-optimised version of a video."""
    return file_path.parent / f"{file_path.stem}.web.mp4"

def create_web_version(file_path: Path, gallery_id: str = None, file_id: str = None):
    """Create a web-optimised copy (1080p, 5Mbps) for smooth streaming. Tries GPU first, falls back to CPU. Reports real-time progress."""
    web_path = get_web_version_path(file_path)
    if web_path.exists():
        logger.info(f"Web version already exists: {web_path.name}")
        return True
    
    duration = get_video_duration(file_path)
    progress_key = file_id or file_path.stem
    temp_path = file_path.parent / f"{file_path.stem}.web.tmp.mp4"
    
    def _run_ffmpeg_with_progress(cmd, method):
        """Run FFmpeg with real-time progress tracking. Returns True on success."""
        file_transcode_progress[progress_key] = {
            "gallery_id": gallery_id,
            "filename": file_path.name,
            "percent": 0,
            "status": "transcoding",
            "method": method
        }
        if gallery_id and gallery_id in video_optimise_progress:
            video_optimise_progress[gallery_id]["current_file"] = f"Transcoding ({method}): {file_path.name}"
        
        try:
            process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            for line in process.stdout:
                line = line.strip()
                if line.startswith('out_time_us='):
                    try:
                        us = int(line.split('=')[1])
                        if duration > 0:
                            pct = min(99, int((us / 1000000) / duration * 100))
                            file_transcode_progress[progress_key]["percent"] = pct
                    except (ValueError, ZeroDivisionError):
                        pass
            process.wait(timeout=7200)
            
            if process.returncode == 0 and temp_path.exists() and temp_path.stat().st_size > 0:
                temp_path.rename(web_path)
                file_transcode_progress[progress_key]["percent"] = 100
                file_transcode_progress[progress_key]["status"] = "complete"
                logger.info(f"Web version created ({method}): {web_path.name} ({web_path.stat().st_size / (1024*1024):.0f}MB)")
                return True
            else:
                if temp_path.exists():
                    temp_path.unlink()
                logger.warning(f"{method} encoding failed for {file_path.name}")
                return False
        except Exception as e:
            logger.warning(f"{method} encoding error for {file_path.name}: {e}")
            if temp_path.exists():
                temp_path.unlink()
            return False
    
    # Try GPU encoding first (VAAPI)
    gpu_cmd = [
        'ffmpeg', '-y', '-progress', 'pipe:1', '-nostats',
        '-hwaccel', 'vaapi',
        '-hwaccel_device', '/dev/dri/renderD128',
        '-hwaccel_output_format', 'vaapi',
        '-i', str(file_path),
        '-vf', 'format=nv12|vaapi,scale_vaapi=w=-2:h=1080',
        '-c:v', 'h264_vaapi',
        '-b:v', '5M', '-maxrate', '5M', '-bufsize', '10M',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        str(temp_path)
    ]
    
    if _run_ffmpeg_with_progress(gpu_cmd, "GPU"):
        def _cleanup():
            time.sleep(15)
            file_transcode_progress.pop(progress_key, None)
        threading.Thread(target=_cleanup, daemon=True).start()
        return True
    
    logger.warning(f"GPU encoding failed for {file_path.name}, falling back to CPU")
    
    # Fallback: CPU encoding
    cpu_cmd = [
        'ffmpeg', '-y', '-progress', 'pipe:1', '-nostats',
        '-i', str(file_path),
        '-c:v', 'libx264', '-preset', 'medium',
        '-b:v', '5M', '-maxrate', '5M', '-bufsize', '10M',
        '-vf', 'scale=-2:1080',
        '-c:a', 'aac', '-b:a', '128k',
        '-movflags', '+faststart',
        '-threads', '2',
        str(temp_path)
    ]
    
    success = _run_ffmpeg_with_progress(cpu_cmd, "CPU")
    
    if not success:
        file_transcode_progress[progress_key]["status"] = "failed"
    
    def _cleanup():
        time.sleep(15)
        file_transcode_progress.pop(progress_key, None)
    threading.Thread(target=_cleanup, daemon=True).start()
    
    return success

def optimise_video_full(file_path: Path, gallery_id: str = None, file_id: str = None):
    """Run faststart on original + create web-optimised version."""
    try:
        if gallery_id and gallery_id in video_optimise_progress:
            video_optimise_progress[gallery_id]["current_file"] = f"Faststart: {file_path.name}"
        ensure_video_faststart(file_path)
        create_web_version(file_path, gallery_id, file_id)
    finally:
        if gallery_id and gallery_id in video_optimise_progress:
            video_optimise_progress[gallery_id]["done"] += 1
            if video_optimise_progress[gallery_id]["done"] >= video_optimise_progress[gallery_id]["total"]:
                video_optimise_progress[gallery_id]["current_file"] = "Complete!"

def ensure_video_faststart(file_path: Path, gallery_id: str = None):
    """Move moov atom to start of MP4 for smooth web streaming. No re-encoding — just metadata move."""
    try:
        temp_path = file_path.with_suffix('.faststart.mp4')
        result = subprocess.run([
            'ffmpeg', '-y', '-i', str(file_path),
            '-c', 'copy', '-movflags', '+faststart',
            str(temp_path)
        ], capture_output=True, timeout=600)
        if result.returncode == 0 and temp_path.exists() and temp_path.stat().st_size > 0:
            temp_path.replace(file_path)
            logger.info(f"Faststart applied: {file_path.name}")
        else:
            if temp_path.exists():
                temp_path.unlink()
            logger.warning(f"Faststart failed for {file_path.name}: {result.stderr[:200] if result.stderr else 'unknown'}")
    except Exception as e:
        logger.error(f"Faststart error for {file_path.name}: {e}")
        temp_path = file_path.with_suffix('.faststart.mp4')
        if temp_path.exists():
            temp_path.unlink()

def generate_thumbnails_background(file_path: Path, gallery_id: str, subfolder: str, filename: str, file_type: str, file_id: str):
    """Generate thumbnails in background thread - doesn't block uploads."""
    try:
        has_thumb = False
        has_preview = False
        
        if file_type == "photo":
            thumb_p = get_thumb_path(gallery_id, subfolder, filename)
            preview_p = get_preview_path(gallery_id, subfolder, filename)
            has_thumb = make_thumbnail(file_path, thumb_p)
            has_preview = make_preview(file_path, preview_p)
        elif file_type == "video":
            # First ensure faststart (moov atom at beginning) for smooth streaming
            ensure_video_faststart(file_path)
            # Generate thumbnails FIRST so they appear instantly in the UI
            thumb_p = get_thumb_path(gallery_id, subfolder, filename)
            preview_p = get_preview_path(gallery_id, subfolder, filename)
            has_thumb = make_video_thumbnail(file_path, thumb_p)
            has_preview = make_video_preview(file_path, preview_p)
        
        # Update the file record with thumbnail status using sync pymongo
        from pymongo import MongoClient
        sync_client = MongoClient(os.environ['MONGO_URL'])
        sync_db = sync_client[os.environ['DB_NAME']]
        sync_db.files.update_one(
            {"id": file_id},
            {"$set": {"has_thumb": has_thumb, "has_preview": has_preview}}
        )
        sync_client.close()
        logger.info(f"Thumbnails generated for {filename}")
        
        # Kick off web-optimised transcode in SEPARATE pool so it never blocks thumbnail workers
        if file_type == "video":
            transcode_executor.submit(create_web_version, file_path, gallery_id, file_id)
    except Exception as e:
        logger.error(f"Background thumbnail error for {filename}: {e}")

# ─── Admin Auth ───
@api_router.get("/admin/check-setup")
async def check_admin_setup():
    admin = await db.admins.find_one({}, {"_id": 0})
    return {"setup_complete": admin is not None}

@api_router.post("/admin/setup")
async def setup_admin(data: AdminSetup):
    existing = await db.admins.find_one({})
    if existing:
        raise HTTPException(status_code=400, detail="Admin already setup")
    hashed = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    admin_doc = {
        "id": str(uuid.uuid4()),
        "username": data.username,
        "password": hashed,
        "display_name": data.display_name,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.admins.insert_one(admin_doc)
    # Create default template
    default_template = {
        "id": str(uuid.uuid4()),
        "name": "Default Wedding",
        "subfolders": list(DEFAULT_SUBFOLDERS),
        "is_default": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.templates.insert_one(default_template)
    token = create_jwt({"sub": admin_doc["id"], "role": "admin", "username": data.username})
    return {"token": token, "username": data.username, "display_name": data.display_name}

@api_router.post("/admin/login")
async def admin_login(data: AdminLogin, request: Request):
    # Get client IP for rate limiting
    client_ip = request.client.host if request.client else "unknown"
    
    # Check rate limit
    if check_rate_limit(client_ip):
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again in 30 minutes.")
    
    admin = await db.admins.find_one({"username": data.username}, {"_id": 0})
    if not admin:
        record_login_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(data.password.encode(), admin["password"].encode()):
        record_login_attempt(client_ip)
        raise HTTPException(status_code=401, detail="Invalid credentials")
    
    # Check if 2FA is enabled
    if admin.get("totp_enabled"):
        if not data.totp_code:
            # Password correct, but need 2FA code
            return {"requires_2fa": True}
        
        # Verify TOTP code
        totp = pyotp.TOTP(admin["totp_secret"])
        if not totp.verify(data.totp_code, valid_window=1):
            # Check recovery codes
            recovery_codes = admin.get("recovery_codes", [])
            if data.totp_code in recovery_codes:
                # Valid recovery code - remove it after use
                recovery_codes.remove(data.totp_code)
                await db.admins.update_one({"id": admin["id"]}, {"$set": {"recovery_codes": recovery_codes}})
            else:
                record_login_attempt(client_ip)
                raise HTTPException(status_code=401, detail="Invalid 2FA code")
    
    # Clear rate limit on successful login
    clear_login_attempts(client_ip)
    
    token = create_jwt({"sub": admin["id"], "role": "admin", "username": data.username}, expires_hours=ADMIN_SESSION_HOURS)
    return {"token": token, "username": admin["username"], "display_name": admin.get("display_name", "")}

@api_router.put("/admin/change-password")
async def change_password(data: PasswordChange, admin=Depends(get_admin)):
    admin_doc = await db.admins.find_one({"id": admin["sub"]}, {"_id": 0})
    if not admin_doc:
        raise HTTPException(status_code=404, detail="Admin not found")
    if not bcrypt.checkpw(data.current_password.encode(), admin_doc["password"].encode()):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    new_hashed = bcrypt.hashpw(data.new_password.encode(), bcrypt.gensalt()).decode()
    await db.admins.update_one({"id": admin["sub"]}, {"$set": {"password": new_hashed}})
    return {"message": "Password changed successfully"}

# ─── Two-Factor Authentication ───
class TotpVerify(BaseModel):
    code: str

@api_router.get("/admin/2fa/status")
async def get_2fa_status(admin=Depends(get_admin)):
    """Check if 2FA is enabled for the admin."""
    admin_doc = await db.admins.find_one({"id": admin["sub"]}, {"_id": 0})
    if not admin_doc:
        raise HTTPException(status_code=404, detail="Admin not found")
    return {"enabled": admin_doc.get("totp_enabled", False)}

@api_router.post("/admin/2fa/setup")
async def setup_2fa(admin=Depends(get_admin)):
    """Generate a new TOTP secret and return the provisioning URI for QR code scanning."""
    admin_doc = await db.admins.find_one({"id": admin["sub"]}, {"_id": 0})
    if not admin_doc:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    # Generate new secret
    secret = pyotp.random_base32()
    
    # Store secret temporarily (not enabled yet until verified)
    await db.admins.update_one({"id": admin["sub"]}, {"$set": {"totp_secret_pending": secret}})
    
    # Generate provisioning URI
    display_name = admin_doc.get("display_name", "Gallery Admin")
    totp = pyotp.TOTP(secret)
    uri = totp.provisioning_uri(name=admin_doc["username"], issuer_name=display_name)
    
    # Generate QR code as base64 image
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_L, box_size=6, border=2)
    qr.add_data(uri)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buffer = io.BytesIO()
    img.save(buffer, format='PNG')
    qr_base64 = base64.b64encode(buffer.getvalue()).decode()
    
    return {"secret": secret, "qr_code": f"data:image/png;base64,{qr_base64}", "uri": uri}

@api_router.post("/admin/2fa/enable")
async def enable_2fa(data: TotpVerify, admin=Depends(get_admin)):
    """Verify a TOTP code and enable 2FA. Returns recovery codes."""
    admin_doc = await db.admins.find_one({"id": admin["sub"]}, {"_id": 0})
    if not admin_doc:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    pending_secret = admin_doc.get("totp_secret_pending")
    if not pending_secret:
        raise HTTPException(status_code=400, detail="No 2FA setup in progress. Please start setup first.")
    
    # Verify the code
    totp = pyotp.TOTP(pending_secret)
    if not totp.verify(data.code, valid_window=1):
        raise HTTPException(status_code=400, detail="Invalid code. Please try again.")
    
    # Generate recovery codes
    recovery_codes = [secrets.token_hex(4).upper() for _ in range(8)]
    
    # Enable 2FA
    await db.admins.update_one({"id": admin["sub"]}, {
        "$set": {
            "totp_secret": pending_secret,
            "totp_enabled": True,
            "recovery_codes": recovery_codes
        },
        "$unset": {"totp_secret_pending": ""}
    })
    
    return {"enabled": True, "recovery_codes": recovery_codes}

@api_router.post("/admin/2fa/disable")
async def disable_2fa(data: TotpVerify, admin=Depends(get_admin)):
    """Disable 2FA. Requires a valid TOTP code or recovery code."""
    admin_doc = await db.admins.find_one({"id": admin["sub"]}, {"_id": 0})
    if not admin_doc:
        raise HTTPException(status_code=404, detail="Admin not found")
    
    if not admin_doc.get("totp_enabled"):
        raise HTTPException(status_code=400, detail="2FA is not enabled")
    
    # Verify with TOTP code or recovery code
    totp = pyotp.TOTP(admin_doc["totp_secret"])
    recovery_codes = admin_doc.get("recovery_codes", [])
    
    if not totp.verify(data.code, valid_window=1) and data.code not in recovery_codes:
        raise HTTPException(status_code=400, detail="Invalid code")
    
    # Disable 2FA
    await db.admins.update_one({"id": admin["sub"]}, {
        "$unset": {"totp_secret": "", "totp_secret_pending": "", "totp_enabled": "", "recovery_codes": ""}
    })
    
    return {"enabled": False}

# ─── Templates ───
@api_router.get("/admin/templates")
async def list_templates(admin=Depends(get_admin)):
    templates = await db.templates.find({}, {"_id": 0}).sort("created_at", 1).to_list(100)
    return templates

@api_router.post("/admin/templates")
async def create_template(data: TemplateCreate, admin=Depends(get_admin)):
    subfolders = [require_safe_component(sf, "template subfolder") for sf in data.subfolders]
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "subfolders": subfolders,
        "is_default": False,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.templates.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

@api_router.put("/admin/templates/{template_id}")
async def update_template(template_id: str, data: TemplateUpdate, admin=Depends(get_admin)):
    update = {}
    if data.name is not None:
        update["name"] = data.name
    if data.subfolders is not None:
        update["subfolders"] = [require_safe_component(sf, "template subfolder") for sf in data.subfolders]
    if not update:
        raise HTTPException(status_code=400, detail="Nothing to update")
    await db.templates.update_one({"id": template_id}, {"$set": update})
    updated = await db.templates.find_one({"id": template_id}, {"_id": 0})
    return updated

@api_router.delete("/admin/templates/{template_id}")
async def delete_template(template_id: str, admin=Depends(get_admin)):
    tmpl = await db.templates.find_one({"id": template_id})
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    if tmpl.get("is_default"):
        raise HTTPException(status_code=400, detail="Cannot delete default template")
    await db.templates.delete_one({"id": template_id})
    return {"success": True}

# ─── Gallery (Couple Folder) CRUD ───
@api_router.post("/admin/galleries")
async def create_gallery(data: GalleryCreate, admin=Depends(get_admin)):
    folder_name = require_safe_component(data.folder_name, "gallery folder name")
    # Get template subfolders
    subfolders = list(DEFAULT_SUBFOLDERS)
    if data.template_id:
        tmpl = await db.templates.find_one({"id": data.template_id}, {"_id": 0})
        if tmpl:
            subfolders = tmpl["subfolders"]

    subfolders = [require_safe_component(sf, "gallery subfolder") for sf in subfolders]
    gallery_id = str(uuid.uuid4())
    folder_path = get_gallery_path(folder_name)

    # Create physical folders
    for sf in subfolders:
        (folder_path / sf).mkdir(parents=True, exist_ok=True)

    doc = {
        "id": gallery_id,
        "folder_name": folder_name,
        "subfolders": subfolders,
        "template_id": data.template_id,
        "client_email": data.client_email or "",
        "theme": data.theme or "classic_gold",
        "file_counts": {sf: 0 for sf in subfolders},
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    await db.galleries.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

@api_router.get("/admin/galleries")
async def list_galleries(admin=Depends(get_admin), sort_by: str = Query("date_desc")):
    # Sorting options: date_desc, date_asc, name_asc, name_desc
    sort_field = "created_at"
    sort_dir = -1  # descending
    if sort_by == "date_asc":
        sort_dir = 1
    elif sort_by == "name_asc":
        sort_field = "folder_name"
        sort_dir = 1
    elif sort_by == "name_desc":
        sort_field = "folder_name"
        sort_dir = -1
    
    galleries = await db.galleries.find({}, {"_id": 0}).sort(sort_field, sort_dir).to_list(1000)
    # Enrich with share count + cover image for card
    for g in galleries:
        share_count = await db.shares.count_documents({"gallery_id": g["id"]})
        g["share_count"] = share_count
        g["cover_thumb"] = None
        
        # Prefer the chosen cover image (check Wedding Images first, then any subfolder)
        covers = g.get("covers", {})
        cover_file = None
        if covers:
            # Try Wedding Images cover first, then any other
            cover_id = covers.get("Wedding Images") or next(iter(covers.values()), None)
            if cover_id:
                cover_file = await db.files.find_one({"id": cover_id, "gallery_id": g["id"]}, {"_id": 0})
        
        # Fall back to first photo if no cover set
        if not cover_file:
            cover_file = await db.files.find_one(
                {"gallery_id": g["id"], "file_type": "photo"},
                {"_id": 0}
            )
        
        if cover_file:
            tp = get_thumb_path(g["id"], cover_file["subfolder"], cover_file["filename"])
            if tp.exists():
                g["cover_thumb"] = f"/api/media/thumb/{g['id']}/{slugify(cover_file['subfolder'])}/{Path(cover_file['filename']).stem}.thumb.jpg"
    return galleries

@api_router.get("/admin/galleries/{gallery_id}")
async def get_gallery_detail(gallery_id: str, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    files = await db.files.find({"gallery_id": gallery_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(50000)
    shares = await db.shares.find({"gallery_id": gallery_id}, {"_id": 0}).sort("created_at", -1).to_list(100)
    
    # Auto-discover subfolders from files that aren't in the gallery's subfolders list
    known_subfolders = set(gallery.get("subfolders", []))
    file_subfolders = set(f["subfolder"] for f in files if f.get("subfolder"))
    missing = file_subfolders - known_subfolders
    if missing:
        gallery["subfolders"] = gallery.get("subfolders", []) + sorted(missing)
        await db.galleries.update_one({"id": gallery_id}, {"$set": {"subfolders": gallery["subfolders"]}})
    
    gallery["files"] = files
    gallery["shares"] = shares
    return gallery

@api_router.put("/admin/galleries/{gallery_id}")
async def update_gallery(gallery_id: str, data: GalleryUpdate, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    if data.folder_name and data.folder_name != gallery["folder_name"]:
        new_folder_name = require_safe_component(data.folder_name, "gallery folder name")
        old_path = get_gallery_path(gallery["folder_name"])
        new_path = get_gallery_path(new_folder_name)
        if old_path.exists():
            old_path.rename(new_path)
        update["folder_name"] = new_folder_name
    if data.client_email is not None:
        update["client_email"] = data.client_email
    if data.theme is not None:
        update["theme"] = data.theme
    await db.galleries.update_one({"id": gallery_id}, {"$set": update})
    updated = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    return updated

class SetCoverRequest(BaseModel):
    file_id: str

@api_router.put("/admin/galleries/{gallery_id}/subfolders/{subfolder_name}/cover")
async def set_subfolder_cover(gallery_id: str, subfolder_name: str, data: SetCoverRequest, admin=Depends(get_admin)):
    """Set a specific image as the cover for a subfolder."""
    from urllib.parse import unquote
    subfolder_name = unquote(subfolder_name)
    
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    if subfolder_name not in gallery["subfolders"]:
        raise HTTPException(status_code=404, detail="Subfolder not found")
    
    # Verify file exists
    file = await db.files.find_one({"id": data.file_id, "gallery_id": gallery_id, "subfolder": subfolder_name}, {"_id": 0})
    if not file:
        raise HTTPException(status_code=404, detail="File not found")
    
    # Store cover in gallery document
    covers = gallery.get("covers", {})
    covers[subfolder_name] = data.file_id
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {"covers": covers, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"success": True, "cover_file_id": data.file_id}

@api_router.delete("/admin/galleries/{gallery_id}/subfolders/{subfolder_name}")
async def delete_subfolder(gallery_id: str, subfolder_name: str, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    # URL-decode subfolder name
    from urllib.parse import unquote
    subfolder_name = unquote(subfolder_name)
    if subfolder_name not in gallery["subfolders"]:
        raise HTTPException(status_code=404, detail="Subfolder not found")
    # Delete physical folder
    folder_path = get_gallery_subfolder_path(gallery["folder_name"], subfolder_name)
    if folder_path.exists():
        shutil.rmtree(folder_path)
    # Delete cached thumbs
    cache_path = get_cache_subfolder_path(gallery_id, subfolder_name)
    if cache_path.exists():
        shutil.rmtree(cache_path)
    # Delete files from DB
    await db.files.delete_many({"gallery_id": gallery_id, "subfolder": subfolder_name})
    # Remove from gallery subfolders list and file_counts
    new_subs = [s for s in gallery["subfolders"] if s != subfolder_name]
    new_counts = {k: v for k, v in (gallery.get("file_counts") or {}).items() if k != subfolder_name}
    await db.galleries.update_one({"id": gallery_id}, {
        "$set": {"subfolders": new_subs, "file_counts": new_counts, "updated_at": datetime.now(timezone.utc).isoformat()}
    })
    return {"success": True, "subfolders": new_subs}

@api_router.delete("/admin/galleries/{gallery_id}")
async def delete_gallery(gallery_id: str, delete_backup: bool = Query(False), admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    folder_path = get_gallery_path(gallery["folder_name"])
    if folder_path.exists():
        shutil.rmtree(folder_path)
    cache_path = get_cache_gallery_path(gallery_id)
    if cache_path.exists():
        shutil.rmtree(cache_path)
    # Delete backup if requested
    if delete_backup:
        backup_path = get_backup_gallery_path(gallery["folder_name"])
        if backup_path.exists():
            shutil.rmtree(backup_path)
            logger.info(f"Deleted backup for gallery '{gallery['folder_name']}'")
    await db.files.delete_many({"gallery_id": gallery_id})
    await db.shares.delete_many({"gallery_id": gallery_id})
    await db.favourites.delete_many({"gallery_id": gallery_id})
    await db.galleries.delete_one({"id": gallery_id})
    return {"success": True, "backup_deleted": delete_backup}

# ─── File Upload & Management ───
@api_router.post("/admin/galleries/{gallery_id}/upload")
async def upload_files(
    gallery_id: str,
    subfolder: str = Form(...),
    files: List[UploadFile] = File(...),
    admin=Depends(get_admin)
):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    if subfolder not in gallery["subfolders"]:
        raise HTTPException(status_code=400, detail=f"Invalid subfolder: {subfolder}")

    target_dir = get_gallery_file_path(gallery["folder_name"], subfolder, ".upload-target").parent
    target_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for file in files:
        # Stream file to disk for large file support
        final_name = safe_filename(file.filename, target_dir)
        file_path = get_gallery_file_path(gallery["folder_name"], subfolder, final_name)
        file_size = 0

        async with aiofiles.open(file_path, 'wb') as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                await f.write(chunk)
                file_size += len(chunk)

        file_type = "photo" if is_image(final_name) else "video" if is_video(final_name) else "other"
        file_id = str(uuid.uuid4())

        # Save file record immediately (thumbnails will be generated in background)
        file_doc = {
            "id": file_id,
            "gallery_id": gallery_id,
            "subfolder": subfolder,
            "filename": final_name,
            "original_filename": file.filename,
            "file_type": file_type,
            "file_size": file_size,
            "has_thumb": False,
            "has_preview": False,
            "uploaded_by": "admin",
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        await db.files.insert_one(file_doc)
        uploaded.append({k: v for k, v in file_doc.items() if k != "_id"})

        # Queue thumbnail generation in background (non-blocking)
        if file_type in ("photo", "video"):
            thumbnail_executor.submit(
                generate_thumbnails_background,
                file_path, gallery_id, subfolder, final_name, file_type, file_id
            )

    # Update file counts
    count = await db.files.count_documents({"gallery_id": gallery_id, "subfolder": subfolder})
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {f"file_counts.{subfolder}": count, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )

    # ─── Auto-create share link on first "Wedding Images" upload ───
    auto_share = None
    if subfolder.lower() == "wedding images":
        try:
            # Only create if no non-guest share exists yet for this gallery
            existing_share = await db.shares.find_one({
                "gallery_id": gallery_id,
                "guest_upload_mode": {"$ne": True},
                "is_active": True
            })
            if not existing_share:
                import re, string, random
                folder_name = gallery["folder_name"]

                # Build slug: "Gina & Mark 30.10.21" → "ginamark301021"
                slug = re.sub(r'[^a-z0-9]', '', folder_name.lower())

                # Check slug uniqueness, append random chars if taken
                if await db.shares.find_one({"token": slug}):
                    slug = slug + ''.join(random.choices(string.ascii_lowercase, k=3))

                # Generate 6-char password
                auto_password = ''.join(random.choices(string.ascii_letters + string.digits, k=6))

                # Extract wedding date and calculate 3-month expiry
                expires_at = None
                date_match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})$', folder_name.strip())
                if date_match:
                    day, month, year = int(date_match.group(1)), int(date_match.group(2)), int(date_match.group(3))
                    if year < 100:
                        year += 2000
                    try:
                        from dateutil.relativedelta import relativedelta
                        wedding_date = datetime(year, month, day, tzinfo=timezone.utc)
                        expiry_date = wedding_date + relativedelta(months=3)
                        expires_at = expiry_date.isoformat()
                    except Exception:
                        pass

                hashed_pw = bcrypt.hashpw(auto_password.encode(), bcrypt.gensalt()).decode()
                share_doc = {
                    "id": str(uuid.uuid4()),
                    "gallery_id": gallery_id,
                    "token": slug,
                    "subfolder": None,
                    "password_hash": hashed_pw,
                    "password_raw": auto_password,
                    "has_password": True,
                    "access_level": "download",
                    "allow_uploads": False,
                    "guest_upload_mode": False,
                    "allow_all_file_types": False,
                    "label": gallery["folder_name"],
                    "expires_at": expires_at,
                    "is_active": True,
                    "auto_created": True,
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.shares.insert_one(share_doc)
                auto_share = {
                    "token": slug,
                    "password": auto_password,
                    "expires_at": expires_at,
                }
                await db.activity_log.insert_one({
                    "gallery_id": gallery_id,
                    "action": "auto_share_created",
                    "details": f"Auto-created share link: /{slug} (password omitted, expires: {expires_at or 'never'})",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
                logger.info(f"Auto-created share for {folder_name}: /{slug} expires={expires_at}")
        except Exception as e:
            logger.warning(f"Auto-share creation failed (upload unaffected): {e}")

    result = {"uploaded": uploaded, "count": len(uploaded)}
    if auto_share:
        result["auto_share"] = auto_share
    return result

@api_router.post("/admin/galleries/{gallery_id}/reprocess-videos")
async def reprocess_videos(gallery_id: str, admin=Depends(get_admin)):
    """Reprocess all existing videos: faststart + create web-optimised versions for streaming."""
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    videos = await db.files.find({"gallery_id": gallery_id, "file_type": "video"}, {"_id": 0}).to_list(None)
    valid_videos = []
    for v in videos:
        file_path = get_gallery_file_path(gallery["folder_name"], v["subfolder"], v["filename"])
        if file_path.exists():
            valid_videos.append((file_path, v["filename"], v["id"]))
    if not valid_videos:
        return {"queued": 0, "message": "No video files found"}
    video_optimise_progress[gallery_id] = {"total": len(valid_videos), "done": 0, "current_file": None}
    for file_path, _, fid in valid_videos:
        transcode_executor.submit(optimise_video_full, file_path, gallery_id, fid)
    return {"queued": len(valid_videos), "message": f"{len(valid_videos)} video(s) queued for web optimisation"}

@api_router.get("/admin/galleries/{gallery_id}/reprocess-progress")
async def reprocess_progress(gallery_id: str, admin=Depends(get_admin)):
    """Get video optimisation progress for a gallery."""
    progress = video_optimise_progress.get(gallery_id)
    if not progress:
        return {"active": False}
    return {
        "active": progress["done"] < progress["total"],
        "total": progress["total"],
        "done": progress["done"],
        "current_file": progress["current_file"],
    }

@api_router.get("/admin/galleries/{gallery_id}/transcode-status")
async def transcode_status(gallery_id: str, admin=Depends(get_admin)):
    """Get per-file transcoding progress for all active transcodes in a gallery."""
    active_files = {}
    for key, info in dict(file_transcode_progress).items():
        if info.get("gallery_id") == gallery_id:
            active_files[key] = {
                "filename": info["filename"],
                "percent": info["percent"],
                "status": info["status"],
                "method": info.get("method", "")
            }
    return {"active": len(active_files) > 0, "files": active_files}

@api_router.get("/admin/galleries/{gallery_id}/video-health")
async def video_health_check(gallery_id: str, admin=Depends(get_admin)):
    """Check which videos have web-optimised versions ready for smooth streaming."""
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    videos = await db.files.find({"gallery_id": gallery_id, "file_type": "video"}, {"_id": 0}).to_list(None)
    results = []
    for v in videos:
        file_path = get_gallery_file_path(gallery["folder_name"], v["subfolder"], v["filename"])
        web_path = get_web_version_path(file_path) if file_path.exists() else None
        has_web = web_path.exists() if web_path else False
        original_mb = round(file_path.stat().st_size / (1024 * 1024), 1) if file_path.exists() else 0
        web_mb = round(web_path.stat().st_size / (1024 * 1024), 1) if has_web else 0
        results.append({
            "id": v["id"],
            "filename": v["filename"],
            "subfolder": v["subfolder"],
            "original_mb": original_mb,
            "web_mb": web_mb,
            "has_web_version": has_web,
            "file_exists": file_path.exists(),
        })
    optimised = sum(1 for r in results if r["has_web_version"])
    return {
        "videos": results,
        "summary": {"total": len(results), "optimised": optimised, "not_optimised": len(results) - optimised}
    }


@api_router.delete("/admin/galleries/{gallery_id}/files/{file_id}")
async def delete_file(gallery_id: str, file_id: str, delete_backup: bool = Query(False), admin=Depends(get_admin)):
    f = await db.files.find_one({"id": file_id, "gallery_id": gallery_id}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    # Delete physical file
    file_path = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
    if file_path.exists():
        file_path.unlink()
    # Delete thumbnails
    for tp in [get_thumb_path(gallery_id, f["subfolder"], f["filename"]),
               get_preview_path(gallery_id, f["subfolder"], f["filename"])]:
        if tp.exists():
            tp.unlink()

    # Delete backup copy if requested
    if delete_backup:
        backup_file = get_backup_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
        if backup_file.exists():
            backup_file.unlink()
            logger.info(f"Deleted backup for file '{f['filename']}' in gallery '{gallery['folder_name']}'")

    await db.files.delete_one({"id": file_id})
    await db.favourites.delete_many({"file_id": file_id})

    count = await db.files.count_documents({"gallery_id": gallery_id, "subfolder": f["subfolder"]})
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {f"file_counts.{f['subfolder']}": count}}
    )
    return {"success": True, "backup_deleted": delete_backup}

# ─── Copy to Album Favourites ───
class CopyToSubfolder(BaseModel):
    file_ids: List[str]
    target_subfolder: str

@api_router.post("/admin/galleries/{gallery_id}/copy-to-subfolder")
async def copy_to_subfolder(gallery_id: str, data: CopyToSubfolder, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    if data.target_subfolder not in gallery["subfolders"]:
        raise HTTPException(status_code=400, detail=f"Target subfolder '{data.target_subfolder}' not found")

    target_dir = get_gallery_subfolder_path(gallery["folder_name"], data.target_subfolder)
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = 0

    for file_id in data.file_ids:
        f = await db.files.find_one({"id": file_id, "gallery_id": gallery_id}, {"_id": 0})
        if not f:
            continue
        src_path = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
        if not src_path.exists():
            continue
        dest_name = safe_filename(f["filename"], target_dir)
        dest_path = get_gallery_file_path(gallery["folder_name"], data.target_subfolder, dest_name)
        shutil.copy2(src_path, dest_path)

        # Generate thumbnails for the copy
        has_thumb = False
        has_preview = False
        if f["file_type"] == "photo":
            has_thumb = make_thumbnail(dest_path, get_thumb_path(gallery_id, data.target_subfolder, dest_name))
            has_preview = make_preview(dest_path, get_preview_path(gallery_id, data.target_subfolder, dest_name))

        new_doc = {
            "id": str(uuid.uuid4()),
            "gallery_id": gallery_id,
            "subfolder": data.target_subfolder,
            "filename": dest_name,
            "original_filename": f["original_filename"],
            "file_type": f["file_type"],
            "file_size": f["file_size"],
            "has_thumb": has_thumb,
            "has_preview": has_preview,
            "uploaded_by": "admin",
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        await db.files.insert_one(new_doc)
        copied += 1

    count = await db.files.count_documents({"gallery_id": gallery_id, "subfolder": data.target_subfolder})
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {f"file_counts.{data.target_subfolder}": count, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    return {"copied": copied}

# ─── Streaming Download (for large galleries) ───
@api_router.get("/admin/galleries/{gallery_id}/download-subfolder")
async def download_subfolder_zip(gallery_id: str, subfolder: str = Query(...), admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    if subfolder not in gallery.get("subfolders", []):
        raise HTTPException(status_code=404, detail="Subfolder not found")
    folder_path = get_gallery_subfolder_path(gallery["folder_name"], subfolder)
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="Subfolder not found")

    files = await db.files.find({"gallery_id": gallery_id, "subfolder": subfolder}, {"_id": 0}).to_list(50000)
    if not files:
        raise HTTPException(status_code=404, detail="No files in this subfolder")

    logger.info(f"Admin subfolder download: gallery='{gallery['folder_name']}', subfolder='{subfolder}', folder_path={folder_path}, exists={folder_path.exists()}, file_count={len(files)}")

    def iter_zip():
        buf = io.BytesIO()
        added = 0
        missing = []
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for f in files:
                fp = get_gallery_file_path(gallery["folder_name"], subfolder, f["filename"])
                if fp.exists():
                    zf.write(fp, f["filename"])
                    added += 1
                else:
                    missing.append(f["filename"])
        if missing:
            logger.error(f"Admin ZIP: {len(missing)}/{len(files)} files NOT found in '{folder_path}'. First 5: {missing[:5]}")
            try:
                disk_files = [x.name for x in folder_path.iterdir()][:10]
                logger.error(f"  Actual disk contents (first 10): {disk_files}")
            except Exception as e:
                logger.error(f"  Could not list dir: {e}")
        logger.info(f"Admin ZIP: added {added}/{len(files)} files")
        buf.seek(0)
        while True:
            chunk = buf.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    zip_name = f"{gallery['folder_name']} - {subfolder}.zip".replace(' ', '_')

    # Track download bandwidth
    total_dl_bytes = sum(f.get("file_size", 0) for f in files)
    await log_bandwidth_event("file_download", total_dl_bytes, f"Admin ZIP: {subfolder} ({len(files)} files)")

    return StreamingResponse(
        iter_zip(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_name}"',
            "Cache-Control": "no-cache"
        }
    )

@api_router.get("/admin/galleries/{gallery_id}/download-file/{file_id}")
async def admin_download_file(gallery_id: str, file_id: str, admin=Depends(get_admin)):
    f = await db.files.find_one({"id": file_id, "gallery_id": gallery_id}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    file_path = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    await log_bandwidth_event("file_download", file_path.stat().st_size, f"Admin: {f['filename']}")
    return FileResponse(file_path, filename=f["filename"], media_type="application/octet-stream")

# ─── Shares ───
@api_router.post("/admin/galleries/{gallery_id}/shares")
async def create_share(gallery_id: str, data: ShareCreate, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    if data.subfolder and data.subfolder not in gallery["subfolders"]:
        raise HTTPException(status_code=400, detail="Invalid subfolder")
    if data.access_level not in ("view", "download", "upload", "full"):
        raise HTTPException(status_code=400, detail="Invalid access level")

    # Handle custom slug or generate random token
    if data.custom_slug:
        # Validate custom slug - only alphanumeric and hyphens
        import re
        if not re.match(r'^[a-zA-Z0-9-]+$', data.custom_slug):
            raise HTTPException(status_code=400, detail="Custom URL can only contain letters, numbers, and hyphens")
        # Check if slug already exists
        existing = await db.shares.find_one({"token": data.custom_slug}, {"_id": 0})
        if existing:
            raise HTTPException(status_code=400, detail="This custom URL is already in use")
        share_token = data.custom_slug
    else:
        share_token = secrets.token_urlsafe(16)

    hashed_pw = None
    if data.password:
        hashed_pw = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()

    share_doc = {
        "id": str(uuid.uuid4()),
        "gallery_id": gallery_id,
        "token": share_token,
        "subfolder": data.subfolder,
        "password_hash": hashed_pw,
        "password_raw": data.password or "",
        "has_password": hashed_pw is not None,
        "access_level": data.access_level,
        "allow_uploads": data.access_level in ("upload", "full"),
        "guest_upload_mode": data.guest_upload_mode,  # Simplified upload-only UI
        "allow_all_file_types": data.allow_all_file_types,  # Photographer upload - any file type
        "label": data.label or (data.subfolder or gallery["folder_name"]),
        "expires_at": data.expires_at,  # ISO date string or None
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.shares.insert_one(share_doc)
    result = {k: v for k, v in share_doc.items() if k not in ("_id", "password_hash", "password_raw")}
    return result

@api_router.get("/admin/galleries/{gallery_id}/shares")
async def list_shares(gallery_id: str, admin=Depends(get_admin)):
    shares = await db.shares.find({"gallery_id": gallery_id}, {"_id": 0, "password_hash": 0}).sort("created_at", -1).to_list(100)
    return shares

@api_router.delete("/admin/shares/{share_id}")
async def delete_share(share_id: str, admin=Depends(get_admin)):
    result = await db.shares.delete_one({"id": share_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Share not found")
    return {"success": True}

@api_router.put("/admin/shares/{share_id}/toggle")
async def toggle_share(share_id: str, admin=Depends(get_admin)):
    share = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    new_active = not share.get("is_active", True)
    await db.shares.update_one({"id": share_id}, {"$set": {"is_active": new_active}})
    return {"is_active": new_active}

class ShareExpiryUpdate(BaseModel):
    expires_at: Optional[str] = None  # ISO date string or None to remove expiry

@api_router.put("/admin/shares/{share_id}/expiry")
async def update_share_expiry(share_id: str, data: ShareExpiryUpdate, admin=Depends(get_admin)):
    share = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    await db.shares.update_one({"id": share_id}, {"$set": {"expires_at": data.expires_at}})
    return {"expires_at": data.expires_at}

class ShareUpdate(BaseModel):
    password: Optional[str] = None  # New password, empty string to remove, None to keep unchanged
    label: Optional[str] = None
    access_level: Optional[str] = None

@api_router.put("/admin/shares/{share_id}")
async def update_share(share_id: str, data: ShareUpdate, admin=Depends(get_admin)):
    share = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    
    updates = {}
    if data.label is not None:
        updates["label"] = data.label
    if data.access_level is not None:
        updates["access_level"] = data.access_level
        updates["allow_uploads"] = data.access_level in ("upload", "full")
    if data.password is not None:
        if data.password == "":
            updates["password_hash"] = None
            updates["password_raw"] = ""
            updates["has_password"] = False
        else:
            updates["password_hash"] = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
            updates["password_raw"] = data.password
            updates["has_password"] = True
    
    if updates:
        await db.shares.update_one({"id": share_id}, {"$set": updates})
    
    updated = await db.shares.find_one({"id": share_id}, {"_id": 0, "password_hash": 0})
    return updated



@api_router.get("/admin/shares/{share_id}/qr")
async def get_share_qr(share_id: str, base_url: str = Query(...), token: Optional[str] = Query(None)):
    # Verify admin token (from query param since img src can't send headers)
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if payload.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    share = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    share_url = f"{base_url}/s/{share['token']}"
    qr = qrcode.QRCode(version=1, box_size=10, border=2)
    qr.add_data(share_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="#1C1917", back_color="#FDFCF8")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

@api_router.get("/admin/shares/{share_id}/qr-frame")
async def get_share_qr_frame(share_id: str, base_url: str = Query(...), token: Optional[str] = Query(None), design: int = Query(1)):
    """Generate elegant QR code frame with couple name. Designs: 1=Floral, 2=Wavy Border, 3=Elegant Minimal, 4=Classic Noir, 5=Blush Peony."""
    # Verify admin token
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if payload.get("role") != "admin":
                raise HTTPException(status_code=403, detail="Admin access required")
        except jwt.ExpiredSignatureError:
            raise HTTPException(status_code=401, detail="Token expired")
        except jwt.InvalidTokenError:
            raise HTTPException(status_code=401, detail="Invalid token")
    else:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    share = await db.shares.find_one({"id": share_id}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    
    gallery = await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    import re
    folder_name = gallery["folder_name"]
    # Extract couple name (remove date from end)
    couple_name = re.sub(r'\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$', '', folder_name).strip()
    if not couple_name:
        couple_name = folder_name
    
    # Extract date from folder name
    date_match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})$', folder_name.strip())
    date_str = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}" if date_match else ""
    
    share_url = f"{base_url}/s/{share['token']}"
    
    from PIL import ImageDraw, ImageFont
    
    # Constants
    FW, FH = 2400, 1800  # 8x6 at 300dpi
    FONTS_DIR = ROOT_DIR / "assets" / "fonts"
    TEMPLATES_DIR = ROOT_DIR / "assets" / "qr_templates"
    
    script_f = lambda s: ImageFont.truetype(str(FONTS_DIR / "GreatVibes-Regular.ttf"), s)
    serif_f = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", s)
    serif_bf = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", s)
    serif_if = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf", s)
    sans_f = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", s)
    
    def make_qr_img(url, size=550):
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qi = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        return qi.resize((size, size), Image.LANCZOS)
    
    def tc(draw, text, font, y, fill='black'):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((FW - tw) // 2, y), text, fill=fill, font=font)
    
    def add_brand(draw):
        b = "Designed and hosted by Weddings By Mark"
        bf = sans_f(22)
        bbox = draw.textbbox((0, 0), b, font=bf)
        draw.text((FW - (bbox[2] - bbox[0]) - 60, FH - 60), b, fill='#AAAAAA', font=bf)
    
    # Original templates are 1264x848, output is 2400x1800 (8"x6" at 300dpi)
    SX = FW / 1264.0
    SY = FH / 848.0

    if design == 1:
        # ── BOTANICAL GOLD ── Minimal layout + gold botanical corner frame
        # Use the AI-generated gold botanical frame as the full background
        frame = Image.open(str(TEMPLATES_DIR / "design_1_botanical_gold.png")).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        
        # Same layout as Minimal but on the botanical background
        # "Share the Love" heading at y=15%
        sf = script_f(int(75 * SX))
        tf = serif_if(int(25 * SX))
        sb = draw.textbbox((0, 0), "Share", font=sf)
        tb = draw.textbbox((0, 0), "the", font=tf)
        lb = draw.textbbox((0, 0), "Love", font=sf)
        sw = sb[2] - sb[0]
        tw2 = tb[2] - tb[0]
        lw = lb[2] - lb[0]
        total_w = sw + tw2 + lw + int(40 * SX)
        sx = (FW - total_w) // 2
        ty = int(FH * 0.15)
        draw.text((sx, ty), "Share", fill='#1C1917', font=sf)
        draw.text((sx + sw + int(20 * SX), ty + int(40 * SY)), "the", fill='#666666', font=tf)
        draw.text((sx + sw + int(20 * SX) + tw2 + int(20 * SX), ty), "Love", fill='#1C1917', font=sf)
        
        # QR code at y=48%, ~28% width
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        qr_x = (FW - qr_size) // 2
        qr_y = int(FH * 0.48) - qr_size // 2
        img.paste(qr_img, (qr_x, qr_y))
        draw = ImageDraw.Draw(img)
        
        # Instructions at y=68%
        tc(draw, "PLEASE SCAN THIS CODE TO UPLOAD &", sans_f(int(15 * SX)), int(FH * 0.68), fill='#888888')
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(15 * SX)), int(FH * 0.71), fill='#888888')
        
        # Couple name at y=78%
        tc(draw, couple_name, script_f(int(50 * SX)), int(FH * 0.78), fill='#1C1917')
        
        # Date at y=87%
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#555555')
        
        add_brand(draw)

    elif design == 2:
        # ── HEARTS ── Wavy text layout + rose gold hearts frame
        frame = Image.open(str(TEMPLATES_DIR / "design_2_hearts.png")).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        
        # Same layout as Wavy design
        # Heading: "Capture" script + "THE LOVE" bold side by side at ~22%
        cap_font = script_f(int(60 * SX))
        love_font = serif_bf(int(40 * SX))
        cap_bb = draw.textbbox((0, 0), "Capture", font=cap_font)
        love_bb = draw.textbbox((0, 0), "THE LOVE", font=love_font)
        cap_w = cap_bb[2] - cap_bb[0]
        love_w = love_bb[2] - love_bb[0]
        total = cap_w + love_w + 30
        sx = (FW - total) // 2
        head_y = int(FH * 0.22)
        draw.text((sx, head_y), "Capture", fill='#1C1917', font=cap_font)
        draw.text((sx + cap_w + 30, head_y + int(25 * SY)), "THE LOVE", fill='#1C1917', font=love_font)
        
        # QR code: center at ~50%, ~28% width
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        qr_x = (FW - qr_size) // 2
        qr_y = int(FH * 0.50) - qr_size // 2
        img.paste(qr_img, (qr_x, qr_y))
        draw = ImageDraw.Draw(img)
        
        # Instructions at ~71%
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(17 * SX)), int(FH * 0.71), fill='#333333')
        tc(draw, "JUST SCAN THE QR CODE", sans_f(int(14 * SX)), int(FH * 0.74), fill='#555555')
        
        # Couple name at ~79% (bold uppercase)
        tc(draw, couple_name.upper(), serif_bf(int(35 * SX)), int(FH * 0.79), fill='#1C1917')
        
        # Date at ~87%
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#555555')
        
        add_brand(draw)

    elif design == 4:
        # ── CLASSIC NOIR ── Black & gold elegant border
        frame = Image.open(str(TEMPLATES_DIR / "design_4_classic_noir.png")).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        
        sf = script_f(int(75 * SX))
        tf = serif_if(int(25 * SX))
        sb = draw.textbbox((0, 0), "Share", font=sf)
        tb = draw.textbbox((0, 0), "the", font=tf)
        lb = draw.textbbox((0, 0), "Love", font=sf)
        sw = sb[2] - sb[0]
        tw2 = tb[2] - tb[0]
        total_w = sw + tw2 + (lb[2] - lb[0]) + int(40 * SX)
        sx = (FW - total_w) // 2
        ty = int(FH * 0.15)
        draw.text((sx, ty), "Share", fill='#1C1917', font=sf)
        draw.text((sx + sw + int(20 * SX), ty + int(40 * SY)), "the", fill='#666666', font=tf)
        draw.text((sx + sw + int(20 * SX) + tw2 + int(20 * SX), ty), "Love", fill='#1C1917', font=sf)
        
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.48) - qr_size // 2))
        draw = ImageDraw.Draw(img)
        
        tc(draw, "PLEASE SCAN THIS CODE TO UPLOAD &", sans_f(int(15 * SX)), int(FH * 0.68), fill='#555555')
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(15 * SX)), int(FH * 0.71), fill='#555555')
        tc(draw, couple_name, script_f(int(50 * SX)), int(FH * 0.78), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#555555')
        add_brand(draw)

    elif design == 5:
        # ── BLUSH PEONY ── Romantic pink floral corners
        frame = Image.open(str(TEMPLATES_DIR / "design_5_blush_peony.png")).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        
        sf = script_f(int(75 * SX))
        tf = serif_if(int(25 * SX))
        sb = draw.textbbox((0, 0), "Share", font=sf)
        tb = draw.textbbox((0, 0), "the", font=tf)
        lb = draw.textbbox((0, 0), "Love", font=sf)
        sw = sb[2] - sb[0]
        tw2 = tb[2] - tb[0]
        total_w = sw + tw2 + (lb[2] - lb[0]) + int(40 * SX)
        sx = (FW - total_w) // 2
        ty = int(FH * 0.15)
        draw.text((sx, ty), "Share", fill='#8B5E6B', font=sf)
        draw.text((sx + sw + int(20 * SX), ty + int(40 * SY)), "the", fill='#A8808C', font=tf)
        draw.text((sx + sw + int(20 * SX) + tw2 + int(20 * SX), ty), "Love", fill='#8B5E6B', font=sf)
        
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.48) - qr_size // 2))
        draw = ImageDraw.Draw(img)
        
        tc(draw, "PLEASE SCAN THIS CODE TO UPLOAD &", sans_f(int(15 * SX)), int(FH * 0.68), fill='#A8808C')
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(15 * SX)), int(FH * 0.71), fill='#A8808C')
        tc(draw, couple_name, script_f(int(50 * SX)), int(FH * 0.78), fill='#8B5E6B')
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#A8808C')
        add_brand(draw)

    else:
        # ── MINIMAL ── Clean white, built entirely from scratch
        img = Image.new('RGB', (FW, FH), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
        # "Share the Love" heading at y=15%
        sf = script_f(int(75 * SX))
        tf = serif_if(int(25 * SX))
        sb = draw.textbbox((0, 0), "Share", font=sf)
        tb = draw.textbbox((0, 0), "the", font=tf)
        lb = draw.textbbox((0, 0), "Love", font=sf)
        sw = sb[2] - sb[0]
        tw2 = tb[2] - tb[0]
        lw = lb[2] - lb[0]
        total_w = sw + tw2 + lw + int(40 * SX)
        sx = (FW - total_w) // 2
        ty = int(FH * 0.15)
        draw.text((sx, ty), "Share", fill='#1C1917', font=sf)
        draw.text((sx + sw + int(20 * SX), ty + int(40 * SY)), "the", fill='#666666', font=tf)
        draw.text((sx + sw + int(20 * SX) + tw2 + int(20 * SX), ty), "Love", fill='#1C1917', font=sf)
        
        # QR code at y=48%, ~28% width
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        qr_x = (FW - qr_size) // 2
        qr_y = int(FH * 0.48) - qr_size // 2
        img.paste(qr_img, (qr_x, qr_y))
        draw = ImageDraw.Draw(img)
        
        # Instructions at y=68%
        tc(draw, "PLEASE SCAN THIS CODE TO UPLOAD &", sans_f(int(15 * SX)), int(FH * 0.68), fill='#888888')
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(15 * SX)), int(FH * 0.71), fill='#888888')
        
        # Couple name at y=78%
        tc(draw, couple_name, script_f(int(50 * SX)), int(FH * 0.78), fill='#1C1917')
        
        # Date at y=87%
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#555555')
        
        add_brand(draw)
    
    # Save as PDF
    buf = io.BytesIO()
    img.save(buf, format="PDF", resolution=300.0)
    buf.seek(0)
    
    safe_name = couple_name.replace(' ', '_').replace('&', 'and')
    design_names = {1: "Floral", 2: "Wavy", 3: "Minimal", 4: "Classic_Noir", 5: "Blush_Peony"}
    
    return StreamingResponse(
        buf,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{safe_name}_QR_{design_names.get(design, "Frame")}.pdf"'
        }
    )

_qr_preview_cache = {}

@api_router.get("/admin/qr-design-preview/{design_num}")
async def get_qr_design_preview(design_num: int, token: Optional[str] = Query(None)):
    """Return a small PNG thumbnail preview of a QR frame design (the template itself)."""
    if token:
        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
            if payload.get("role") != "admin":
                raise HTTPException(status_code=403)
        except Exception:
            raise HTTPException(status_code=401)
    else:
        raise HTTPException(status_code=401)

    if design_num not in (1, 2, 3, 4, 5):
        design_num = 1

    if design_num in _qr_preview_cache:
        buf = io.BytesIO(_qr_preview_cache[design_num])
        return StreamingResponse(buf, media_type="image/png")

    TEMPLATES_DIR = ROOT_DIR / "assets" / "qr_templates"
    names = {1: "design_1_botanical_gold.png", 2: "design_2_hearts.png", 3: "design_3_minimal.png", 4: "design_4_classic_noir.png", 5: "design_5_blush_peony.png"}
    img = Image.open(str(TEMPLATES_DIR / names[design_num])).convert('RGB')
    thumb = img.resize((480, 360), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="PNG", optimize=True)
    _qr_preview_cache[design_num] = buf.getvalue()
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

# ─── QR Picker Email System ───
# Sends a branded email with 3 QR design previews. Couple clicks one → auto-emails the PDF.

def _generate_qr_preview_png(share_url: str, couple_name: str, date_str: str, design: int, width=560, height=420) -> bytes:
    """Generate a small preview PNG of a QR frame design with the actual QR code."""
    from PIL import ImageDraw, ImageFont
    
    TEMPLATES_DIR = ROOT_DIR / "assets" / "qr_templates"
    FONTS_DIR = ROOT_DIR / "assets" / "fonts"
    
    FW, FH = width, height
    
    script_f = lambda s: ImageFont.truetype(str(FONTS_DIR / "GreatVibes-Regular.ttf"), s)
    serif_f = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", s)
    serif_bf = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", s)
    serif_if = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf", s)
    sans_f = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", s)
    
    def make_qr_img(url, size=120):
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=1)
        qr.add_data(url)
        qr.make(fit=True)
        qi = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        return qi.resize((size, size), Image.LANCZOS)
    
    def tc(draw, text, font, y, fill='black'):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((FW - tw) // 2, y), text, fill=fill, font=font)
    
    names = {1: "design_1_botanical_gold.png", 2: "design_2_hearts.png", 4: "design_4_classic_noir.png", 5: "design_5_blush_peony.png"}
    
    if design in names:
        frame = Image.open(str(TEMPLATES_DIR / names[design])).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
    else:
        img = Image.new('RGB', (FW, FH), (255, 255, 255))
    
    draw = ImageDraw.Draw(img)
    
    if design == 1:
        sf = script_f(20)
        tc(draw, "Share the Love", sf, int(FH * 0.10), fill='#1C1917')
        qr_size = int(FW * 0.25)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.28)))
        draw = ImageDraw.Draw(img)
        tc(draw, couple_name, script_f(16), int(FH * 0.72), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(10), int(FH * 0.84), fill='#555555')
    elif design == 2:
        tc(draw, "Capture THE LOVE", serif_bf(16), int(FH * 0.12), fill='#1C1917')
        qr_size = int(FW * 0.25)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.28)))
        draw = ImageDraw.Draw(img)
        tc(draw, couple_name.upper(), serif_bf(14), int(FH * 0.72), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(10), int(FH * 0.84), fill='#555555')
    elif design == 4:
        # Classic Noir — black & gold border, elegant serif text
        tc(draw, "Share the Love", script_f(20), int(FH * 0.10), fill='#1C1917')
        qr_size = int(FW * 0.25)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.28)))
        draw = ImageDraw.Draw(img)
        tc(draw, couple_name, script_f(16), int(FH * 0.72), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(10), int(FH * 0.84), fill='#555555')
    elif design == 5:
        # Blush Peony — romantic floral corners, soft text
        tc(draw, "Share the Love", script_f(20), int(FH * 0.10), fill='#8B5E6B')
        qr_size = int(FW * 0.25)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.28)))
        draw = ImageDraw.Draw(img)
        tc(draw, couple_name, script_f(16), int(FH * 0.72), fill='#8B5E6B')
        if date_str:
            tc(draw, date_str, serif_f(10), int(FH * 0.84), fill='#A8808C')
    else:
        sf = script_f(20)
        tc(draw, "Share the Love", sf, int(FH * 0.10), fill='#1C1917')
        qr_size = int(FW * 0.25)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.28)))
        draw = ImageDraw.Draw(img)
        tc(draw, couple_name, script_f(16), int(FH * 0.72), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(10), int(FH * 0.84), fill='#555555')
    
    # Add a subtle border
    draw.rectangle([(0, 0), (FW - 1, FH - 1)], outline='#E8E4DC', width=2)
    
    # Design label at bottom
    labels = {1: "Botanical Gold", 2: "Rose Hearts", 3: "Elegant Minimal", 4: "Classic Noir", 5: "Blush Peony"}
    label = labels.get(design, "Design")
    tc(draw, label, sans_f(11), FH - 22, fill='#A8A29E')
    
    buf = io.BytesIO()
    img.save(buf, format="PNG", optimize=True)
    return buf.getvalue()


def _make_qr_picker_token(gallery_id: str) -> str:
    """Create a signed JWT for the QR picker flow, valid for 60 days."""
    return jwt.encode(
        {"gallery_id": gallery_id, "purpose": "qr_pick", "exp": datetime.now(timezone.utc) + timedelta(days=60)},
        JWT_SECRET, algorithm="HS256"
    )

def _verify_qr_picker_token(token: str) -> str:
    """Verify and return gallery_id from a QR picker token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        if payload.get("purpose") != "qr_pick":
            raise HTTPException(status_code=403, detail="Invalid token")
        return payload["gallery_id"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=410, detail="This link has expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=403, detail="Invalid link")


@api_router.get("/public/qr-preview/{token}/{design}")
async def public_qr_preview(token: str, design: int):
    """Public endpoint: serves a QR design preview PNG (used as img src in emails)."""
    gallery_id = _verify_qr_picker_token(token)
    
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404)
    
    # Find guest upload share
    share = await db.shares.find_one(
        {"gallery_id": gallery_id, "is_active": True, "guest_upload_mode": True}, {"_id": 0}
    )
    if not share:
        # Fallback to any active share
        share = await db.shares.find_one({"gallery_id": gallery_id, "is_active": True}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="No share link found")
    
    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    site_url = smtp_doc.get("value", {}).get("site_url", "") if smtp_doc else ""
    share_url = f"{site_url}/s/{share.get('custom_slug') or share['token']}" if site_url else f"/s/{share['token']}"
    
    import re
    folder_name = gallery["folder_name"]
    couple_name = re.sub(r'\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$', '', folder_name).strip() or folder_name
    date_match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})$', folder_name.strip())
    date_str = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}" if date_match else ""
    
    if design not in (1, 2, 3, 4, 5):
        design = 1
    
    png_bytes = _generate_qr_preview_png(share_url, couple_name, date_str, design)
    
    return StreamingResponse(
        io.BytesIO(png_bytes),
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=86400"}
    )


@api_router.get("/public/qr-select/{token}/{design}")
async def public_qr_select(token: str, design: int, request: Request):
    """Public endpoint: couple clicks a QR design → generates PDF and emails it to them."""
    gallery_id = _verify_qr_picker_token(token)
    
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404)
    
    client_email = gallery.get("client_email", "")
    if not client_email:
        return Response(
            content="<html><body style='font-family:Georgia;text-align:center;padding:60px;'><h2>Sorry, no email address on file.</h2><p>Please contact your photographer.</p></body></html>",
            media_type="text/html"
        )
    
    # Find the guest upload share
    share = await db.shares.find_one(
        {"gallery_id": gallery_id, "is_active": True, "guest_upload_mode": True}, {"_id": 0}
    )
    if not share:
        share = await db.shares.find_one({"gallery_id": gallery_id, "is_active": True}, {"_id": 0})
    if not share:
        return Response(
            content="<html><body style='font-family:Georgia;text-align:center;padding:60px;'><h2>No share link found.</h2></body></html>",
            media_type="text/html"
        )
    
    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not smtp_doc or not smtp_doc.get("value", {}).get("smtp_email"):
        return Response(
            content="<html><body style='font-family:Georgia;text-align:center;padding:60px;'><h2>Email not configured.</h2></body></html>",
            media_type="text/html"
        )
    smtp = smtp_doc["value"]
    site_url = smtp.get("site_url", "")
    share_url = f"{site_url}/s/{share.get('custom_slug') or share['token']}" if site_url else f"/s/{share['token']}"
    
    if design not in (1, 2, 3, 4, 5):
        design = 1
    
    import re
    folder_name = gallery["folder_name"]
    couple_name = re.sub(r'\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$', '', folder_name).strip() or folder_name
    
    design_names = {1: "Botanical Gold", 2: "Rose Hearts", 3: "Elegant Minimal", 4: "Classic Noir", 5: "Blush Peony"}
    design_label = design_names.get(design, "Design")
    
    # Generate the full PDF by calling the existing qr-frame logic
    # We need to build it here to avoid auth issues
    date_match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})$', folder_name.strip())
    date_str = f"{date_match.group(1)}.{date_match.group(2)}.{date_match.group(3)}" if date_match else ""
    
    from PIL import ImageDraw, ImageFont
    FW, FH = 2400, 1800
    FONTS_DIR = ROOT_DIR / "assets" / "fonts"
    TEMPLATES_DIR = ROOT_DIR / "assets" / "qr_templates"
    
    script_f = lambda s: ImageFont.truetype(str(FONTS_DIR / "GreatVibes-Regular.ttf"), s)
    serif_f = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", s)
    serif_bf = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", s)
    serif_if = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf", s)
    sans_f = lambda s: ImageFont.truetype("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf", s)
    
    def make_qr_img(url, size=550):
        qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=10, border=2)
        qr.add_data(url)
        qr.make(fit=True)
        qi = qr.make_image(fill_color="black", back_color="white").convert('RGB')
        return qi.resize((size, size), Image.LANCZOS)
    
    def tc(draw, text, font, y, fill='black'):
        bbox = draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((FW - tw) // 2, y), text, fill=fill, font=font)
    
    def add_brand(draw):
        b = "Designed and hosted by Weddings By Mark"
        bf = sans_f(22)
        bbox = draw.textbbox((0, 0), b, font=bf)
        draw.text((FW - (bbox[2] - bbox[0]) - 60, FH - 60), b, fill='#AAAAAA', font=bf)
    
    SX = FW / 1264.0
    SY = FH / 848.0
    
    if design == 1:
        frame = Image.open(str(TEMPLATES_DIR / "design_1_botanical_gold.png")).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        sf = script_f(int(75 * SX))
        tf = serif_if(int(25 * SX))
        sb = draw.textbbox((0, 0), "Share", font=sf)
        tb = draw.textbbox((0, 0), "the", font=tf)
        lb = draw.textbbox((0, 0), "Love", font=sf)
        sw = sb[2] - sb[0]
        tw2 = tb[2] - tb[0]
        lw = lb[2] - lb[0]
        total_w = sw + tw2 + lw + int(40 * SX)
        sx = (FW - total_w) // 2
        ty = int(FH * 0.15)
        draw.text((sx, ty), "Share", fill='#1C1917', font=sf)
        draw.text((sx + sw + int(20 * SX), ty + int(40 * SY)), "the", fill='#666666', font=tf)
        draw.text((sx + sw + int(20 * SX) + tw2 + int(20 * SX), ty), "Love", fill='#1C1917', font=sf)
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.48) - qr_size // 2))
        draw = ImageDraw.Draw(img)
        tc(draw, "PLEASE SCAN THIS CODE TO UPLOAD &", sans_f(int(15 * SX)), int(FH * 0.68), fill='#888888')
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(15 * SX)), int(FH * 0.71), fill='#888888')
        tc(draw, couple_name, script_f(int(50 * SX)), int(FH * 0.78), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#555555')
        add_brand(draw)
    elif design == 2:
        frame = Image.open(str(TEMPLATES_DIR / "design_2_hearts.png")).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        cap_font = script_f(int(60 * SX))
        love_font = serif_bf(int(40 * SX))
        cap_bb = draw.textbbox((0, 0), "Capture", font=cap_font)
        love_bb = draw.textbbox((0, 0), "THE LOVE", font=love_font)
        cap_w = cap_bb[2] - cap_bb[0]
        total = cap_w + (love_bb[2] - love_bb[0]) + 30
        sx = (FW - total) // 2
        head_y = int(FH * 0.22)
        draw.text((sx, head_y), "Capture", fill='#1C1917', font=cap_font)
        draw.text((sx + cap_w + 30, head_y + int(25 * SY)), "THE LOVE", fill='#1C1917', font=love_font)
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.50) - qr_size // 2))
        draw = ImageDraw.Draw(img)
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(17 * SX)), int(FH * 0.71), fill='#333333')
        tc(draw, "JUST SCAN THE QR CODE", sans_f(int(14 * SX)), int(FH * 0.74), fill='#555555')
        tc(draw, couple_name.upper(), serif_bf(int(35 * SX)), int(FH * 0.79), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#555555')
        add_brand(draw)
    elif design == 4:
        frame = Image.open(str(TEMPLATES_DIR / "design_4_classic_noir.png")).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        sf = script_f(int(75 * SX))
        tf = serif_if(int(25 * SX))
        sb = draw.textbbox((0, 0), "Share", font=sf)
        tb = draw.textbbox((0, 0), "the", font=tf)
        lb = draw.textbbox((0, 0), "Love", font=sf)
        sw = sb[2] - sb[0]
        tw2 = tb[2] - tb[0]
        total_w = sw + tw2 + (lb[2] - lb[0]) + int(40 * SX)
        sx = (FW - total_w) // 2
        ty = int(FH * 0.15)
        draw.text((sx, ty), "Share", fill='#1C1917', font=sf)
        draw.text((sx + sw + int(20 * SX), ty + int(40 * SY)), "the", fill='#666666', font=tf)
        draw.text((sx + sw + int(20 * SX) + tw2 + int(20 * SX), ty), "Love", fill='#1C1917', font=sf)
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.48) - qr_size // 2))
        draw = ImageDraw.Draw(img)
        tc(draw, "PLEASE SCAN THIS CODE TO UPLOAD &", sans_f(int(15 * SX)), int(FH * 0.68), fill='#555555')
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(15 * SX)), int(FH * 0.71), fill='#555555')
        tc(draw, couple_name, script_f(int(50 * SX)), int(FH * 0.78), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#555555')
        add_brand(draw)
    elif design == 5:
        frame = Image.open(str(TEMPLATES_DIR / "design_5_blush_peony.png")).convert('RGB')
        img = frame.resize((FW, FH), Image.LANCZOS)
        draw = ImageDraw.Draw(img)
        sf = script_f(int(75 * SX))
        tf = serif_if(int(25 * SX))
        sb = draw.textbbox((0, 0), "Share", font=sf)
        tb = draw.textbbox((0, 0), "the", font=tf)
        lb = draw.textbbox((0, 0), "Love", font=sf)
        sw = sb[2] - sb[0]
        tw2 = tb[2] - tb[0]
        total_w = sw + tw2 + (lb[2] - lb[0]) + int(40 * SX)
        sx = (FW - total_w) // 2
        ty = int(FH * 0.15)
        draw.text((sx, ty), "Share", fill='#8B5E6B', font=sf)
        draw.text((sx + sw + int(20 * SX), ty + int(40 * SY)), "the", fill='#A8808C', font=tf)
        draw.text((sx + sw + int(20 * SX) + tw2 + int(20 * SX), ty), "Love", fill='#8B5E6B', font=sf)
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.48) - qr_size // 2))
        draw = ImageDraw.Draw(img)
        tc(draw, "PLEASE SCAN THIS CODE TO UPLOAD &", sans_f(int(15 * SX)), int(FH * 0.68), fill='#A8808C')
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(15 * SX)), int(FH * 0.71), fill='#A8808C')
        tc(draw, couple_name, script_f(int(50 * SX)), int(FH * 0.78), fill='#8B5E6B')
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#A8808C')
        add_brand(draw)
    else:
        img = Image.new('RGB', (FW, FH), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        sf = script_f(int(75 * SX))
        tf = serif_if(int(25 * SX))
        sb = draw.textbbox((0, 0), "Share", font=sf)
        tb = draw.textbbox((0, 0), "the", font=tf)
        lb = draw.textbbox((0, 0), "Love", font=sf)
        sw = sb[2] - sb[0]
        tw2 = tb[2] - tb[0]
        total_w = sw + tw2 + (lb[2] - lb[0]) + int(40 * SX)
        sx = (FW - total_w) // 2
        ty = int(FH * 0.15)
        draw.text((sx, ty), "Share", fill='#1C1917', font=sf)
        draw.text((sx + sw + int(20 * SX), ty + int(40 * SY)), "the", fill='#666666', font=tf)
        draw.text((sx + sw + int(20 * SX) + tw2 + int(20 * SX), ty), "Love", fill='#1C1917', font=sf)
        qr_size = int(FW * 0.28)
        qr_img = make_qr_img(share_url, qr_size)
        img.paste(qr_img, ((FW - qr_size) // 2, int(FH * 0.48) - qr_size // 2))
        draw = ImageDraw.Draw(img)
        tc(draw, "PLEASE SCAN THIS CODE TO UPLOAD &", sans_f(int(15 * SX)), int(FH * 0.68), fill='#888888')
        tc(draw, "SHARE YOUR PHOTOS WITH US!", sans_f(int(15 * SX)), int(FH * 0.71), fill='#888888')
        tc(draw, couple_name, script_f(int(50 * SX)), int(FH * 0.78), fill='#1C1917')
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.87), fill='#555555')
        add_brand(draw)
    
    # Save as PDF
    pdf_buf = io.BytesIO()
    img.save(pdf_buf, format="PDF", resolution=300.0)
    pdf_bytes = pdf_buf.getvalue()
    safe_name = couple_name.replace(' ', '_').replace('&', 'and')
    
    # Email the PDF to the couple
    awards_url = get_awards_url(smtp)
    email_html = build_branded_email(f"""
<p style="font-size:15px;color:#57534E;margin:0 0 12px 0;line-height:1.8;">
Great choice! You selected the <strong>{design_label}</strong> design.
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 12px 0;line-height:1.8;">
Your personalised QR code is attached as a PDF — ready to print at any size for your big day!
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 12px 0;line-height:1.8;">
We recommend printing at <strong>8&times;6 inches</strong> or larger for best quality.
</p>
<p style="font-size:14px;color:#A8A29E;margin:20px 0 0 0;font-style:italic;">
With love, Weddings By Mark
</p>
""", awards_url)
    
    try:
        send_smtp_email(
            smtp, client_email,
            f"Your QR Code — {design_label} Design",
            email_html,
            [{"filename": f"{safe_name}_QR_{design_label.replace(' ', '_')}.pdf", "data": pdf_bytes}]
        )
    except Exception as e:
        logging.error(f"QR picker email failed: {e}")
        return Response(
            content=f"""<html><body style="font-family:Georgia,'Times New Roman',serif;text-align:center;padding:60px;background:#FDFCF8;">
<h2 style="color:#1C1917;">Oops!</h2>
<p style="color:#57534E;">We couldn't send the email right now. Please contact your photographer.</p>
</body></html>""",
            media_type="text/html"
        )
    
    # Log it
    await db.email_log.insert_one({
        "type": "qr_picker_delivery",
        "design": design_label,
        "gallery_id": gallery_id,
        "gallery_name": couple_name,
        "recipient": client_email,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # Return a beautiful thank-you page
    return Response(
        content=f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>QR Code Sent!</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Cormorant+Garamond:wght@300;400;500&family=Manrope:wght@300;400&display=swap" rel="stylesheet">
</head>
<body style="margin:0;padding:60px 20px;background:#FDFCF8;font-family:'Manrope',sans-serif;text-align:center;min-height:100vh;display:flex;align-items:center;justify-content:center;">
<div style="max-width:480px;">
<div style="width:64px;height:64px;border-radius:50%;background:#1C1917;margin:0 auto 24px;display:flex;align-items:center;justify-content:center;">
<svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#D4AF37" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"/></svg>
</div>
<h1 style="font-family:'Cormorant Garamond',Georgia,serif;font-size:32px;color:#1C1917;margin:0 0 12px;font-weight:400;">
Beautiful Choice!
</h1>
<p style="font-size:15px;color:#57534E;line-height:1.7;margin:0 0 8px;">
The <strong>{design_label}</strong> QR code has been sent to
</p>
<p style="font-size:14px;color:#D4AF37;margin:0 0 24px;letter-spacing:0.5px;">
{client_email}
</p>
<p style="font-size:13px;color:#A8A29E;line-height:1.6;">
Check your inbox (and spam folder, just in case!) for a PDF ready to print.
</p>
<div style="margin-top:32px;height:1px;background:linear-gradient(to right,transparent,#D4AF37,transparent);"></div>
<p style="margin-top:20px;font-size:12px;color:#A8A29E;letter-spacing:1.5px;text-transform:uppercase;">Weddings By Mark</p>
</div>
</body>
</html>""",
        media_type="text/html"
    )


@api_router.post("/admin/galleries/{gallery_id}/send-qr-picker")
async def send_qr_picker_email(gallery_id: str, admin=Depends(get_admin)):
    """Send the QR design picker email to the couple."""
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    client_email = gallery.get("client_email", "")
    if not client_email:
        raise HTTPException(status_code=400, detail="No client email set for this gallery")
    
    # Find guest upload share first
    share = await db.shares.find_one(
        {"gallery_id": gallery_id, "is_active": True, "guest_upload_mode": True}, {"_id": 0}
    )
    if not share:
        share = await db.shares.find_one({"gallery_id": gallery_id, "is_active": True}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=400, detail="No active share link found. Create a Guest Upload share first.")
    
    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not smtp_doc or not smtp_doc.get("value", {}).get("smtp_email"):
        raise HTTPException(status_code=400, detail="SMTP not configured. Go to Settings > Email to set up.")
    smtp = smtp_doc["value"]
    site_url = smtp.get("site_url", "").rstrip("/")
    
    if not site_url:
        raise HTTPException(status_code=400, detail="Site URL not set in SMTP settings. Please set it so email links work.")
    
    import re
    folder_name = gallery["folder_name"]
    couple_name = re.sub(r'\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$', '', folder_name).strip() or folder_name
    
    # Generate a signed token for the public endpoints
    picker_token = _make_qr_picker_token(gallery_id)
    
    # Build preview image URLs
    previews = {i: f"{site_url}/api/public/qr-preview/{picker_token}/{i}" for i in range(1, 6)}
    selects = {i: f"{site_url}/api/public/qr-select/{picker_token}/{i}" for i in range(1, 6)}
    
    awards_url = get_awards_url(smtp)
    
    design_labels = {1: "Botanical Gold", 2: "Rose Hearts", 3: "Elegant Minimal", 4: "Classic Noir", 5: "Blush Peony"}
    
    def _qr_cell(num):
        return f"""<td width="33%" align="center" valign="top" style="padding:0 6px 16px;">
<a href="{selects[num]}" target="_blank" style="text-decoration:none;display:block;">
<img src="{previews[num]}" alt="{design_labels[num]}" style="width:100%;max-width:170px;border-radius:6px;border:2px solid #E8E4DC;" />
<p style="font-size:12px;color:#D4AF37;margin:8px 0 2px;font-weight:bold;text-transform:uppercase;letter-spacing:1px;">{design_labels[num]}</p>
<p style="font-size:11px;color:#A8A29E;margin:0;">Click to select</p>
</a>
</td>"""
    
    email_content = f"""
<p style="font-size:22px;color:#1C1917;font-family:Georgia,'Times New Roman',serif;margin:0 0 8px 0;font-weight:normal;">
Hi {couple_name},
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 20px 0;line-height:1.8;">
Your guest upload link is ready! Now it's time to choose your QR code design. Pick your favourite below and we'll send you a print-ready PDF straight to your inbox.
</p>

<table width="100%" cellpadding="0" cellspacing="0" style="margin:20px 0;">
<tr>
{_qr_cell(1)}
{_qr_cell(2)}
{_qr_cell(3)}
</tr>
<tr>
<td width="33%"></td>
{_qr_cell(4)}
{_qr_cell(5)}
</tr>
</table>

<div style="text-align:center;margin:16px 0 0;padding:16px 0 0;border-top:1px solid #F5F2EB;">
<p style="font-size:13px;color:#A8A29E;line-height:1.6;margin:0;">
Simply click on your favourite design above and the print-ready PDF will be emailed to you automatically. Easy!
</p>
</div>
"""
    
    html_content = build_branded_email(email_content, awards_url)
    
    try:
        send_smtp_email(smtp, client_email, f"Choose Your QR Code Design — {couple_name}", html_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send email: {str(e)}")
    
    # Log
    await db.email_log.insert_one({
        "type": "qr_picker",
        "gallery_id": gallery_id,
        "gallery_name": couple_name,
        "recipient": client_email,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"success": True, "message": f"QR picker email sent to {client_email}"}



# ─── Slideshow Music ───
MUSIC_DIR = Path(__file__).parent / "assets" / "slideshow_music"

@api_router.get("/slideshow/music/{filename}")
async def serve_slideshow_music(filename: str, request: Request):
    safe_name = require_safe_component(filename, "music filename")
    try:
        file_path = contained_path(MUSIC_DIR, safe_name, labels=("music filename",))
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.exists() or not safe_name.endswith('.mp3'):
        raise HTTPException(status_code=404, detail="Track not found")
    file_size = file_path.stat().st_size
    range_header = request.headers.get("range")
    if range_header:
        range_val = range_header.strip().split("=")[-1]
        parts = range_val.split("-")
        start = int(parts[0])
        end = int(parts[1]) if parts[1] else min(start + 1024 * 1024, file_size - 1)
        end = min(end, file_size - 1)
        length = end - start + 1
        def iter_range():
            with open(file_path, "rb") as fh:
                fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = fh.read(min(65536, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk
        return StreamingResponse(iter_range(), status_code=206, media_type="audio/mpeg", headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes", "Content-Length": str(length),
        })
    return FileResponse(file_path, media_type="audio/mpeg", headers={"Accept-Ranges": "bytes"})

# ─── Media Serving ───
@api_router.get("/media/thumb/{gallery_id}/{subfolder_slug}/{filename}")
async def serve_thumb(gallery_id: str, subfolder_slug: str, filename: str):
    try:
        file_path = contained_path(
            CACHE_DIR,
            gallery_id,
            subfolder_slug,
            filename,
            labels=("gallery id", "subfolder cache key", "thumbnail filename"),
        )
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(file_path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=2592000, immutable"})

@api_router.get("/media/preview/{gallery_id}/{subfolder_slug}/{filename}")
async def serve_preview(gallery_id: str, subfolder_slug: str, filename: str):
    try:
        file_path = contained_path(
            CACHE_DIR,
            gallery_id,
            subfolder_slug,
            filename,
            labels=("gallery id", "subfolder cache key", "preview filename"),
        )
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(file_path, media_type="image/jpeg", headers={"Cache-Control": "public, max-age=2592000, immutable"})

@api_router.get("/media/original/{gallery_id}/{subfolder}/{filename}")
async def serve_original(
    gallery_id: str,
    subfolder: str,
    filename: str,
    authorization: str = Header(None),
    t: str = Query(None),
):
    auth_token = t
    if authorization:
        auth_token = authorization.replace("Bearer ", "")
    if not auth_token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_jwt(auth_token)
    if payload.get("role") == "share":
        payload = await validate_live_share_session(payload)
        if payload.get("gallery_id") != gallery_id:
            raise HTTPException(status_code=403, detail="Access denied")
        if payload.get("subfolder") and payload.get("subfolder") != subfolder:
            raise HTTPException(status_code=403, detail="Access denied")
    elif payload.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Access denied")

    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    file_doc = await db.files.find_one(
        {"gallery_id": gallery_id, "subfolder": subfolder, "filename": filename},
        {"_id": 0, "id": 1},
    )
    if not file_doc:
        raise HTTPException(status_code=404, detail="File not found")
    file_path = get_gallery_file_path(gallery["folder_name"], subfolder, filename)
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

# ─── Public Email Assets ───
EMAIL_ASSETS_DIR = Path(__file__).parent / "assets"

@api_router.get("/public/email-assets/{filename}")
async def get_email_asset(filename: str):
    """Serve email assets (like awards badges) publicly for email clients."""
    try:
        file_path = contained_path(EMAIL_ASSETS_DIR, filename, labels=("email asset filename",))
    except UnsafePathError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Asset not found")
    return FileResponse(file_path, media_type="image/png", headers={"Cache-Control": "public, max-age=31536000"})

# ─── Public Share Access ───
@api_router.get("/share/{token}")
async def get_share_info(token: str):
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    if is_share_expired(share):
        raise HTTPException(status_code=410, detail="This share link has expired")
    gallery = await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    # Get a cover image
    query = {"gallery_id": share["gallery_id"], "file_type": "photo"}
    if share.get("subfolder"):
        query["subfolder"] = share["subfolder"]
    first_file = await db.files.find_one(query, {"_id": 0})
    cover_url = None
    if first_file and first_file.get("has_preview"):
        cover_url = f"/api/media/preview/{gallery['id']}/{slugify(first_file['subfolder'])}/{Path(first_file['filename']).stem}.preview.jpg"

    file_count = await db.files.count_documents(query)

    return {
        "gallery_name": gallery["folder_name"],
        "label": share.get("label", gallery["folder_name"]),
        "subfolder": share.get("subfolder"),
        "has_password": share.get("has_password", False),
        "access_level": share.get("access_level", "download"),
        "allow_uploads": share.get("allow_uploads", False),
        "guest_upload_mode": share.get("guest_upload_mode", False),
        "allow_all_file_types": share.get("allow_all_file_types", False),
        "expires_at": share.get("expires_at"),
        "cover_url": cover_url,
        "file_count": file_count
    }

@api_router.post("/share/{token}/access")
async def access_share(token: str, body: ShareAccessBody = None):
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    if is_share_expired(share):
        raise HTTPException(status_code=410, detail="This share link has expired")

    if share.get("has_password") and share.get("password_hash"):
        if not body or not body.password:
            raise HTTPException(status_code=401, detail="Password required")
        if not bcrypt.checkpw(body.password.encode(), share["password_hash"].encode()):
            raise HTTPException(status_code=401, detail="Invalid password")

    # Use provided viewer_id or generate new one (for persistent favourites)
    session_id = body.viewer_id if body and body.viewer_id else str(uuid.uuid4())
    
    access_level = share.get("access_level", "download")
    jwt_token = create_jwt({
        "sub": session_id,
        "role": "share",
        "share_id": share["id"],
        "gallery_id": share["gallery_id"],
        "subfolder": share.get("subfolder"),
        "access_level": access_level,
        "allow_uploads": access_level in ("upload", "full"),
        "allow_downloads": access_level in ("download", "upload", "full"),
        "allow_delete": access_level == "full",
        "token": token
    }, expires_hours=72)
    gallery = await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0})
    return {"jwt": jwt_token, "viewer_id": session_id, "gallery_name": gallery["folder_name"] if gallery else ""}

@api_router.get("/share/{token}/open-access")
async def open_access_share(token: str, viewer_id: str = Query(None)):
    """For shares without password - get JWT directly."""
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    if is_share_expired(share):
        raise HTTPException(status_code=410, detail="This share link has expired")
    if share.get("has_password"):
        raise HTTPException(status_code=401, detail="Password required")
    
    # Use provided viewer_id or generate new one (for persistent favourites)
    session_id = viewer_id if viewer_id else str(uuid.uuid4())
    
    access_level = share.get("access_level", "download")
    jwt_token = create_jwt({
        "sub": session_id,
        "role": "share",
        "share_id": share["id"],
        "gallery_id": share["gallery_id"],
        "subfolder": share.get("subfolder"),
        "access_level": access_level,
        "allow_uploads": access_level in ("upload", "full"),
        "allow_downloads": access_level in ("download", "upload", "full"),
        "allow_delete": access_level == "full",
        "token": token
    }, expires_hours=72)
    gallery = await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0})
    return {"jwt": jwt_token, "viewer_id": session_id, "gallery_name": gallery["folder_name"] if gallery else ""}

@api_router.get("/share/{token}/files")
async def get_share_files(token: str, session=Depends(get_share_session)):
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    gallery_id = session["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    subfolder = session.get("subfolder")
    if subfolder:
        files = await db.files.find({"gallery_id": gallery_id, "subfolder": subfolder}, {"_id": 0}).sort("uploaded_at", 1).to_list(50000)
        subfolders_data = [{
            "name": subfolder,
            "files": files
        }]
    else:
        # Single query for ALL files, then group by subfolder
        all_files = await db.files.find({"gallery_id": gallery_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(50000)
        files_by_sf = {}
        for f in all_files:
            files_by_sf.setdefault(f["subfolder"], []).append(f)
        subfolders_data = [{"name": sf, "files": files_by_sf.get(sf, [])} for sf in gallery["subfolders"]]

    # Get favourites
    favs = await db.favourites.find({"session_id": session["sub"], "gallery_id": gallery_id}, {"_id": 0}).to_list(50000)
    fav_ids = {f["file_id"] for f in favs}

    for sf_data in subfolders_data:
        for f in sf_data["files"]:
            f["is_favourite"] = f["id"] in fav_ids

    # Get share doc for additional flags
    share = await db.shares.find_one({"token": token}, {"_id": 0})

    return {
        "gallery_id": gallery_id,
        "gallery_name": gallery["folder_name"],
        "theme": gallery.get("theme", "classic_gold"),
        "subfolders": subfolders_data,
        "covers": gallery.get("covers", {}),
        "access_level": session.get("access_level", "download"),
        "allow_uploads": session.get("allow_uploads", False),
        "allow_downloads": session.get("allow_downloads", True),
        "allow_delete": session.get("allow_delete", False),
        "allow_all_file_types": share.get("allow_all_file_types", False) if share else False
    }

@api_router.post("/share/{token}/favourite")
async def toggle_share_favourite(token: str, data: FavouriteToggle, session=Depends(get_share_session)):
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    visible_file = await db.files.find_one(share_file_query(session, id=data.file_id), {"_id": 0, "id": 1})
    if not visible_file:
        raise HTTPException(status_code=404, detail="File not found")
    existing = await db.favourites.find_one({
        "session_id": session["sub"],
        "file_id": data.file_id,
        "gallery_id": session["gallery_id"]
    })
    if existing:
        await db.favourites.delete_one({"_id": existing["_id"]})
        return {"favourited": False}
    await db.favourites.insert_one({
        "id": str(uuid.uuid4()),
        "session_id": session["sub"],
        "file_id": data.file_id,
        "gallery_id": session["gallery_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    })
    return {"favourited": True}

@api_router.post("/share/{token}/submit-favourites")
async def submit_favourites_to_album(token: str, request: Request, session=Depends(get_share_session)):
    """Copy all favourited files to Album Favourites folder."""
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    
    # Get client IP
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    gallery_id = session["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    # Get all favourites for this session
    favs = await db.favourites.find({
        "session_id": session["sub"],
        "gallery_id": gallery_id
    }, {"_id": 0}).to_list(50000)
    
    if not favs:
        raise HTTPException(status_code=400, detail="No favourites selected")
    
    # Ensure Album Favourites folder exists
    target_subfolder = "Album Favourites"
    if target_subfolder not in gallery["subfolders"]:
        gallery["subfolders"].append(target_subfolder)
        await db.galleries.update_one(
            {"id": gallery_id},
            {"$set": {"subfolders": gallery["subfolders"]}}
        )
    
    target_dir = get_gallery_subfolder_path(gallery["folder_name"], target_subfolder)
    target_dir.mkdir(parents=True, exist_ok=True)
    
    copied = 0
    already_exists = 0
    
    for fav in favs:
        f = await db.files.find_one(share_file_query(session, id=fav["file_id"]), {"_id": 0})
        if not f:
            continue
        
        # Check if file already exists in Album Favourites
        existing = await db.files.find_one({
            "gallery_id": gallery_id,
            "subfolder": target_subfolder,
            "original_filename": f["original_filename"]
        })
        if existing:
            already_exists += 1
            continue
        
        src_path = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
        if not src_path.exists():
            continue
        
        dest_name = safe_filename(f["filename"], target_dir)
        dest_path = get_gallery_file_path(gallery["folder_name"], target_subfolder, dest_name)
        shutil.copy2(src_path, dest_path)
        
        # Generate thumbnails for the copy
        has_thumb = False
        has_preview = False
        if f["file_type"] == "photo":
            has_thumb = make_thumbnail(dest_path, get_thumb_path(gallery_id, target_subfolder, dest_name))
            has_preview = make_preview(dest_path, get_preview_path(gallery_id, target_subfolder, dest_name))
        
        new_doc = {
            "id": str(uuid.uuid4()),
            "gallery_id": gallery_id,
            "subfolder": target_subfolder,
            "filename": dest_name,
            "original_filename": f["original_filename"],
            "file_type": f["file_type"],
            "file_size": f["file_size"],
            "has_thumb": has_thumb,
            "has_preview": has_preview,
            "uploaded_by": "client_favourite",
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        await db.files.insert_one(new_doc)
        copied += 1
    
    # Update file count
    count = await db.files.count_documents({"gallery_id": gallery_id, "subfolder": target_subfolder})
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {f"file_counts.{target_subfolder}": count, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    
    # Log the activity
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    await db.activity_log.insert_one({
        "id": str(uuid.uuid4()),
        "gallery_id": gallery_id,
        "gallery_name": gallery.get("folder_name", "Unknown"),
        "share_label": share.get("label", token) if share else token,
        "action": "favourites_submitted",
        "details": f"{copied} photos submitted for album",
        "ip_address": client_ip,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"copied": copied, "already_existed": already_exists, "total_favourites": len(favs)}


@api_router.post("/share/{token}/choose-album-cover")
async def choose_album_cover(token: str, request: Request, session=Depends(get_share_session)):
    """Couple selects their preferred album cover from Album Favourites."""
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    
    body = await request.json()
    file_id = body.get("file_id")
    if not file_id:
        raise HTTPException(status_code=400, detail="No file selected")
    
    gallery_id = session["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    # Verify the file exists in Album Favourites
    file_doc = await db.files.find_one({
        "id": file_id, "gallery_id": gallery_id, "subfolder": "Album Favourites"
    }, {"_id": 0})
    if not file_doc:
        raise HTTPException(status_code=404, detail="Photo not found in Album Favourites")
    
    filename = file_doc.get("original_filename") or file_doc["filename"]
    
    # Save the choice on the gallery
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {
            "album_cover_choice": {
                "file_id": file_id,
                "filename": file_doc["filename"],
                "original_filename": filename,
                "chosen_at": datetime.now(timezone.utc).isoformat()
            }
        }}
    )
    
    # Log activity
    import re
    folder_name = gallery["folder_name"]
    couple_name = re.sub(r'\s*\d{1,2}[./]\d{1,2}[./]\d{2,4}\s*$', '', folder_name).strip() or folder_name
    
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    await db.activity_log.insert_one({
        "id": str(uuid.uuid4()),
        "gallery_id": gallery_id,
        "gallery_name": folder_name,
        "share_label": share.get("label", token) if share else token,
        "action": "album_cover_chosen",
        "details": f"{couple_name} chose {filename} as their album cover",
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    # Email the admin
    try:
        smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
        if smtp_doc and smtp_doc.get("value", {}).get("smtp_email"):
            smtp = smtp_doc["value"]
            admin_email = smtp.get("smtp_email", "")
            site_url = smtp.get("site_url", "").rstrip("/")
            awards_url = get_awards_url(smtp)
            
            # Build thumbnail URL for the email
            thumb_link = f"{site_url}/api/share/{token}/files/{file_id}/thumb" if site_url else ""
            
            email_html = build_branded_email(f"""
<p style="font-size:22px;color:#1C1917;font-family:Georgia,'Times New Roman',serif;margin:0 0 8px 0;font-weight:normal;">
Album Cover Selected!
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 20px 0;line-height:1.8;">
<strong>{couple_name}</strong> has chosen their album cover image:
</p>
<div style="text-align:center;margin:20px 0;">
<p style="font-size:18px;color:#1C1917;font-weight:bold;margin:0 0 12px 0;font-family:Georgia,serif;">
{filename}
</p>
{f'<img src="{thumb_link}" alt="{filename}" style="max-width:400px;width:100%;border-radius:4px;border:2px solid #E8E4DC;" />' if thumb_link else ''}
</div>
<p style="font-size:14px;color:#A8A29E;margin:20px 0 0 0;">
Gallery: {folder_name}
</p>
""", awards_url)
            
            send_smtp_email(smtp, admin_email, f"Album Cover Chosen — {couple_name}", email_html)
    except Exception as e:
        logger.warning(f"Failed to send album cover notification email: {e}")
    
    return {"success": True, "message": "Cover choice saved!", "filename": filename}


@api_router.get("/share/{token}/album-cover-choice")
async def get_album_cover_choice(token: str, session=Depends(get_share_session)):
    """Get the current album cover choice for this gallery."""
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    
    gallery = await db.galleries.find_one({"id": session["gallery_id"]}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    choice = gallery.get("album_cover_choice")
    return {"choice": choice}



async def _log_download(gallery_id, gallery_name, share_label, client_ip,
                        download_type, filenames, subfolder, downloaded_count, total_in_scope):
    """Log a detailed download event to activity_log.
    download_type: 'single', 'selection', 'album', 'favourites'
    """
    if downloaded_count >= total_in_scope and total_in_scope > 1:
        completeness = "full"
    elif downloaded_count == 1:
        completeness = "single"
    else:
        completeness = "partial"

    if download_type == "single":
        details = f"Downloaded 1 file: {filenames[0]}"
    elif download_type == "favourites":
        details = f"Downloaded {downloaded_count} favourites as ZIP"
    else:
        scope = f" from {subfolder}" if subfolder else " (full gallery)"
        details = f"Downloaded {downloaded_count}/{total_in_scope} files{scope}"

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.activity.update_one(
        {"gallery_id": gallery_id, "date": today},
        {"$inc": {"downloads": 1}},
        upsert=True
    )
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$inc": {"total_downloads": 1}}
    )
    await db.activity_log.insert_one({
        "id": str(uuid.uuid4()),
        "gallery_id": gallery_id,
        "gallery_name": gallery_name,
        "share_label": share_label,
        "action": "download",
        "download_type": download_type,
        "completeness": completeness,
        "details": details,
        "files_downloaded": filenames[:50],  # Cap at 50 to avoid huge docs
        "files_count": downloaded_count,
        "total_available": total_in_scope,
        "subfolder": subfolder,
        "ip_address": client_ip,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })


@api_router.get("/share/{token}/video-token/{file_id}")
async def get_video_playback_token(token: str, file_id: str, t: str = Query(None)):
    """Generate a short-lived playback token with file path baked in — no DB lookups during streaming."""
    if not t:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_jwt(t)
    payload = await validate_live_share_session(payload, expected_token=token)
    f = await db.files.find_one(share_file_query(payload, id=file_id), {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    gallery = await db.galleries.find_one({"id": payload["gallery_id"]}, {"_id": 0})
    file_path = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Check for web-optimised version (smaller, smoother streaming)
    web_path = get_web_version_path(file_path)
    stream_filename = web_path.name if web_path.exists() else f["filename"]
    
    # If nginx video server is configured, use it (zero Python involvement in streaming)
    if NGINX_VIDEO_URL:
        url = generate_nginx_video_url(gallery["folder_name"], f["subfolder"], stream_filename)
        # Log estimated video bandwidth (file size of streamed version)
        stream_path = web_path if web_path.exists() else file_path
        await log_bandwidth_event("video_stream", stream_path.stat().st_size if stream_path.exists() else 0, f["filename"])
        return {"url": url, "mode": "nginx"}
    
    # Fallback: Python streaming with JWT token (zero DB calls during playback)
    stream_path = web_path if web_path.exists() else file_path
    await log_bandwidth_event("video_stream", stream_path.stat().st_size if stream_path.exists() else 0, f["filename"])
    vtoken = create_jwt({"role": "video", "path": str(stream_path)}, expires_hours=2)
    return {"url": f"/api/v/{vtoken}", "mode": "direct"}

@api_router.get("/v/{vtoken}")
async def stream_video_direct(vtoken: str, request: Request):
    """Ultra-lightweight video streaming — JWT contains file path, zero DB calls."""
    payload = verify_jwt(vtoken)
    if payload.get("role") != "video":
        raise HTTPException(status_code=403, detail="Invalid video token")
    file_path = Path(payload["path"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    file_size = file_path.stat().st_size
    ext = file_path.suffix.lower()
    content_types = {'.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm',
                     '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska', '.mts': 'video/mp2t'}
    content_type = content_types.get(ext, 'video/mp4')
    CHUNK_SIZE = 1024 * 1024  # 1MB chunks for large files

    range_header = request.headers.get("range")
    if range_header:
        range_val = range_header.strip().split("=")[-1]
        range_parts = range_val.split("-")
        start = int(range_parts[0])
        end = int(range_parts[1]) if range_parts[1] else min(start + 10 * 1024 * 1024, file_size - 1)
        end = min(end, file_size - 1)
        length = end - start + 1

        async def async_iter_range():
            async with aiofiles.open(file_path, "rb") as fh:
                await fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = await fh.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(async_iter_range(), status_code=206, media_type=content_type, headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Cache-Control": "public, max-age=86400",
        })
    else:
        return FileResponse(file_path, media_type=content_type, headers={
            "Accept-Ranges": "bytes",
            "Content-Length": str(file_size),
            "Cache-Control": "public, max-age=86400",
        })

@api_router.get("/share/{token}/stream/{file_id}")
async def stream_share_video(token: str, file_id: str, request: Request, t: str = Query(None)):
    """Stream a video file with async range request support for smooth in-browser playback."""
    if not t:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_jwt(t)
    payload = await validate_live_share_session(payload, expected_token=token)
    f = await db.files.find_one(share_file_query(payload, id=file_id), {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    gallery = await db.galleries.find_one({"id": payload["gallery_id"]}, {"_id": 0})
    file_path = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")

    # Prefer web-optimised version for smoother streaming on mobile
    web_path = get_web_version_path(file_path)
    stream_path = web_path if web_path.exists() else file_path

    file_size = stream_path.stat().st_size
    ext = stream_path.suffix.lower()
    content_types = {'.mp4': 'video/mp4', '.mov': 'video/quicktime', '.webm': 'video/webm',
                     '.avi': 'video/x-msvideo', '.mkv': 'video/x-matroska', '.mts': 'video/mp2t'}
    content_type = content_types.get(ext, 'video/mp4')
    CHUNK_SIZE = 512 * 1024  # 512KB chunks for smooth streaming

    range_header = request.headers.get("range")
    if range_header:
        range_val = range_header.strip().split("=")[-1]
        range_parts = range_val.split("-")
        start = int(range_parts[0])
        end = int(range_parts[1]) if range_parts[1] else min(start + 10 * 1024 * 1024, file_size - 1)
        end = min(end, file_size - 1)
        length = end - start + 1

        async def async_iter_range():
            async with aiofiles.open(stream_path, "rb") as fh:
                await fh.seek(start)
                remaining = length
                while remaining > 0:
                    chunk = await fh.read(min(CHUNK_SIZE, remaining))
                    if not chunk:
                        break
                    remaining -= len(chunk)
                    yield chunk

        return StreamingResponse(async_iter_range(), status_code=206, media_type=content_type, headers={
            "Content-Range": f"bytes {start}-{end}/{file_size}",
            "Accept-Ranges": "bytes",
            "Content-Length": str(length),
            "Cache-Control": "public, max-age=86400",
        })
    else:
        return FileResponse(stream_path, media_type=content_type, headers={
            "Accept-Ranges": "bytes",
            "Cache-Control": "public, max-age=86400",
        })

@api_router.get("/share/{token}/download/{file_id}")
async def download_share_file(token: str, file_id: str, request: Request, session=Depends(get_share_session)):
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    # Enforce download permission
    if not session.get("allow_downloads", False):
        raise HTTPException(status_code=403, detail="Downloads not allowed on this share")
    f = await db.files.find_one(share_file_query(session, id=file_id), {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    gallery = await db.galleries.find_one({"id": session["gallery_id"]}, {"_id": 0})
    file_path = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
    if not file_path.exists():
        # Enhanced diagnostic: show what IS on disk
        parent = file_path.parent
        parent_exists = parent.exists()
        parent_contents = []
        if parent_exists:
            try:
                parent_contents = [x.name for x in parent.iterdir()][:10]
            except Exception:
                pass
        logger.error(f"Download single: file not on disk: {file_path} | UPLOAD_DIR={UPLOAD_DIR} | gallery='{gallery['folder_name']}' | subfolder='{f['subfolder']}' | file='{f['filename']}' | parent_exists={parent_exists} | parent_contents={parent_contents}")
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Log detailed download
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    await _log_download(session["gallery_id"], gallery.get("folder_name", "Unknown"),
                        share.get("label", token) if share else token, client_ip,
                        "single", [f["filename"]], f["subfolder"], 1, 1)
    
    # Track download bandwidth
    await log_bandwidth_event("file_download", file_path.stat().st_size if file_path.exists() else f.get("file_size", 0), f["filename"])
    
    return FileResponse(file_path, filename=f["filename"], media_type="application/octet-stream")

@api_router.post("/share/{token}/download-zip")
async def download_share_zip(token: str, request: Request, file_ids: List[str] = [], session=Depends(get_share_session)):
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    if not session.get("allow_downloads", False):
        raise HTTPException(status_code=403, detail="Downloads not allowed on this share")
    gallery_id = session["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    subfolder = session.get("subfolder")
    if file_ids:
        query = share_file_query(session, id={"$in": file_ids})
    else:
        query = share_file_query(session)
    files = await db.files.find(query, {"_id": 0}).to_list(50000)
    
    if not files:
        raise HTTPException(status_code=404, detail="No files to download")

    # Count total available files for completeness tracking
    total_query = {"gallery_id": gallery_id}
    if subfolder:
        total_query["subfolder"] = subfolder
    total_available = await db.files.count_documents(total_query)

    # Log detailed download
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    dl_type = "selection" if file_ids else "album"
    sub = files[0]["subfolder"] if files else subfolder
    await _log_download(gallery_id, gallery.get("folder_name", "Unknown"),
                        share.get("label", token) if share else token, client_ip,
                        dl_type, [f["filename"] for f in files], sub,
                        len(files), total_available)
    
    if not files:
        raise HTTPException(status_code=404, detail="No files to download")

    # Use ZIP_STORED for speed (same as admin panel)
    gallery_path = get_gallery_path(gallery["folder_name"])
    logger.info(f"Download ZIP (POST): gallery='{gallery['folder_name']}', gallery_path={gallery_path}, exists={gallery_path.exists()}, file_count={len(files)}")

    def iter_zip():
        buf = io.BytesIO()
        added = 0
        missing = []
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for f in files:
                fp = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
                if fp.exists():
                    arcname = f"{f['subfolder']}/{f['filename']}"
                    zf.write(fp, arcname)
                    added += 1
                else:
                    missing.append(f"{f['subfolder']}/{f['filename']}")
        if missing:
            logger.error(f"Download ZIP: {len(missing)}/{len(files)} files NOT found. First 5: {missing[:5]}")
            try:
                gp = get_gallery_path(gallery["folder_name"])
                if gp.exists():
                    for sd in gp.iterdir():
                        if sd.is_dir():
                            contents = list(sd.iterdir())[:5]
                            logger.error(f"  Subfolder '{sd.name}': {len(list(sd.iterdir()))} files, first 5: {[x.name for x in contents]}")
                else:
                    logger.error(f"  Gallery dir does NOT exist: {gp}")
            except Exception as e:
                logger.error(f"  Could not list gallery dir: {e}")
        logger.info(f"Download ZIP: added {added}/{len(files)} files to archive")
        buf.seek(0)
        while True:
            chunk = buf.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            yield chunk

    # Track download bandwidth (sum of all file sizes)
    total_dl_bytes = sum(f.get("file_size", 0) for f in files)
    await log_bandwidth_event("file_download", total_dl_bytes, f"ZIP: {len(files)} files")

    zip_name = f"{gallery['folder_name'].replace(' ', '_')}.zip"
    return StreamingResponse(
        iter_zip(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_name}"',
            "Cache-Control": "no-cache"
        }
    )

# Direct GET endpoint for share ZIP download (better browser support)
@api_router.get("/share/{token}/download-album")
async def download_share_album_direct(token: str, request: Request, subfolder: str = Query(None), jwt_token: str = Query(..., alias="t")):
    # Verify JWT from query param
    payload = await validate_live_share_session(verify_jwt(jwt_token), expected_token=token)
    if not payload.get("allow_downloads", False):
        raise HTTPException(status_code=403, detail="Downloads not allowed")
    
    gallery_id = payload["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    share_subfolder = payload.get("subfolder")
    if share_subfolder and subfolder and subfolder != share_subfolder:
        raise HTTPException(status_code=403, detail="Access denied")
    effective_subfolder = share_subfolder or subfolder
    query = share_file_query(payload)
    if effective_subfolder:
        query["subfolder"] = effective_subfolder
    files = await db.files.find(query, {"_id": 0}).to_list(50000)
    
    if not files:
        raise HTTPException(status_code=404, detail="No files to download")

    # Log detailed download
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    total_available = len(files)
    await _log_download(gallery_id, gallery.get("folder_name", "Unknown"),
                        share.get("label", token) if share else token, client_ip,
                        "album", [f["filename"] for f in files], subfolder,
                        len(files), total_available)

    gallery_path = get_gallery_path(gallery["folder_name"])
    logger.info(f"Download album: gallery='{gallery['folder_name']}', UPLOAD_DIR={UPLOAD_DIR}, gallery_path={gallery_path}, exists={gallery_path.exists()}, file_count={len(files)}")

    def iter_zip():
        buf = io.BytesIO()
        added = 0
        missing = []
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for f in files:
                fp = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
                if fp.exists():
                    arcname = f["filename"] if subfolder else f"{f['subfolder']}/{f['filename']}"
                    zf.write(fp, arcname)
                    added += 1
                else:
                    missing.append(str(fp))
        if missing:
            logger.error(f"Download album ZIP: {len(missing)}/{len(files)} files NOT found on disk. First 5 missing: {missing[:5]}")
            # Also log what IS on disk at the gallery path for debugging
            try:
                gp = get_gallery_path(gallery["folder_name"])
                if gp.exists():
                    disk_contents = list(gp.iterdir())[:10]
                    logger.error(f"  Gallery dir contents (first 10): {[str(x.name) for x in disk_contents]}")
                else:
                    logger.error(f"  Gallery dir does NOT exist: {gp}")
            except Exception as e:
                logger.error(f"  Could not list gallery dir: {e}")
        logger.info(f"Download album ZIP: added {added}/{len(files)} files to archive")
        buf.seek(0)
        while True:
            chunk = buf.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    folder_name = subfolder if subfolder else gallery['folder_name']
    zip_name = f"{folder_name.replace(' ', '_')}.zip"

    # Track download bandwidth
    total_dl_bytes = sum(f.get("file_size", 0) for f in files)
    await log_bandwidth_event("file_download", total_dl_bytes, f"Album ZIP: {len(files)} files")

    return StreamingResponse(
        iter_zip(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_name}"',
            "Cache-Control": "no-cache"
        }
    )

# Direct GET endpoint for downloading favourites
@api_router.get("/share/{token}/download-favourites")
async def download_share_favourites_direct(token: str, request: Request, jwt_token: str = Query(..., alias="t")):
    # Verify JWT from query param
    payload = await validate_live_share_session(verify_jwt(jwt_token), expected_token=token)
    if not payload.get("allow_downloads", False):
        raise HTTPException(status_code=403, detail="Downloads not allowed")
    
    gallery_id = payload["gallery_id"]
    session_id = payload["sub"]
    
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    # Get all favourites for this session
    favs = await db.favourites.find({
        "session_id": session_id,
        "gallery_id": gallery_id
    }, {"_id": 0}).to_list(50000)
    
    if not favs:
        raise HTTPException(status_code=404, detail="No favourites to download")
    
    fav_ids = [f["file_id"] for f in favs]
    files = await db.files.find(share_file_query(payload, id={"$in": fav_ids}), {"_id": 0}).to_list(50000)
    
    if not files:
        raise HTTPException(status_code=404, detail="No files found")

    # Log detailed download
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    await _log_download(gallery_id, gallery.get("folder_name", "Unknown"),
                        share.get("label", token) if share else token, client_ip,
                        "favourites", [f["filename"] for f in files], "Favourites",
                        len(files), len(files))

    def iter_zip():
        buf = io.BytesIO()
        added = 0
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for f in files:
                fp = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
                if fp.exists():
                    zf.write(fp, f["filename"])
                    added += 1
                else:
                    logger.error(f"Favourites ZIP: file not found: {fp}")
        if added == 0:
            logger.error(f"Favourites ZIP: 0 files found. Gallery='{gallery['folder_name']}', UPLOAD_DIR={UPLOAD_DIR}")
        logger.info(f"Favourites ZIP: added {added}/{len(files)} files")
        buf.seek(0)
        while True:
            chunk = buf.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    zip_name = f"{gallery['folder_name'].replace(' ', '_')}_favourites.zip"

    # Track download bandwidth
    total_dl_bytes = sum(f.get("file_size", 0) for f in files)
    await log_bandwidth_event("file_download", total_dl_bytes, f"Favourites ZIP: {len(files)} files")

    return StreamingResponse(
        iter_zip(),
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{zip_name}"',
            "Cache-Control": "no-cache"
        }
    )

# ─── Guest Upload (via share) ───
@api_router.post("/share/{token}/upload")
async def guest_upload(
    token: str,
    files: List[UploadFile] = File(...),
    session=Depends(get_share_session)
):
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    if not session.get("allow_uploads"):
        raise HTTPException(status_code=403, detail="Uploads not allowed on this share")

    gallery_id = session["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    # Check if this share allows all file types (photographer mode)
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    is_photographer_mode = share.get("allow_all_file_types", False) if share else False

    subfolder = session.get("subfolder") or "Guest Uploads"
    target_dir = get_gallery_file_path(gallery["folder_name"], subfolder, ".upload-target").parent
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Only check compression setting for non-photographer uploads
    compression_enabled = False if is_photographer_mode else await get_compression_setting()

    uploaded = []
    skipped_too_large = []
    for file in files:
        if is_photographer_mode:
            # PHOTOGRAPHER MODE: Stream directly to disk, preserve original filename, no size limit
            final_name = safe_filename(file.filename, target_dir)
            file_path = get_gallery_file_path(gallery["folder_name"], subfolder, final_name)

            # Stream directly to disk in chunks - no memory buffering
            file_size = 0
            async with aiofiles.open(file_path, 'wb') as f_out:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    await f_out.write(chunk)
                    file_size += len(chunk)

            file_type = "photo" if is_image(final_name) else "video" if is_video(final_name) else "other"
            
            # Generate thumbnails in background for photos (non-blocking)
            has_thumb = False
            has_preview = False
            file_doc = {
                "id": str(uuid.uuid4()),
                "gallery_id": gallery_id,
                "subfolder": subfolder,
                "filename": final_name,
                "original_filename": file.filename,
                "file_type": file_type,
                "file_size": file_size,
                "has_thumb": has_thumb,
                "has_preview": has_preview,
                "uploaded_by": "photographer",
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            }
            await db.files.insert_one(file_doc)
            
            # Queue thumbnail generation in background (non-blocking)
            if file_type == "photo":
                thumbnail_executor.submit(
                    generate_thumbnails_background,
                    file_path, gallery_id, subfolder, final_name, file_type, file_doc["id"]
                )
            
            uploaded.append({k: v for k, v in file_doc.items() if k != "_id"})
        else:
            # GUEST MODE: stream to a temporary file so large uploads do not fill RAM.
            final_name = safe_filename(file.filename, target_dir)
            file_path = get_gallery_file_path(gallery["folder_name"], subfolder, final_name)
            temp_path = file_path.with_name(f".{file_path.name}.{uuid.uuid4().hex}.partial")
            file_size = 0
            too_large = False
            try:
                async with aiofiles.open(temp_path, 'wb') as f_out:
                    while True:
                        chunk = await file.read(1024 * 1024)
                        if not chunk:
                            break
                        file_size += len(chunk)
                        if file_size > MAX_GUEST_UPLOAD_SIZE:
                            too_large = True
                            break
                        await f_out.write(chunk)
                if too_large:
                    temp_path.unlink(missing_ok=True)
                    skipped_too_large.append(file.filename)
                    continue
                temp_path.replace(file_path)
            except Exception:
                temp_path.unlink(missing_ok=True)
                raise

            file_type = "photo" if is_image(final_name) else "video" if is_video(final_name) else "other"
            has_thumb = False
            has_preview = False
            if file_type == "photo":
                has_thumb = make_thumbnail(file_path, get_thumb_path(gallery_id, subfolder, final_name))
                has_preview = make_preview(file_path, get_preview_path(gallery_id, subfolder, final_name))

            file_doc = {
                "id": str(uuid.uuid4()),
                "gallery_id": gallery_id,
                "subfolder": subfolder,
                "filename": final_name,
                "original_filename": file.filename,
                "file_type": file_type,
                "file_size": file_size,
                "has_thumb": has_thumb,
                "has_preview": has_preview,
                "uploaded_by": "guest",
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            }
            await db.files.insert_one(file_doc)
            uploaded.append({k: v for k, v in file_doc.items() if k != "_id"})
            
            # Schedule background compression for large guest videos if enabled
            if compression_enabled and file_type == "video" and file_size > VIDEO_COMPRESSION_SIZE_THRESHOLD:
                thumbnail_executor.submit(
                    compress_guest_video_background,
                    file_path,
                    file_doc["id"],
                    gallery_id
                )

    count = await db.files.count_documents({"gallery_id": gallery_id, "subfolder": subfolder})
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {f"file_counts.{subfolder}": count}}
    )
    
    # Ensure the subfolder is in the gallery's subfolders list (auto-add if created by upload)
    await db.galleries.update_one(
        {"id": gallery_id, "subfolders": {"$ne": subfolder}},
        {"$push": {"subfolders": subfolder}}
    )
    
    result = {"uploaded": uploaded, "count": len(uploaded)}
    if skipped_too_large:
        result["skipped"] = skipped_too_large
        result["message"] = f"{len(skipped_too_large)} file(s) exceeded 500MB limit and were not uploaded"
    return result

@api_router.get("/share/{token}/guest-upload-count")
async def get_guest_upload_count(token: str):
    """Get the count of files uploaded by guests (for live counter in Guest Upload Mode)."""
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    if is_share_expired(share):
        raise HTTPException(status_code=410, detail="This share link has expired")
    
    gallery_id = share["gallery_id"]
    subfolder = share.get("subfolder") or "Guest Uploads"
    
    # Count files uploaded by guests in this subfolder
    count = await db.files.count_documents({
        "gallery_id": gallery_id,
        "subfolder": subfolder,
        "uploaded_by": "guest"
    })
    
    return {"count": count}

# ─── Guest Delete (via share with full access) ───
class DeleteFilesRequest(BaseModel):
    file_ids: List[str]

@api_router.post("/share/{token}/delete")
async def guest_delete_files(token: str, data: DeleteFilesRequest, session=Depends(get_share_session)):
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    if not session.get("allow_delete", False):
        raise HTTPException(status_code=403, detail="Deleting not allowed on this share")
    
    gallery_id = session["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    deleted = 0
    affected_subfolders = set()
    
    for file_id in data.file_ids:
        f = await db.files.find_one(share_file_query(session, id=file_id), {"_id": 0})
        if not f:
            continue
        # Delete physical file
        file_path = get_gallery_file_path(gallery["folder_name"], f["subfolder"], f["filename"])
        if file_path.exists():
            file_path.unlink()
        # Delete thumbnails
        for tp in [get_thumb_path(gallery_id, f["subfolder"], f["filename"]),
                   get_preview_path(gallery_id, f["subfolder"], f["filename"])]:
            if tp.exists():
                tp.unlink()
        await db.files.delete_one({"id": file_id})
        await db.favourites.delete_many({"file_id": file_id})
        affected_subfolders.add(f["subfolder"])
        deleted += 1
    
    # Update file counts for affected subfolders
    for sf in affected_subfolders:
        count = await db.files.count_documents({"gallery_id": gallery_id, "subfolder": sf})
        await db.galleries.update_one(
            {"id": gallery_id},
            {"$set": {f"file_counts.{sf}": count}}
        )
    
    return {"deleted": deleted}

# ─── Print Shop Admin Endpoints ───
@api_router.get("/admin/print-sizes")
async def list_print_sizes(admin=Depends(get_admin)):
    sizes = await db.print_sizes.find({}, {"_id": 0}).sort("name", 1).to_list(100)
    return sizes

@api_router.post("/admin/print-sizes")
async def create_print_size(data: PrintSizeCreate, admin=Depends(get_admin)):
    # Check for duplicate
    existing = await db.print_sizes.find_one({"name": data.name}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Print size already exists")
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "prices": {
            "gloss": data.gloss_price,
            "luster": data.luster_price,
            "silk": data.silk_price
        },
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.print_sizes.insert_one(doc)
    return {k: v for k, v in doc.items() if k != "_id"}

@api_router.put("/admin/print-sizes/{size_id}")
async def update_print_size(size_id: str, data: PrintSizeUpdate, admin=Depends(get_admin)):
    size = await db.print_sizes.find_one({"id": size_id}, {"_id": 0})
    if not size:
        raise HTTPException(status_code=404, detail="Print size not found")
    update = {}
    if data.name is not None:
        update["name"] = data.name
    if data.gloss_price is not None:
        update["prices.gloss"] = data.gloss_price
    if data.luster_price is not None:
        update["prices.luster"] = data.luster_price
    if data.silk_price is not None:
        update["prices.silk"] = data.silk_price
    if update:
        await db.print_sizes.update_one({"id": size_id}, {"$set": update})
    updated = await db.print_sizes.find_one({"id": size_id}, {"_id": 0})
    return updated

@api_router.delete("/admin/print-sizes/{size_id}")
async def delete_print_size(size_id: str, admin=Depends(get_admin)):
    result = await db.print_sizes.delete_one({"id": size_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Print size not found")
    return {"deleted": True}

@api_router.get("/admin/print-orders")
async def list_print_orders(admin=Depends(get_admin)):
    orders = await db.print_orders.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return orders

@api_router.put("/admin/print-orders/{order_id}/status")
async def update_order_status(order_id: str, status: str = Query(...), admin=Depends(get_admin)):
    if status not in ("pending", "processing", "printed", "shipped", "completed", "cancelled"):
        raise HTTPException(status_code=400, detail="Invalid status")
    result = await db.print_orders.update_one(
        {"id": order_id},
        {"$set": {"status": status, "updated_at": datetime.now(timezone.utc).isoformat()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"status": status}

# ─── Print Shop Public Endpoints (for couples via share) ───
@api_router.get("/share/{token}/print-sizes")
async def get_print_sizes_for_share(token: str):
    """Get available print sizes for ordering"""
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share or is_share_expired(share):
        raise HTTPException(status_code=404, detail="Share not found or expired")
    sizes = await db.print_sizes.find({"is_active": True}, {"_id": 0}).sort("name", 1).to_list(100)
    return {"sizes": sizes, "shipping_cost": SHIPPING_COST}

@api_router.post("/share/{token}/print-order")
async def create_print_order(token: str, data: PrintOrderCreate, session=Depends(get_share_session)):
    """Create a print order - returns PayPal payment URL"""
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share or is_share_expired(share):
        raise HTTPException(status_code=404, detail="Share not found or expired")
    
    gallery = await db.galleries.find_one({"id": data.gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    # Calculate order total
    order_items = []
    subtotal = 0.0
    
    for item in data.items:
        file = await db.files.find_one({"id": item.file_id, "gallery_id": data.gallery_id}, {"_id": 0})
        if not file:
            raise HTTPException(status_code=404, detail=f"File {item.file_id} not found")
        
        size = await db.print_sizes.find_one({"id": item.size_id, "is_active": True}, {"_id": 0})
        if not size:
            raise HTTPException(status_code=404, detail=f"Print size {item.size_id} not found")
        
        if item.finish not in ("gloss", "luster", "silk"):
            raise HTTPException(status_code=400, detail="Invalid finish type")
        
        price = size["prices"].get(item.finish, 0)
        item_total = price * item.quantity
        subtotal += item_total
        
        order_items.append({
            "file_id": item.file_id,
            "filename": file["filename"],
            "subfolder": file["subfolder"],
            "size_id": item.size_id,
            "size_name": size["name"],
            "finish": item.finish,
            "quantity": item.quantity,
            "unit_price": price,
            "total": item_total
        })
    
    total = subtotal + SHIPPING_COST
    
    # Create order
    order_id = str(uuid.uuid4())
    order_doc = {
        "id": order_id,
        "gallery_id": data.gallery_id,
        "gallery_name": gallery["folder_name"],
        "share_token": token,
        "customer_email": data.customer_email,
        "items": order_items,
        "subtotal": subtotal,
        "shipping": SHIPPING_COST,
        "total": total,
        "currency": "GBP",
        "status": "pending",
        "paypal_order_id": None,
        "shipping_address": None,  # Will be filled by PayPal
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    
    await db.print_orders.insert_one(order_doc)
    
    # Return order details - frontend will redirect to PayPal
    return {
        "order_id": order_id,
        "subtotal": subtotal,
        "shipping": SHIPPING_COST,
        "total": total,
        "currency": "GBP",
        "items": order_items
    }

@api_router.put("/share/{token}/print-order/{order_id}/paypal")
async def update_order_paypal(token: str, order_id: str, paypal_order_id: str = Query(...), status: str = Query("paid")):
    """Update order with PayPal transaction details"""
    order = await db.print_orders.find_one({"id": order_id, "share_token": token}, {"_id": 0})
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    
    await db.print_orders.update_one(
        {"id": order_id},
        {"$set": {
            "paypal_order_id": paypal_order_id,
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat()
        }}
    )
    return {"success": True}

@api_router.get("/share/{token}/print-orders")
async def get_my_print_orders(token: str, session=Depends(get_share_session)):
    """Get orders for this share"""
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    orders = await db.print_orders.find({"share_token": token}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return orders

# ─── Activity Tracking ───
@api_router.post("/share/{token}/track-view")
async def track_gallery_view(token: str, request: Request):
    """Track when a gallery is viewed."""
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        return {"ok": False}
    
    # Get client IP
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    gallery = await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0})
    gallery_name = gallery.get("folder_name", "Unknown") if gallery else "Unknown"
    
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    await db.activity.update_one(
        {"gallery_id": share["gallery_id"], "date": today},
        {"$inc": {"views": 1}},
        upsert=True
    )
    await db.galleries.update_one(
        {"id": share["gallery_id"]},
        {"$inc": {"total_views": 1}}
    )
    
    # Add to detailed activity log
    await db.activity_log.insert_one({
        "id": str(uuid.uuid4()),
        "gallery_id": share["gallery_id"],
        "gallery_name": gallery_name,
        "share_label": share.get("label", token),
        "action": "view",
        "details": "Gallery viewed",
        "ip_address": client_ip,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {"ok": True}

@api_router.post("/share/{token}/track-download")
async def track_download(token: str, request: Request, session=Depends(get_share_session)):
    """Legacy tracking endpoint — downloads are now logged directly in the download handlers."""
    return {"ok": True}

# ─── Live Visitor Heartbeat ───

def parse_device(user_agent: str) -> str:
    """Simple device detection from User-Agent."""
    ua = user_agent.lower()
    if any(m in ua for m in ["iphone", "android", "mobile"]):
        return "Mobile"
    if any(t in ua for t in ["ipad", "tablet"]):
        return "Tablet"
    return "Desktop"

class HeartbeatData(BaseModel):
    session_id: str
    action: str = "browsing"
    subfolder: Optional[str] = None
    detail: Optional[str] = None

@api_router.post("/share/{token}/heartbeat")
async def visitor_heartbeat(token: str, data: HeartbeatData, request: Request):
    """Receive a heartbeat from an active gallery visitor."""
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        return {"ok": False}
    gallery = await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0})
    gallery_name = gallery.get("folder_name", "Unknown") if gallery else "Unknown"
    
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    user_agent = request.headers.get("User-Agent", "")
    device = parse_device(user_agent)
    
    now = time.time()
    # Update or create visitor entry
    existing = active_visitors.get(data.session_id)
    active_visitors[data.session_id] = {
        "gallery_id": share["gallery_id"],
        "gallery_name": gallery_name,
        "share_label": share.get("label", token),
        "action": data.action,
        "subfolder": data.subfolder,
        "detail": data.detail,
        "device": device,
        "ip": client_ip,
        "last_seen": now,
        "first_seen": existing["first_seen"] if existing else now,
    }
    
    # Clean up stale visitors
    stale = [k for k, v in active_visitors.items() if now - v["last_seen"] > VISITOR_TIMEOUT]
    for k in stale:
        del active_visitors[k]
    
    return {"ok": True}

@api_router.get("/admin/live-visitors")
async def get_live_visitors(admin=Depends(get_admin)):
    """Get all currently active visitors."""
    now = time.time()
    # Clean stale entries
    stale = [k for k, v in active_visitors.items() if now - v["last_seen"] > VISITOR_TIMEOUT]
    for k in stale:
        del active_visitors[k]
    
    visitors = []
    for session_id, v in active_visitors.items():
        visitors.append({
            "session_id": session_id,
            "gallery_id": v["gallery_id"],
            "gallery_name": v["gallery_name"],
            "share_label": v["share_label"],
            "action": v["action"],
            "subfolder": v["subfolder"],
            "detail": v["detail"],
            "device": v["device"],
            "ip": v.get("ip", ""),
            "duration_seconds": int(now - v["first_seen"]),
        })
    return {"count": len(visitors), "visitors": visitors}

@api_router.get("/admin/activity")
async def get_admin_activity(limit: int = Query(50, le=200), gallery_id: str = Query(None), action: str = Query(None), search: str = Query(None), admin=Depends(get_admin)):
    """Get recent activity across all galleries, optionally filtered."""
    query = {}
    if gallery_id:
        query["gallery_id"] = gallery_id
    if action:
        query["action"] = action
    if search:
        query["$or"] = [
            {"share_label": {"$regex": search, "$options": "i"}},
            {"gallery_name": {"$regex": search, "$options": "i"}},
            {"details": {"$regex": search, "$options": "i"}},
        ]
    activities = await db.activity_log.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"activities": activities}

@api_router.get("/admin/activity/archived")
async def get_archived_activity(limit: int = Query(200, le=500), gallery_id: str = Query(None), action: str = Query(None), search: str = Query(None), admin=Depends(get_admin)):
    """Get archived activity logs."""
    query = {}
    if gallery_id:
        query["gallery_id"] = gallery_id
    if action:
        query["action"] = action
    if search:
        query["$or"] = [
            {"share_label": {"$regex": search, "$options": "i"}},
            {"gallery_name": {"$regex": search, "$options": "i"}},
            {"details": {"$regex": search, "$options": "i"}},
        ]
    activities = await db.activity_log_archive.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    count = await db.activity_log_archive.count_documents({})
    return {"activities": activities, "total_archived": count}

@api_router.delete("/admin/activity/clear")
async def clear_activity_logs(admin=Depends(get_admin)):
    """Clear all active activity logs."""
    result = await db.activity_log.delete_many({})
    logger.info(f"Cleared {result.deleted_count} activity logs")
    return {"success": True, "cleared": result.deleted_count}

@api_router.post("/admin/activity/archive-now")
async def archive_old_logs(admin=Depends(get_admin)):
    """Manually trigger archiving of logs older than 6 months."""
    count = await run_auto_archive()
    return {"success": True, "archived": count}

@api_router.get("/admin/activity/stats")
async def activity_stats(admin=Depends(get_admin)):
    """Get counts for active and archived logs."""
    active = await db.activity_log.count_documents({})
    archived = await db.activity_log_archive.count_documents({})
    return {"active_count": active, "archived_count": archived}

@api_router.get("/admin/galleries/{gallery_id}/stats")
async def get_gallery_stats(gallery_id: str, admin=Depends(get_admin)):
    """Get activity stats for a gallery."""
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    # Get last 30 days activity
    thirty_days_ago = (datetime.now(timezone.utc) - timedelta(days=30)).strftime("%Y-%m-%d")
    activity = await db.activity.find(
        {"gallery_id": gallery_id, "date": {"$gte": thirty_days_ago}},
        {"_id": 0}
    ).sort("date", 1).to_list(30)
    
    # Count unique visitors (by IP) from activity log
    unique_ips = await db.activity_log.distinct("ip_address", {"gallery_id": gallery_id, "ip_address": {"$ne": None}})
    
    # Check if album has been submitted (files exist in Album Favourites)
    album_submitted = await db.files.count_documents({
        "gallery_id": gallery_id,
        "subfolder": "Album Favourites"
    }) > 0
    
    return {
        "total_views": gallery.get("total_views", 0),
        "total_downloads": gallery.get("total_downloads", 0),
        "unique_visitors": len(unique_ips),
        "album_submitted": album_submitted,
        "daily_activity": activity
    }

@api_router.get("/admin/dashboard-stats")
async def get_dashboard_stats(admin=Depends(get_admin)):
    """Get the 5 key dashboard stats."""
    now = datetime.now(timezone.utc)
    week_ago = (now - timedelta(days=7)).isoformat()
    soon = (now + timedelta(days=14)).isoformat()

    # Active galleries
    active_galleries = await db.galleries.count_documents({})

    # Expiring soon — active main shares expiring within 14 days
    expiring_shares = await db.shares.find({
        "is_active": True,
        "guest_upload_mode": {"$ne": True},
        "expires_at": {"$exists": True, "$ne": None, "$lte": soon, "$gte": now.isoformat()}
    }).to_list(500)
    expiring_gallery_ids = list(set(s["gallery_id"] for s in expiring_shares))
    expiring_soon = len(expiring_gallery_ids)

    # Downloads this week
    downloads_this_week = await db.activity_log.count_documents({
        "action": {"$in": ["download", "download_file", "download_all"]},
        "timestamp": {"$gte": week_ago}
    })

    # Pending albums — galleries where Album Favourites subfolder has 0 files (single aggregation)
    galleries_with_album_files = await db.files.distinct("gallery_id", {"subfolder": "Album Favourites"})
    active_galleries_count = await db.galleries.count_documents({})
    pending_albums = active_galleries_count - len(galleries_with_album_files)

    # Storage used — sum of all file sizes
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$file_size"}}}]
    result = await db.files.aggregate(pipeline).to_list(1)
    total_bytes = result[0]["total"] if result else 0

    return {
        "active_galleries": active_galleries,
        "expiring_soon": expiring_soon,
        "downloads_this_week": downloads_this_week,
        "pending_albums": pending_albums,
        "storage_used_bytes": total_bytes
    }

async def log_bandwidth_event(event_type: str, bytes_size: int, detail: str = ""):
    """Log a bandwidth event for application-level tracking."""
    try:
        await db.bandwidth_log.insert_one({
            "type": event_type,
            "bytes": bytes_size,
            "detail": detail,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception:
        pass


@api_router.get("/admin/diagnose-gallery/{gallery_id}")
async def diagnose_gallery_files(gallery_id: str, admin=Depends(get_admin)):
    """Diagnostic endpoint: check if DB files match what's on disk for a gallery."""
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    gallery_path = get_gallery_path(gallery["folder_name"])
    db_files = await db.files.find({"gallery_id": gallery_id}, {"_id": 0}).to_list(50000)
    
    result = {
        "gallery_name": gallery["folder_name"],
        "upload_dir": str(UPLOAD_DIR),
        "gallery_path": str(gallery_path),
        "gallery_path_exists": gallery_path.exists(),
        "db_file_count": len(db_files),
        "subfolders_in_db": gallery.get("subfolders", []),
        "disk_subfolders": [],
        "files_found": 0,
        "files_missing": 0,
        "missing_samples": [],
        "found_samples": [],
    }
    
    # Check what's actually on disk
    if gallery_path.exists():
        try:
            for item in sorted(gallery_path.iterdir()):
                if item.is_dir() and not item.name.startswith('.'):
                    disk_files = list(item.iterdir())
                    result["disk_subfolders"].append({
                        "name": item.name,
                        "file_count": len(disk_files),
                        "sample_files": [f.name for f in disk_files[:5]]
                    })
        except Exception as e:
            result["disk_error"] = str(e)
    
    # Check each DB file against disk
    for f in db_files:
        fp = gallery_path / f["subfolder"] / f["filename"]
        if fp.exists():
            result["files_found"] += 1
            if len(result["found_samples"]) < 3:
                result["found_samples"].append({"path": str(fp), "size": fp.stat().st_size})
        else:
            result["files_missing"] += 1
            if len(result["missing_samples"]) < 10:
                result["missing_samples"].append({
                    "expected_path": str(fp),
                    "subfolder": f["subfolder"],
                    "filename": f["filename"],
                    "parent_exists": fp.parent.exists(),
                    "parent_contents": [x.name for x in fp.parent.iterdir()][:5] if fp.parent.exists() else []
                })
    
    return result


@api_router.get("/admin/network-stats")
async def get_network_stats(admin=Depends(get_admin)):
    """Get network bandwidth usage: daily and weekly totals from stored snapshots."""
    now = datetime.now(timezone.utc)
    day_ago = (now - timedelta(hours=24)).isoformat()
    week_ago = (now - timedelta(days=7)).isoformat()

    # Get current live reading
    counters = psutil.net_io_counters()
    current = {
        "bytes_sent": counters.bytes_sent,
        "bytes_recv": counters.bytes_recv,
        "timestamp": now.isoformat()
    }

    # Get oldest snapshot within last 24h
    day_snapshots = await db.network_snapshots.find(
        {"timestamp": {"$gte": day_ago}}
    ).sort("timestamp", 1).limit(1).to_list(1)

    # Get oldest snapshot within last 7 days
    week_snapshots = await db.network_snapshots.find(
        {"timestamp": {"$gte": week_ago}}
    ).sort("timestamp", 1).limit(1).to_list(1)

    daily_sent = 0
    daily_recv = 0
    weekly_sent = 0
    weekly_recv = 0

    if day_snapshots:
        oldest_day = day_snapshots[0]
        daily_sent = max(0, counters.bytes_sent - oldest_day["bytes_sent"])
        daily_recv = max(0, counters.bytes_recv - oldest_day["bytes_recv"])

    if week_snapshots:
        oldest_week = week_snapshots[0]
        weekly_sent = max(0, counters.bytes_sent - oldest_week["bytes_sent"])
        weekly_recv = max(0, counters.bytes_recv - oldest_week["bytes_recv"])

    # Clean up snapshots older than 8 days
    cutoff = (now - timedelta(days=8)).isoformat()
    await db.network_snapshots.delete_many({"timestamp": {"$lt": cutoff}})

    # App-level bandwidth: video streams + file downloads tracked by the app
    daily_video_pipeline = [{"$match": {"type": "video_stream", "timestamp": {"$gte": day_ago}}}, {"$group": {"_id": None, "total": {"$sum": "$bytes"}}}]
    daily_download_pipeline = [{"$match": {"type": "file_download", "timestamp": {"$gte": day_ago}}}, {"$group": {"_id": None, "total": {"$sum": "$bytes"}}}]
    weekly_video_pipeline = [{"$match": {"type": "video_stream", "timestamp": {"$gte": week_ago}}}, {"$group": {"_id": None, "total": {"$sum": "$bytes"}}}]
    weekly_download_pipeline = [{"$match": {"type": "file_download", "timestamp": {"$gte": week_ago}}}, {"$group": {"_id": None, "total": {"$sum": "$bytes"}}}]

    dv = await db.bandwidth_log.aggregate(daily_video_pipeline).to_list(1)
    dd = await db.bandwidth_log.aggregate(daily_download_pipeline).to_list(1)
    wv = await db.bandwidth_log.aggregate(weekly_video_pipeline).to_list(1)
    wd = await db.bandwidth_log.aggregate(weekly_download_pipeline).to_list(1)

    daily_video = dv[0]["total"] if dv else 0
    daily_downloads = dd[0]["total"] if dd else 0
    weekly_video = wv[0]["total"] if wv else 0
    weekly_downloads = wd[0]["total"] if wd else 0

    # Clean up old bandwidth logs
    await db.bandwidth_log.delete_many({"timestamp": {"$lt": cutoff}})

    return {
        "daily": {
            "sent_bytes": daily_sent,
            "recv_bytes": daily_recv,
            "total_bytes": daily_sent + daily_recv
        },
        "weekly": {
            "sent_bytes": weekly_sent,
            "recv_bytes": weekly_recv,
            "total_bytes": weekly_sent + weekly_recv
        },
        "video": {
            "daily_bytes": daily_video,
            "weekly_bytes": weekly_video
        },
        "downloads": {
            "daily_bytes": daily_downloads,
            "weekly_bytes": weekly_downloads
        },
        "current": current
    }

@api_router.get("/admin/galleries-stats")
async def get_all_galleries_stats(admin=Depends(get_admin)):
    """Get summary stats for all galleries (for dashboard cards)."""
    galleries = await db.galleries.find({}, {"_id": 0, "id": 1}).to_list(1000)
    
    stats = {}
    for gallery in galleries:
        gid = gallery["id"]
        
        # Get gallery doc for view/download counts
        gallery_doc = await db.galleries.find_one({"id": gid}, {"_id": 0, "total_views": 1, "total_downloads": 1})
        
        # Count unique visitors
        unique_ips = await db.activity_log.distinct("ip_address", {"gallery_id": gid, "ip_address": {"$ne": None}})
        
        # Check album submitted
        album_submitted = await db.files.count_documents({
            "gallery_id": gid,
            "subfolder": "Album Favourites"
        }) > 0
        
        stats[gid] = {
            "total_views": gallery_doc.get("total_views", 0) if gallery_doc else 0,
            "total_downloads": gallery_doc.get("total_downloads", 0) if gallery_doc else 0,
            "unique_visitors": len(unique_ips),
            "album_submitted": album_submitted
        }
    
    return stats

# ─── Backup Endpoint ───
BACKUP_DIR = Path(os.environ.get('BACKUP_DIR', '/backup'))

@api_router.post("/admin/backup")
async def run_backup(admin=Depends(get_admin)):
    """Run incremental backup of all galleries to the backup directory."""
    if not BACKUP_DIR.exists():
        raise HTTPException(status_code=500, detail="Backup directory not configured or not accessible")
    
    stats = {"copied": 0, "skipped": 0, "errors": [], "galleries": 0}
    
    try:
        # Iterate through all gallery folders in UPLOAD_DIR
        for gallery_folder in UPLOAD_DIR.iterdir():
            if not gallery_folder.is_dir():
                continue
            
            stats["galleries"] += 1
            backup_gallery_path = get_backup_gallery_path(gallery_folder.name)
            backup_gallery_path.mkdir(parents=True, exist_ok=True)
            
            # Walk through all subfolders and files
            for src_path in gallery_folder.rglob("*"):
                if src_path.is_file():
                    # Skip thumbnail/preview files
                    if '.thumb.' in src_path.name or '.preview.' in src_path.name:
                        continue
                    
                    # Calculate relative path and destination
                    rel_path = src_path.relative_to(gallery_folder)
                    try:
                        dst_path = contained_path(
                            backup_gallery_path,
                            *rel_path.parts,
                            labels=tuple("backup path component" for _ in rel_path.parts),
                        )
                    except UnsafePathError as exc:
                        stats["errors"].append(f"Skipped unsafe backup path {rel_path}: {exc}")
                        continue
                    
                    # Create parent directories if needed
                    dst_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Check if file needs copying (incremental logic)
                    needs_copy = False
                    if not dst_path.exists():
                        needs_copy = True
                    else:
                        # Compare modification time and size
                        src_stat = src_path.stat()
                        dst_stat = dst_path.stat()
                        if src_stat.st_size != dst_stat.st_size or src_stat.st_mtime > dst_stat.st_mtime:
                            needs_copy = True
                    
                    if needs_copy:
                        try:
                            shutil.copy2(src_path, dst_path)  # copy2 preserves metadata
                            stats["copied"] += 1
                        except Exception as e:
                            stats["errors"].append(f"{src_path.name}: {str(e)}")
                    else:
                        stats["skipped"] += 1
        
        return {
            "success": True,
            "message": f"Backup complete. {stats['copied']} files copied, {stats['skipped']} unchanged.",
            "stats": stats
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup failed: {str(e)}")

# ─── Video Compression Settings ───
VIDEO_COMPRESSION_SIZE_THRESHOLD = 200 * 1024 * 1024  # 200MB in bytes

async def get_compression_setting():
    """Get video compression enabled setting from DB."""
    setting = await db.settings.find_one({"key": "guest_video_compression"}, {"_id": 0})
    return setting.get("enabled", False) if setting else False

async def set_compression_setting(enabled: bool):
    """Set video compression enabled setting in DB."""
    await db.settings.update_one(
        {"key": "guest_video_compression"},
        {"$set": {"key": "guest_video_compression", "enabled": enabled}},
        upsert=True
    )

def compress_video_ffmpeg(input_path: Path, output_path: Path) -> bool:
    """
    Compress video using FFmpeg with high-quality settings.
    Returns True if successful, False otherwise.
    Tries GPU (VAAPI) first, falls back to CPU (libx264).
    """
    # Try GPU first (VAAPI)
    try:
        gpu_cmd = [
            'ffmpeg', '-y',
            '-hwaccel', 'vaapi',
            '-hwaccel_device', '/dev/dri/renderD128',
            '-hwaccel_output_format', 'vaapi',
            '-i', str(input_path),
            '-vf', 'format=nv12|vaapi',
            '-c:v', 'h264_vaapi',
            '-qp', '23',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            str(output_path)
        ]
        result = subprocess.run(gpu_cmd, capture_output=True, timeout=600)
        if result.returncode == 0:
            logger.info(f"Guest video compressed via GPU: {input_path.name}")
            return True
        logger.warning(f"GPU compression failed for {input_path.name}, falling back to CPU")
    except Exception as e:
        logger.warning(f"GPU compression error for {input_path.name}: {e}, falling back to CPU")

    if output_path.exists():
        output_path.unlink()

    # Fallback: CPU encoding
    try:
        cpu_cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-c:v', 'libx264',
            '-crf', '23',
            '-preset', 'medium',
            '-c:a', 'aac', '-b:a', '128k',
            '-movflags', '+faststart',
            '-threads', '2',
            str(output_path)
        ]
        result = subprocess.run(cpu_cmd, capture_output=True, timeout=600)
        if result.returncode == 0:
            logger.info(f"Guest video compressed via CPU: {input_path.name}")
            return True
        logger.error(f"CPU compression also failed for {input_path.name}: {result.stderr[:500]}")
        return False
    except Exception as e:
        logger.error(f"Video compression failed: {e}")
        return False

def compress_guest_video_background(file_path: Path, file_id: str, gallery_id: str):
    """
    Background task to compress a guest video if it exceeds threshold.
    Keeps original until compression is verified, then replaces.
    """
    import asyncio
    from motor.motor_asyncio import AsyncIOMotorClient
    
    try:
        file_size = file_path.stat().st_size
        if file_size < VIDEO_COMPRESSION_SIZE_THRESHOLD:
            logger.info(f"Video {file_path.name} is under 200MB, skipping compression")
            return
        
        logger.info(f"Starting compression for {file_path.name} ({file_size / 1024 / 1024:.1f}MB)")
        
        # Create temp output path
        temp_output = file_path.with_suffix('.compressed.mp4')
        
        # Compress
        success = compress_video_ffmpeg(file_path, temp_output)
        
        if success and temp_output.exists():
            new_size = temp_output.stat().st_size
            
            # Only replace if we actually saved space (at least 10% reduction)
            if new_size < file_size * 0.9:
                # Delete original directly (no backup needed - compressed is verified)
                file_path.unlink()
                
                # Move compressed to original location
                shutil.move(str(temp_output), str(file_path))
                
                # Update file size in database using sync approach
                try:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    
                    # Create new client for this thread
                    thread_client = AsyncIOMotorClient(os.environ.get("MONGO_URL", "mongodb://localhost:27017"))
                    thread_db = thread_client[os.environ.get("DB_NAME", "weddings_gallery")]
                    
                    loop.run_until_complete(
                        thread_db.files.update_one(
                            {"id": file_id},
                            {"$set": {
                                "file_size": new_size,
                                "compressed": True,
                                "original_size": file_size
                            }}
                        )
                    )
                    thread_client.close()
                    loop.close()
                except Exception as db_err:
                    logger.error(f"DB update failed for {file_path.name}: {db_err}")
                
                savings = ((file_size - new_size) / file_size) * 100
                logger.info(f"Compressed {file_path.name}: {file_size/1024/1024:.1f}MB → {new_size/1024/1024:.1f}MB ({savings:.1f}% smaller)")
            else:
                # Compression didn't help enough, remove temp file
                temp_output.unlink(missing_ok=True)
                logger.info(f"Compression didn't reduce size enough for {file_path.name}, keeping original")
        else:
            # Compression failed, clean up
            if temp_output.exists():
                temp_output.unlink()
            logger.warning(f"Compression failed for {file_path.name}, keeping original")
            
    except Exception as e:
        logger.error(f"Error in compression background task: {e}")
        # Clean up any temp files
        try:
            temp_output = file_path.with_suffix('.compressed.mp4')
            if temp_output.exists():
                temp_output.unlink()
        except:
            pass

@api_router.get("/admin/settings/compression")
async def get_compression_status(admin=Depends(get_admin)):
    """Get current video compression setting."""
    enabled = await get_compression_setting()
    return {"enabled": enabled, "threshold_mb": VIDEO_COMPRESSION_SIZE_THRESHOLD / 1024 / 1024}

@api_router.post("/admin/settings/compression")
async def toggle_compression(enabled: bool = Query(...), admin=Depends(get_admin)):
    """Enable or disable guest video compression."""
    await set_compression_setting(enabled)
    status = "enabled" if enabled else "disabled"
    return {"success": True, "message": f"Guest video compression {status}", "enabled": enabled}

# ─── Email / SMTP Settings ───

@api_router.get("/admin/settings/smtp")
async def get_smtp_settings(admin=Depends(get_admin)):
    """Get SMTP settings (password masked)."""
    doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not doc:
        return {"smtp_server": "", "smtp_port": 465, "smtp_email": "", "smtp_password": "", "sender_name": "", "site_url": ""}
    data = doc.get("value", {})
    masked_pw = "••••••••" if data.get("smtp_password") else ""
    return {**data, "smtp_password": masked_pw, "site_url": data.get("site_url", "")}

class SMTPSettings(BaseModel):
    smtp_server: str
    smtp_port: int = 465
    smtp_email: str
    smtp_password: Optional[str] = None
    sender_name: str = ""
    site_url: str = ""

@api_router.post("/admin/settings/smtp")
async def save_smtp_settings(data: SMTPSettings, admin=Depends(get_admin)):
    """Save SMTP settings."""
    existing = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    value = {
        "smtp_server": data.smtp_server,
        "smtp_port": data.smtp_port,
        "smtp_email": data.smtp_email,
        "sender_name": data.sender_name,
        "site_url": data.site_url.rstrip("/") if data.site_url else "",
    }
    # Only update password if not the masked placeholder
    if data.smtp_password and data.smtp_password != "••••••••":
        value["smtp_password"] = data.smtp_password
    elif existing and existing.get("value", {}).get("smtp_password"):
        value["smtp_password"] = existing["value"]["smtp_password"]
    
    await db.settings.update_one({"key": "smtp"}, {"$set": {"key": "smtp", "value": value}}, upsert=True)
    return {"success": True}

@api_router.post("/admin/settings/smtp/test")
async def test_smtp(admin=Depends(get_admin)):
    """Send a test email to verify SMTP settings."""
    doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not doc or not doc.get("value", {}).get("smtp_email"):
        raise HTTPException(status_code=400, detail="SMTP not configured")
    smtp = doc["value"]
    try:
        msg = MIMEText("Your email settings are configured correctly!", "plain")
        msg["Subject"] = "SMTP Test — Gallery Notification System"
        msg["From"] = formataddr((smtp.get('sender_name', ''), smtp['smtp_email']))
        msg["To"] = smtp["smtp_email"]
        
        if smtp["smtp_port"] == 465:
            server = smtplib.SMTP_SSL(smtp["smtp_server"], smtp["smtp_port"], timeout=10)
        else:
            server = smtplib.SMTP(smtp["smtp_server"], smtp["smtp_port"], timeout=10)
            server.starttls()
        server.login(smtp["smtp_email"], smtp["smtp_password"])
        server.send_message(msg)
        server.quit()
        return {"success": True, "message": "Test email sent to " + smtp["smtp_email"]}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"SMTP error: {str(e)}")

@api_router.post("/admin/galleries/{gallery_id}/notify")
async def send_gallery_notification(gallery_id: str, request: Request, admin=Depends(get_admin)):
    """Send gallery ready notification email to couple."""
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    client_email = gallery.get("client_email", "")
    if not client_email:
        raise HTTPException(status_code=400, detail="No client email set for this gallery")
    
    # Get SMTP settings
    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not smtp_doc or not smtp_doc.get("value", {}).get("smtp_email"):
        raise HTTPException(status_code=400, detail="SMTP not configured. Go to Settings > Email to set up.")
    smtp = smtp_doc["value"]
    
    # The gallery-ready email must use the downloadable whole-gallery share.
    # Never fall back to a QR/guest-upload or subfolder-only share: doing so can
    # email the couple an upload link instead of their password-protected gallery.
    share = await db.shares.find_one(main_gallery_share_query(gallery_id), {"_id": 0})
    if not share:
        raise HTTPException(
            status_code=400,
            detail="No active main gallery download link found. Upload Wedding Images or create a whole-gallery Download share first.",
        )
    
    # Build gallery URL
    base_url = str(request.base_url).rstrip("/")
    # Use Referer/Origin header for the correct public URL
    origin = request.headers.get("origin") or request.headers.get("referer", "").rstrip("/")
    if origin:
        from urllib.parse import urlparse
        parsed = urlparse(origin)
        base_url = f"{parsed.scheme}://{parsed.netloc}"
    gallery_link = f"{base_url}/s/{share['token']}"
    share_password = share.get("password_raw", "")
    
    couple_name = gallery["folder_name"]
    
    # Build HTML email
    html_body = f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#FDFCF8;font-family:Georgia,'Times New Roman',serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#FDFCF8;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border:1px solid #E8E4DC;max-width:600px;">

<!-- Header -->
<tr><td style="background-color:#1C1917;padding:30px 40px;text-align:center;">
<h1 style="color:#D4AF37;font-family:Georgia,'Times New Roman',serif;font-size:24px;margin:0;font-weight:normal;letter-spacing:2px;">
Your Wedding Gallery is Ready
</h1>
</td></tr>

<!-- Body -->
<tr><td style="padding:40px;">

<p style="font-size:18px;color:#1C1917;margin:0 0 20px 0;line-height:1.6;">
Huge Congratulations, {couple_name} &#x1F942;
</p>

<p style="font-size:15px;color:#57534E;margin:0 0 15px 0;line-height:1.8;">
I hope you're both having the best time settling into married life!
</p>

<p style="font-size:15px;color:#57534E;margin:0 0 25px 0;line-height:1.8;">
The wait is finally over&mdash;your wedding gallery is officially ready for viewing &amp; downloading. I know you've been eager to relive all those special moments, and I'm so excited for you to see them.
</p>

<!-- Gallery Link Section -->
<div style="background-color:#F5F2EB;border-left:4px solid #D4AF37;padding:20px 25px;margin:0 0 25px 0;">
<p style="font-size:14px;color:#1C1917;margin:0 0 8px 0;font-weight:bold;letter-spacing:1px;">
&#x1F4F8; HOW TO ACCESS YOUR MEMORIES
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 12px 0;line-height:1.6;">
You can dive into your gallery right now using the link below.
</p>
<p style="margin:0;">
<a href="{gallery_link}" style="display:inline-block;background-color:#1C1917;color:#D4AF37;text-decoration:none;padding:12px 30px;font-size:14px;letter-spacing:2px;font-weight:bold;">
VIEW YOUR GALLERY
</a>
</p>
{f'<p style="font-size:13px;color:#A8A29E;margin:10px 0 0 0;">Password: <strong style="color:#1C1917;">{share_password}</strong></p>' if share_password else ''}
</div>

<!-- Album Section -->
<div style="margin:0 0 25px 0;">
<p style="font-size:14px;color:#1C1917;margin:0 0 12px 0;font-weight:bold;letter-spacing:1px;">
&#x1F4D6; CREATING YOUR KEEPSAKE ALBUM
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 10px 0;line-height:1.8;">
If your package includes a wedding album, let's get the design process started!<br>
Select Your Favourites: Browse your gallery and click the "Heart" icon on the photos you love most.
</p>

<p style="font-size:14px;color:#1C1917;margin:15px 0 8px 0;font-weight:bold;">
How Many Images to Choose:
</p>
<table cellpadding="8" cellspacing="0" style="border:1px solid #E8E4DC;margin:0 0 10px 0;width:100%;">
<tr style="background-color:#F5F2EB;">
<td style="font-size:13px;color:#57534E;border-bottom:1px solid #E8E4DC;font-weight:bold;">Standard / Special Offer Albums</td>
<td style="font-size:13px;color:#1C1917;border-bottom:1px solid #E8E4DC;text-align:right;">Up to <strong>40 images</strong> + 1 front cover</td>
</tr>
<tr>
<td style="font-size:13px;color:#57534E;font-weight:bold;">Full-Price Albums</td>
<td style="font-size:13px;color:#1C1917;text-align:right;">Up to <strong>60 images</strong> + 1 front cover</td>
</tr>
</table>
<p style="font-size:14px;color:#57534E;margin:0 0 10px 0;line-height:1.6;">
<strong>Final Step:</strong> Once you've picked your favourites, send me a quick email with the image number you'd like for your front cover.
</p>
<p style="font-size:14px;color:#A8A29E;margin:0;line-height:1.6;font-style:italic;">
Need help? I've included some "How-To" videos right inside your gallery folder to guide you through the process!
</p>
</div>

<!-- What Happens Next -->
<div style="background-color:#F5F2EB;border-left:4px solid #D4AF37;padding:20px 25px;margin:0 0 30px 0;">
<p style="font-size:14px;color:#1C1917;margin:0 0 8px 0;font-weight:bold;letter-spacing:1px;">
&#x1F552; WHAT HAPPENS NEXT?
</p>
<p style="font-size:15px;color:#57534E;margin:0;line-height:1.8;">
Once I receive your final selection, I'll get to work on the design. Your custom album will be designed, printed, and delivered to your door within 4 to 6 weeks.
</p>
</div>

<p style="font-size:15px;color:#57534E;margin:0 0 25px 0;line-height:1.8;">
Enjoy your photos&mdash;it was such an honour to capture your big day!
</p>

<p style="font-size:15px;color:#1C1917;margin:0;line-height:1.8;">
Best Regards<br>
<strong>Mark</strong><br>
<em>Weddings By Mark</em>
</p>

</td></tr>

<!-- Awards -->
{f'''<tr><td style="padding:25px 40px 10px;text-align:center;">
<p style="font-size:11px;color:#A8A29E;margin:0 0 12px 0;letter-spacing:1.5px;text-transform:uppercase;">Award-Winning Photography</p>
<img src="{smtp.get("site_url", "")}/api/public/email-assets/awards-badges.png" alt="Awards" style="max-width:480px;width:100%;height:auto;" />
</td></tr>''' if smtp.get("site_url") else ''}

<!-- Footer -->
<tr><td style="background-color:#1C1917;padding:20px 40px;text-align:center;">
<p style="color:#A8A29E;font-size:12px;margin:0;letter-spacing:1px;">
WEDDINGS BY MARK &bull; CAPTURING YOUR STORY
</p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>"""

    # Send the email
    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = "Your Wedding Gallery is Ready"
        msg["From"] = formataddr((smtp.get('sender_name', 'Weddings By Mark'), smtp['smtp_email']))
        msg["To"] = client_email
        msg.attach(MIMEText(html_body, "html"))
        
        if smtp["smtp_port"] == 465:
            server = smtplib.SMTP_SSL(smtp["smtp_server"], smtp["smtp_port"], timeout=15)
        else:
            server = smtplib.SMTP(smtp["smtp_server"], smtp["smtp_port"], timeout=15)
            server.starttls()
        server.login(smtp["smtp_email"], smtp["smtp_password"])
        server.send_message(msg)
        server.quit()
        
        # Log the notification
        await db.galleries.update_one({"id": gallery_id}, {"$set": {
            "notification_sent_at": datetime.now(timezone.utc).isoformat(),
            "notification_sent_to": client_email
        }})

        # Log to email_log
        await db.email_log.insert_one({
            "type": "gallery_ready",
            "subject": "Your Wedding Gallery is Ready",
            "gallery_name": couple_name,
            "recipient": client_email,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        return {"success": True, "message": f"Notification sent to {client_email}"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send email: {str(e)}")

async def run_auto_archive():
    """Move activity logs older than 6 months to the archive collection."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=183)).isoformat()
    old_logs = await db.activity_log.find({"timestamp": {"$lt": cutoff}}).to_list(None)
    if not old_logs:
        return 0
    # Copy to archive (strip _id so MongoDB assigns new ones)
    archive_docs = [{k: v for k, v in doc.items() if k != "_id"} for doc in old_logs]
    await db.activity_log_archive.insert_many(archive_docs)
    # Remove from active
    result = await db.activity_log.delete_many({"timestamp": {"$lt": cutoff}})
    logger.info(f"Auto-archived {result.deleted_count} activity logs older than 6 months")
    
    # Send archive email notification if SMTP is configured
    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if smtp_doc and smtp_doc.get("value", {}).get("smtp_email"):
        smtp = smtp_doc["value"]
        try:
            msg = MIMEText(
                f"Activity Log Archive Summary\n\n"
                f"{result.deleted_count} log entries older than 6 months have been archived.\n"
                f"Archived on: {datetime.now(timezone.utc).strftime('%d %B %Y at %H:%M UTC')}\n\n"
                f"You can view archived logs in your admin panel under Activity > Archive tab.\n\n"
                f"— Gallery System",
                "plain"
            )
            msg["Subject"] = "Activity Log Archived — Gallery System"
            msg["From"] = formataddr((smtp.get("sender_name", ""), smtp["smtp_email"]))
            msg["To"] = smtp["smtp_email"]
            
            if smtp["smtp_port"] == 465:
                server = smtplib.SMTP_SSL(smtp["smtp_server"], smtp["smtp_port"], timeout=10)
            else:
                server = smtplib.SMTP(smtp["smtp_server"], smtp["smtp_port"], timeout=10)
                server.starttls()
            server.login(smtp["smtp_email"], smtp["smtp_password"])
            server.send_message(msg)
            server.quit()
            logger.info("Archive notification email sent")
        except Exception as e:
            logger.warning(f"Failed to send archive email: {e}")
    
    return result.deleted_count

# ─── Reusable SMTP Send Helper ───
def send_smtp_email(smtp: dict, to_email: str, subject: str, html_body: str, attachments: list = None):
    """Send an email using stored SMTP settings. Runs synchronously (use in thread/executor).
    attachments: list of dicts with 'filename' and 'data' (bytes)
    """
    msg = MIMEMultipart("mixed")
    msg["Subject"] = subject
    msg["From"] = formataddr((smtp.get("sender_name", "Weddings By Mark"), smtp["smtp_email"]))
    msg["To"] = to_email

    # HTML body as a sub-part
    html_part = MIMEText(html_body, "html")
    msg.attach(html_part)

    # Add attachments
    if attachments:
        for att in attachments:
            from email.mime.base import MIMEBase
            from email import encoders
            part = MIMEBase("application", "octet-stream")
            part.set_payload(att["data"])
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{att["filename"]}"')
            msg.attach(part)

    if smtp["smtp_port"] == 465:
        server = smtplib.SMTP_SSL(smtp["smtp_server"], smtp["smtp_port"], timeout=15)
    else:
        server = smtplib.SMTP(smtp["smtp_server"], smtp["smtp_port"], timeout=15)
        server.starttls()
    server.login(smtp["smtp_email"], smtp["smtp_password"])
    server.send_message(msg)
    server.quit()

def get_awards_url(smtp: dict) -> str:
    """Construct the awards badge image URL from site_url in SMTP settings."""
    site_url = smtp.get("site_url", "")
    if site_url:
        return f"{site_url}/api/public/email-assets/awards-badges.png"
    return ""

def build_branded_email(content_html: str, awards_url: str = "") -> str:
    """Wrap content in the branded Weddings By Mark email template."""
    awards_section = ""
    if awards_url:
        awards_section = f"""
<tr><td style="padding:25px 40px 10px;text-align:center;">
<p style="font-size:11px;color:#A8A29E;margin:0 0 12px 0;letter-spacing:1.5px;text-transform:uppercase;">Award-Winning Photography</p>
<img src="{awards_url}" alt="Awards" style="max-width:480px;width:100%;height:auto;" />
</td></tr>"""
    return f"""<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"></head>
<body style="margin:0;padding:0;background-color:#FDFCF8;font-family:Georgia,'Times New Roman',serif;">
<table width="100%" cellpadding="0" cellspacing="0" style="background-color:#FDFCF8;padding:40px 20px;">
<tr><td align="center">
<table width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border:1px solid #E8E4DC;max-width:600px;">
<tr><td style="background-color:#1C1917;padding:30px 40px;text-align:center;">
<h1 style="color:#D4AF37;font-family:Georgia,'Times New Roman',serif;font-size:22px;margin:0;font-weight:normal;letter-spacing:2px;">
Weddings By Mark
</h1>
</td></tr>
<tr><td style="padding:40px;">
{content_html}
</td></tr>{awards_section}
<tr><td style="background-color:#1C1917;padding:20px 40px;text-align:center;">
<p style="color:#A8A29E;font-size:12px;margin:0;letter-spacing:1px;">
WEDDINGS BY MARK &bull; CAPTURING YOUR STORY
</p>
</td></tr>
</table>
</td></tr>
</table>
</body>
</html>"""

# ─── Broadcast Email ───

class BroadcastEmailBody(BaseModel):
    subject: str
    body: str

@api_router.get("/admin/broadcast-preview")
async def broadcast_preview(admin=Depends(get_admin)):
    """Return list of couples who would receive a broadcast email."""
    galleries = await db.galleries.find(
        {"client_email": {"$exists": True, "$ne": "", "$ne": None}},
        {"_id": 0, "id": 1, "folder_name": 1, "client_email": 1}
    ).to_list(500)
    return {"recipients": galleries, "count": len(galleries)}

@api_router.post("/admin/broadcast-email")
async def send_broadcast_email(
    subject: str = Form(...),
    body: str = Form(...),
    attachments: List[UploadFile] = File(default=[]),
    admin=Depends(get_admin)
):
    """Send an email to all couples with an email address on their gallery."""
    if not subject.strip() or not body.strip():
        raise HTTPException(status_code=400, detail="Subject and body are required")

    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not smtp_doc or not smtp_doc.get("value", {}).get("smtp_email"):
        raise HTTPException(status_code=400, detail="SMTP not configured. Go to Settings > Email to set up.")
    smtp = smtp_doc["value"]

    galleries = await db.galleries.find(
        {"client_email": {"$exists": True, "$ne": "", "$ne": None}},
        {"_id": 0, "folder_name": 1, "client_email": 1}
    ).to_list(500)

    if not galleries:
        raise HTTPException(status_code=400, detail="No couples have email addresses set on their galleries")

    # Read attachment files once
    att_list = []
    for att in attachments:
        data = await att.read()
        att_list.append({"filename": att.filename, "data": data})

    # Convert plain text body to HTML paragraphs
    body_html = ""
    for line in body.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            body_html += '<br>'
        else:
            body_html += f'<p style="font-size:15px;color:#57534E;margin:0 0 12px 0;line-height:1.8;">{stripped}</p>\n'

    html_content = build_branded_email(body_html, get_awards_url(smtp))

    sent = 0
    failed = []
    for g in galleries:
        try:
            send_smtp_email(smtp, g["client_email"], subject.strip(), html_content, att_list if att_list else None)
            sent += 1
            await db.email_log.insert_one({
                "type": "broadcast",
                "subject": subject.strip(),
                "gallery_name": g["folder_name"],
                "recipient": g["client_email"],
                "has_attachment": len(att_list) > 0,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.warning(f"Broadcast email failed for {g['client_email']}: {e}")
            failed.append({"name": g["folder_name"], "email": g["client_email"], "error": str(e)})

    await db.activity_log.insert_one({
        "action": "broadcast_email",
        "details": f"Broadcast sent: '{subject}' to {sent} couples" + (f" with attachment" if att_list else ""),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "admin": True
    })

    return {"success": True, "sent": sent, "failed": len(failed), "failures": failed}

# ─── Email Log ───

@api_router.get("/admin/email-log")
async def get_email_log(limit: int = Query(200), admin=Depends(get_admin)):
    """Return log of all sent emails (broadcast, gallery-ready, expiry reminders)."""
    logs = await db.email_log.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"emails": logs, "count": len(logs)}

# ─── Email Templates ───

class EmailTemplateBody(BaseModel):
    name: str
    subject: str
    body: str

@api_router.get("/admin/email-templates")
async def list_email_templates(admin=Depends(get_admin)):
    templates = await db.email_templates.find({}, {"_id": 0}).sort("created_at", -1).to_list(100)
    return templates

@api_router.post("/admin/email-templates")
async def create_email_template(data: EmailTemplateBody, admin=Depends(get_admin)):
    if not data.name.strip() or not data.subject.strip() or not data.body.strip():
        raise HTTPException(status_code=400, detail="Name, subject and body are required")
    template = {
        "id": str(uuid.uuid4()),
        "name": data.name.strip(),
        "subject": data.subject.strip(),
        "body": data.body.strip(),
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.email_templates.insert_one(template)
    template.pop("_id", None)
    return template

@api_router.put("/admin/email-templates/{template_id}")
async def update_email_template(template_id: str, data: EmailTemplateBody, admin=Depends(get_admin)):
    if not data.name.strip() or not data.subject.strip() or not data.body.strip():
        raise HTTPException(status_code=400, detail="Name, subject and body are required")
    result = await db.email_templates.update_one(
        {"id": template_id},
        {"$set": {"name": data.name.strip(), "subject": data.subject.strip(), "body": data.body.strip()}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True}

@api_router.delete("/admin/email-templates/{template_id}")
async def delete_email_template(template_id: str, admin=Depends(get_admin)):
    result = await db.email_templates.delete_one({"id": template_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Template not found")
    return {"success": True}

class SendTemplateEmailBody(BaseModel):
    template_id: str

@api_router.post("/admin/galleries/{gallery_id}/send-template-email")
async def send_template_email(gallery_id: str, data: SendTemplateEmailBody, admin=Depends(get_admin)):
    template_id = data.template_id
    """Send an email template to the couple on this gallery, with token replacement."""
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    client_email = gallery.get("client_email", "")
    if not client_email:
        raise HTTPException(status_code=400, detail="No email address set for this gallery")

    template = await db.email_templates.find_one({"id": template_id}, {"_id": 0})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not smtp_doc or not smtp_doc.get("value", {}).get("smtp_email"):
        raise HTTPException(status_code=400, detail="SMTP not configured. Go to Settings > Email to set up.")
    smtp = smtp_doc["value"]

    # Find the first active share link for this gallery
    share = await db.shares.find_one({"gallery_id": gallery_id, "is_active": True, "guest_upload_mode": {"$ne": True}}, {"_id": 0})
    gallery_link = ""
    if share:
        gallery_link = share.get("custom_slug") or share.get("token", "")

    couple_name = gallery.get("folder_name", "")

    # Token replacement in subject and body
    subject = template["subject"].replace("{couple_name}", couple_name).replace("{gallery_link}", gallery_link)
    body_text = template["body"].replace("{couple_name}", couple_name).replace("{gallery_link}", gallery_link)

    # Convert body to HTML
    body_html = ""
    for line in body_text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            body_html += '<br>'
        else:
            body_html += f'<p style="font-size:15px;color:#57534E;margin:0 0 12px 0;line-height:1.8;">{stripped}</p>\n'

    html_content = build_branded_email(body_html, get_awards_url(smtp))

    try:
        send_smtp_email(smtp, client_email, subject, html_content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send email: {str(e)}")

    # Log to email_log
    await db.email_log.insert_one({
        "type": "template",
        "subject": subject,
        "gallery_name": couple_name,
        "recipient": client_email,
        "template_name": template["name"],
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"success": True, "message": f"Email sent to {client_email}"}


@api_router.post("/admin/galleries/{gallery_id}/send-email")
async def send_gallery_email_with_attachment(
    gallery_id: str,
    subject: str = Form(...),
    body: str = Form(...),
    template_id: str = Form(default=""),
    attachments: List[UploadFile] = File(default=[]),
    admin=Depends(get_admin)
):
    """Send an email to the couple on this gallery — supports attachments + optional template."""
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    client_email = gallery.get("client_email", "")
    if not client_email:
        raise HTTPException(status_code=400, detail="No email address set for this gallery")

    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not smtp_doc or not smtp_doc.get("value", {}).get("smtp_email"):
        raise HTTPException(status_code=400, detail="SMTP not configured")
    smtp = smtp_doc["value"]

    # Read attachments
    att_list = []
    for att in attachments:
        data = await att.read()
        att_list.append({"filename": att.filename, "data": data})

    # Convert body to HTML
    couple_name = gallery.get("folder_name", "")
    share = await db.shares.find_one({"gallery_id": gallery_id, "is_active": True, "guest_upload_mode": {"$ne": True}}, {"_id": 0})
    gallery_link = (share.get("custom_slug") or share.get("token", "")) if share else ""

    final_subject = subject.replace("{couple_name}", couple_name).replace("{gallery_link}", gallery_link)
    body_text = body.replace("{couple_name}", couple_name).replace("{gallery_link}", gallery_link)

    body_html = ""
    for line in body_text.strip().split("\n"):
        stripped = line.strip()
        if not stripped:
            body_html += '<br>'
        else:
            body_html += f'<p style="font-size:15px;color:#57534E;margin:0 0 12px 0;line-height:1.8;">{stripped}</p>\n'

    html_content = build_branded_email(body_html, get_awards_url(smtp))

    try:
        send_smtp_email(smtp, client_email, final_subject, html_content, att_list if att_list else None)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to send email: {str(e)}")

    await db.email_log.insert_one({
        "type": "gallery_email",
        "subject": final_subject,
        "gallery_name": couple_name,
        "recipient": client_email,
        "has_attachment": len(att_list) > 0,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })

    return {"success": True, "message": f"Email sent to {client_email}"}


# ─── Automated Expiry Reminder Emails ───

async def check_expiry_reminders():
    """Check for main share links expiring within 7 days and send reminders."""
    smtp_doc = await db.settings.find_one({"key": "smtp"}, {"_id": 0})
    if not smtp_doc or not smtp_doc.get("value", {}).get("smtp_email"):
        return 0

    smtp = smtp_doc["value"]
    now = datetime.now(timezone.utc)
    remind_start = now + timedelta(days=6)
    remind_end = now + timedelta(days=8)

    # Find active, non-guest-upload shares with expiry dates
    shares = await db.shares.find({
        "is_active": True,
        "guest_upload_mode": {"$ne": True},
        "expires_at": {"$exists": True, "$ne": None},
        "expiry_reminder_sent": {"$ne": True}
    }, {"_id": 0}).to_list(500)

    sent_count = 0
    for share in shares:
        try:
            expiry_str = share.get("expires_at", "")
            if not expiry_str:
                continue
            expiry_date = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))

            # Only send if expiring between 6-8 days from now
            if not (remind_start <= expiry_date <= remind_end):
                continue

            # Get the gallery for this share
            gallery = await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0})
            if not gallery:
                continue

            client_email = gallery.get("client_email", "")
            if not client_email:
                continue

            expiry_formatted = expiry_date.strftime("%d %B %Y")

            # Build the expiry reminder email with the user's exact wording
            reminder_html = f"""
<p style="font-size:15px;color:#57534E;margin:0 0 15px 0;line-height:1.8;">
Hey Guys,
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 15px 0;line-height:1.8;">
I hope you're both doing really well!
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 15px 0;line-height:1.8;">
This is just a little reminder to let you know that your online wedding gallery is due to expire in <strong>one week's time</strong>.
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 15px 0;line-height:1.8;">
If you haven't already done so, now's the perfect time to download everything from your gallery and save it somewhere safe. That includes all of your high-resolution photographs and, if your package included them, your wedding videos too.
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 15px 0;line-height:1.8;">
Although your gallery has been available for quite a while, I know how quickly life gets busy, so I didn't want you to miss the opportunity to keep everything before the gallery closes.
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 15px 0;line-height:1.8;">
If you've already downloaded everything, then you're all set and you can simply ignore this email.
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 15px 0;line-height:1.8;">
If you need a little more time for any reason, just hit reply and let me know. I'm always happy to extend your gallery for a short while if it'll help.
</p>
<p style="font-size:15px;color:#57534E;margin:0 0 25px 0;line-height:1.8;">
Thank you once again for choosing me to capture your wedding day. It really was a privilege to be part of it, and I hope your photographs and films continue to bring back all those wonderful memories for many years to come.
</p>
<p style="font-size:15px;color:#1C1917;margin:0;line-height:1.8;">
Speak soon,<br><br>
<strong>Mark</strong><br>
<em>Weddings by Mark</em>
</p>"""

            html_body = build_branded_email(reminder_html, get_awards_url(smtp))
            send_smtp_email(smtp, client_email, "Your Wedding Gallery Expires Soon", html_body)

            # Mark as sent so we don't send again
            await db.shares.update_one(
                {"id": share["id"]},
                {"$set": {"expiry_reminder_sent": True, "expiry_reminder_sent_at": now.isoformat()}}
            )

            # Log to email_log
            await db.email_log.insert_one({
                "type": "expiry_reminder",
                "subject": "Your Wedding Gallery Expires Soon",
                "gallery_name": gallery["folder_name"],
                "recipient": client_email,
                "timestamp": now.isoformat()
            })

            # Log it
            await db.activity_log.insert_one({
                "action": "expiry_reminder",
                "gallery_id": share["gallery_id"],
                "details": f"Expiry reminder sent to {client_email} (gallery expires {expiry_formatted})",
                "timestamp": now.isoformat(),
                "admin": True
            })

            sent_count += 1
            logger.info(f"Expiry reminder sent to {client_email} for gallery '{gallery['folder_name']}' (expires {expiry_formatted})")

        except Exception as e:
            logger.warning(f"Failed to send expiry reminder for share {share.get('id')}: {e}")

    if sent_count > 0:
        logger.info(f"Sent {sent_count} expiry reminder email(s)")
    return sent_count

async def network_snapshot_loop():
    """Background loop that records network stats every 15 minutes."""
    while True:
        try:
            counters = psutil.net_io_counters()
            await db.network_snapshots.insert_one({
                "bytes_sent": counters.bytes_sent,
                "bytes_recv": counters.bytes_recv,
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
        except Exception as e:
            logger.warning(f"Network snapshot failed: {e}")
        await asyncio.sleep(900)  # Every 15 minutes

async def expiry_reminder_loop():
    """Background loop that checks for expiring shares once daily."""
    while True:
        try:
            await check_expiry_reminders()
        except Exception as e:
            logger.warning(f"Expiry reminder check failed: {e}")
        # Check once every 24 hours
        await asyncio.sleep(86400)


# ─── Guest Uploads Auto-Cleanup (90 days) ───
GUEST_UPLOAD_MAX_AGE_DAYS = 90

async def run_guest_upload_cleanup():
    """Delete Guest Uploads subfolder files older than 90 days from disk, backup, and database.
    ONLY targets 'Guest Uploads' subfolder. Never touches Wedding Images, Video, SelfieBooth, Album Favourites, etc."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=GUEST_UPLOAD_MAX_AGE_DAYS)).isoformat()
    
    # Find all guest upload files older than the cutoff
    old_files = await db.files.find({
        "subfolder": "Guest Uploads",
        "uploaded_at": {"$lt": cutoff}
    }, {"_id": 0}).to_list(10000)
    
    if not old_files:
        return 0
    
    # Group by gallery for logging
    gallery_ids = set(f["gallery_id"] for f in old_files)
    total_deleted = 0
    
    for gallery_id in gallery_ids:
        gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
        if not gallery:
            continue
        
        gallery_files = [f for f in old_files if f["gallery_id"] == gallery_id]
        folder_name = gallery["folder_name"]
        
        for f in gallery_files:
            file_id = f["id"]
            filename = f["filename"]
            
            try:
                # Delete from disk (main upload)
                file_path = get_gallery_file_path(folder_name, "Guest Uploads", filename)
                if file_path.exists():
                    file_path.unlink()
                
                # Delete thumbnail
                thumb_path = get_thumb_path(gallery_id, "Guest Uploads", filename)
                if thumb_path.exists():
                    thumb_path.unlink()
                
                # Delete preview
                preview_path = get_preview_path(gallery_id, "Guest Uploads", filename)
                if preview_path.exists():
                    preview_path.unlink()
                
                # Delete from backup
                backup_file = get_backup_file_path(folder_name, "Guest Uploads", filename)
                if backup_file.exists():
                    backup_file.unlink()
                
                # Delete from database
                await db.files.delete_one({"id": file_id})
                total_deleted += 1
                
            except Exception as e:
                logger.warning(f"Guest cleanup: failed to delete {filename} in {folder_name}: {e}")
        
        # If Guest Uploads folder is now empty, remove the empty directories
        guest_dir = get_gallery_subfolder_path(folder_name, "Guest Uploads")
        if guest_dir.exists() and not any(guest_dir.iterdir()):
            guest_dir.rmdir()
        
        guest_cache = get_cache_subfolder_path(gallery_id, "Guest Uploads")
        if guest_cache.exists() and not any(guest_cache.iterdir()):
            guest_cache.rmdir()
        
        try:
            guest_backup = contained_path(
                BACKUP_DIR,
                folder_name,
                "Guest Uploads",
                labels=("backup gallery folder name", "backup subfolder"),
            )
        except UnsafePathError as exc:
            logger.warning(f"Guest cleanup: unsafe backup path for {folder_name}: {exc}")
            guest_backup = None
        if guest_backup and guest_backup.exists() and not any(guest_backup.iterdir()):
            guest_backup.rmdir()
        
        if total_deleted > 0:
            # Log activity
            await db.activity_log.insert_one({
                "action": "guest_cleanup",
                "gallery_id": gallery_id,
                "gallery_name": folder_name,
                "details": f"Auto-deleted {len(gallery_files)} guest upload(s) older than {GUEST_UPLOAD_MAX_AGE_DAYS} days",
                "timestamp": datetime.now(timezone.utc).isoformat()
            })
    
    if total_deleted > 0:
        logger.info(f"Guest upload cleanup: deleted {total_deleted} file(s) from {len(gallery_ids)} gallery(s)")
    
    return total_deleted

async def guest_upload_cleanup_loop():
    """Run guest upload cleanup once daily."""
    while True:
        try:
            deleted = await run_guest_upload_cleanup()
            if deleted > 0:
                logger.info(f"Daily guest upload cleanup: {deleted} file(s) removed")
        except Exception as e:
            logger.warning(f"Guest upload cleanup failed: {e}")
        await asyncio.sleep(86400)  # Check once every 24 hours


# ─── Auto-Expire Guest Upload Links (3 days after wedding date) ───
GUEST_UPLOAD_GRACE_DAYS = 3  # Expire at 00:01 on the 3rd day after the wedding

def _parse_wedding_date(folder_name: str):
    """Extract wedding date from folder name like 'Sarah & James 15.06.25' or '15/06/2025'."""
    import re
    match = re.search(r'(\d{1,2})[./](\d{1,2})[./](\d{2,4})$', folder_name.strip())
    if not match:
        return None
    try:
        day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
        if year < 100:
            year += 2000
        return datetime(year, month, day, tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None

async def run_guest_upload_link_expiry():
    """Deactivate guest upload share links 3 days after the wedding date."""
    now = datetime.now(timezone.utc)
    
    # Find all active guest upload shares
    guest_shares = await db.shares.find(
        {"is_active": True, "guest_upload_mode": True}, {"_id": 0}
    ).to_list(1000)
    
    expired_count = 0
    
    for share in guest_shares:
        gallery = await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0})
        if not gallery:
            continue
        
        wedding_date = _parse_wedding_date(gallery["folder_name"])
        if not wedding_date:
            continue  # Can't determine date, skip
        
        # Expire at 00:01 on the 3rd day after the wedding
        expiry_time = wedding_date + timedelta(days=GUEST_UPLOAD_GRACE_DAYS, minutes=1)
        
        if now >= expiry_time:
            # Deactivate the share
            await db.shares.update_one(
                {"id": share["id"]},
                {"$set": {"is_active": False, "auto_expired": True, "auto_expired_at": now.isoformat()}}
            )
            expired_count += 1
            
            logger.info(f"Auto-expired guest upload link for '{gallery['folder_name']}' (wedding: {wedding_date.strftime('%d/%m/%Y')}, expired: {expiry_time.strftime('%d/%m/%Y %H:%M')})")
            
            # Log activity
            await db.activity_log.insert_one({
                "action": "guest_link_expired",
                "gallery_id": share["gallery_id"],
                "gallery_name": gallery["folder_name"],
                "share_label": share.get("label", ""),
                "details": f"Guest upload link auto-expired ({GUEST_UPLOAD_GRACE_DAYS} days after wedding on {wedding_date.strftime('%d/%m/%Y')})",
                "timestamp": now.isoformat()
            })
    
    return expired_count

async def guest_upload_expiry_loop():
    """Check for expired guest upload links every hour."""
    while True:
        try:
            expired = await run_guest_upload_link_expiry()
            if expired > 0:
                logger.info(f"Guest upload expiry check: {expired} link(s) deactivated")
        except Exception as e:
            logger.warning(f"Guest upload expiry check failed: {e}")
        await asyncio.sleep(3600)  # Check every hour (to catch 00:01 accurately)



@app.on_event("startup")
async def startup_auto_archive():
    """Check for old logs on startup and archive if needed. Also start expiry reminder loop."""
    try:
        await run_auto_archive()
    except Exception as e:
        logger.warning(f"Auto-archive check failed: {e}")
    # Run expiry check once at startup
    try:
        await check_expiry_reminders()
    except Exception as e:
        logger.warning(f"Startup expiry reminder check failed: {e}")
    # Start daily background loop
    asyncio.create_task(expiry_reminder_loop())
    # Start network monitoring snapshots (every 15 minutes)
    asyncio.create_task(network_snapshot_loop())
    # Record initial network snapshot
    try:
        counters = psutil.net_io_counters()
        await db.network_snapshots.insert_one({
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    except Exception as e:
        logger.warning(f"Initial network snapshot failed: {e}")

    # Create indexes for performance
    try:
        await db.network_snapshots.create_index("timestamp")
        await db.bandwidth_log.create_index("timestamp")
        await db.bandwidth_log.create_index([("type", 1), ("timestamp", 1)])
        await db.activity_log.create_index("timestamp")
        await db.activity_log.create_index([("action", 1), ("timestamp", 1)])
        await db.files.create_index("gallery_id")
        await db.files.create_index([("gallery_id", 1), ("subfolder", 1)])
        await db.files.create_index([("gallery_id", 1), ("id", 1)])
        await db.shares.create_index("gallery_id")
        await db.shares.create_index("id")
        await db.shares.create_index("token", unique=True)
        await db.favourites.create_index([("session_id", 1), ("gallery_id", 1)])
        await db.favourites.create_index([("session_id", 1), ("file_id", 1)])
        await db.email_log.create_index("timestamp")
        await db.galleries.create_index("id", unique=True)
    except Exception as e:
        logger.warning(f"Index creation: {e}")


    # Start guest uploads auto-cleanup loop (90 days)
    asyncio.create_task(guest_upload_cleanup_loop())
    # Start guest upload link auto-expiry loop (3 days after wedding)
    asyncio.create_task(guest_upload_expiry_loop())


app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_noindex_header(request, call_next):
    response = await call_next(request)
    response.headers["X-Robots-Tag"] = "noindex, nofollow, noarchive, nosnippet"
    return response


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
