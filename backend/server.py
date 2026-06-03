from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Depends, Form, Query, Header, Request
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
import numpy as np
import bcrypt
from PIL import Image
import aiofiles
import qrcode
import threading
from concurrent.futures import ThreadPoolExecutor
import pyotp
import base64

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

class GalleryUpdate(BaseModel):
    folder_name: Optional[str] = None

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
    return payload

# ─── File Helpers ───
def is_image(filename: str) -> bool:
    return filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'))

def is_video(filename: str) -> bool:
    return filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm', '.mts'))

def is_share_expired(share: dict) -> bool:
    """Check if a share has expired based on expires_at date."""
    if not share.get("is_active"):
        return True
    expires_at = share.get("expires_at")
    if not expires_at:
        return False
    try:
        expiry_date = datetime.fromisoformat(expires_at.replace('Z', '+00:00'))
        return datetime.now(timezone.utc) > expiry_date
    except (ValueError, TypeError):
        return False

def slugify(text: str) -> str:
    return text.lower().strip().replace(' ', '-').replace('&', 'and')

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
    return UPLOAD_DIR / folder_name

def get_thumb_path(gallery_id: str, subfolder: str, filename: str) -> Path:
    return CACHE_DIR / gallery_id / slugify(subfolder) / f"{Path(filename).stem}.thumb.jpg"

def get_preview_path(gallery_id: str, subfolder: str, filename: str) -> Path:
    return CACHE_DIR / gallery_id / slugify(subfolder) / f"{Path(filename).stem}.preview.jpg"

def safe_filename(filename: str, existing_dir: Path) -> str:
    """Keep original filename, append (1), (2) etc if duplicate."""
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
thumbnail_executor = ThreadPoolExecutor(max_workers=4)

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
    doc = {
        "id": str(uuid.uuid4()),
        "name": data.name,
        "subfolders": data.subfolders,
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
        update["subfolders"] = data.subfolders
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
    # Get template subfolders
    subfolders = list(DEFAULT_SUBFOLDERS)
    if data.template_id:
        tmpl = await db.templates.find_one({"id": data.template_id}, {"_id": 0})
        if tmpl:
            subfolders = tmpl["subfolders"]

    gallery_id = str(uuid.uuid4())
    folder_path = get_gallery_path(data.folder_name)

    # Create physical folders
    for sf in subfolders:
        (folder_path / sf).mkdir(parents=True, exist_ok=True)

    doc = {
        "id": gallery_id,
        "folder_name": data.folder_name,
        "subfolders": subfolders,
        "template_id": data.template_id,
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
    # Enrich with share count + first image for cover
    for g in galleries:
        share_count = await db.shares.count_documents({"gallery_id": g["id"]})
        g["share_count"] = share_count
        first_file = await db.files.find_one(
            {"gallery_id": g["id"], "file_type": "photo"},
            {"_id": 0}
        )
        g["cover_thumb"] = None
        if first_file:
            tp = get_thumb_path(g["id"], first_file["subfolder"], first_file["filename"])
            if tp.exists():
                g["cover_thumb"] = f"/api/media/thumb/{g['id']}/{slugify(first_file['subfolder'])}/{Path(first_file['filename']).stem}.thumb.jpg"
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
        old_path = get_gallery_path(gallery["folder_name"])
        new_path = get_gallery_path(data.folder_name)
        if old_path.exists():
            old_path.rename(new_path)
        update["folder_name"] = data.folder_name
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
    folder_path = get_gallery_path(gallery["folder_name"]) / subfolder_name
    if folder_path.exists():
        shutil.rmtree(folder_path)
    # Delete cached thumbs
    cache_path = CACHE_DIR / gallery_id / slugify(subfolder_name)
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
async def delete_gallery(gallery_id: str, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    folder_path = get_gallery_path(gallery["folder_name"])
    if folder_path.exists():
        shutil.rmtree(folder_path)
    cache_path = CACHE_DIR / gallery_id
    if cache_path.exists():
        shutil.rmtree(cache_path)
    await db.files.delete_many({"gallery_id": gallery_id})
    await db.shares.delete_many({"gallery_id": gallery_id})
    await db.favourites.delete_many({"gallery_id": gallery_id})
    await db.galleries.delete_one({"id": gallery_id})
    return {"success": True}

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

    target_dir = get_gallery_path(gallery["folder_name"]) / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for file in files:
        # Stream file to disk for large file support
        final_name = safe_filename(file.filename, target_dir)
        file_path = target_dir / final_name
        file_size = 0

        async with aiofiles.open(file_path, 'wb') as f:
            while True:
                chunk = await file.read(1024 * 1024)  # 1MB chunks
                if not chunk:
                    break
                await f.write(chunk)
                file_size += len(chunk)

        file_type = "photo" if is_image(file.filename) else "video" if is_video(file.filename) else "other"
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
    return {"uploaded": uploaded, "count": len(uploaded)}

@api_router.delete("/admin/galleries/{gallery_id}/files/{file_id}")
async def delete_file(gallery_id: str, file_id: str, admin=Depends(get_admin)):
    f = await db.files.find_one({"id": file_id, "gallery_id": gallery_id}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    # Delete physical file
    file_path = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
    if file_path.exists():
        file_path.unlink()
    # Delete thumbnails
    for tp in [get_thumb_path(gallery_id, f["subfolder"], f["filename"]),
               get_preview_path(gallery_id, f["subfolder"], f["filename"])]:
        if tp.exists():
            tp.unlink()

    await db.files.delete_one({"id": file_id})
    await db.favourites.delete_many({"file_id": file_id})

    count = await db.files.count_documents({"gallery_id": gallery_id, "subfolder": f["subfolder"]})
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {f"file_counts.{f['subfolder']}": count}}
    )
    return {"success": True}

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

    target_dir = get_gallery_path(gallery["folder_name"]) / data.target_subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    copied = 0

    for file_id in data.file_ids:
        f = await db.files.find_one({"id": file_id, "gallery_id": gallery_id}, {"_id": 0})
        if not f:
            continue
        src_path = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
        if not src_path.exists():
            continue
        dest_name = safe_filename(f["filename"], target_dir)
        dest_path = target_dir / dest_name
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
    folder_path = get_gallery_path(gallery["folder_name"]) / subfolder
    if not folder_path.exists():
        raise HTTPException(status_code=404, detail="Subfolder not found")

    files = await db.files.find({"gallery_id": gallery_id, "subfolder": subfolder}, {"_id": 0}).to_list(50000)
    if not files:
        raise HTTPException(status_code=404, detail="No files in this subfolder")

    def iter_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for f in files:
                fp = folder_path / f["filename"]
                if fp.exists():
                    zf.write(fp, f["filename"])
        buf.seek(0)
        while True:
            chunk = buf.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            yield chunk

    zip_name = f"{gallery['folder_name']} - {subfolder}.zip".replace(' ', '_')
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
    file_path = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
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
    result = {k: v for k, v in share_doc.items() if k not in ("_id", "password_hash")}
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
    """Generate elegant QR code frame with couple name. Designs: 1=Floral, 2=Wavy Border, 3=Elegant Minimal."""
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
        # ── FLORAL ── Fresh canvas, flowers FIRST, then text/QR on top
        BG = (250, 248, 244)
        img = Image.new('RGB', (FW, FH), BG)
        
        # Step 1: Paste flower decorations FIRST (so text renders on top)
        tmpl = Image.open(str(TEMPLATES_DIR / "original_floral_cream.png")).convert('RGB')
        tw, th = tmpl.size
        
        # Top-right flowers: crop the densest flower area from template corner
        tr_crop = tmpl.crop((int(tw * 0.55), 0, tw, int(th * 0.45)))
        # Scale to ~25% of output — compact corner placement
        tr_w = int(FW * 0.25)
        tr_h = int(FH * 0.25)
        tr_scaled = tr_crop.resize((tr_w, tr_h), Image.LANCZOS).convert('RGBA')
        tr_arr = np.array(tr_scaled)
        # Targeted cream removal: only remove pixels where R>235 AND G>230 AND B>220
        # This preserves pinks (high R, low B) and greens (low R, high G)
        bg_mask = (tr_arr[:,:,0] > 235) & (tr_arr[:,:,1] > 230) & (tr_arr[:,:,2] > 220)
        tr_arr[bg_mask, 3] = 0
        tr_final = Image.fromarray(tr_arr)
        img.paste(tr_final, (FW - tr_w, 0), tr_final)
        
        # Bottom-left flowers: crop the densest flower area
        bl_crop = tmpl.crop((0, int(th * 0.55), int(tw * 0.45), th))
        bl_w = int(FW * 0.25)
        bl_h = int(FH * 0.25)
        bl_scaled = bl_crop.resize((bl_w, bl_h), Image.LANCZOS).convert('RGBA')
        bl_arr = np.array(bl_scaled)
        bg_mask = (bl_arr[:,:,0] > 235) & (bl_arr[:,:,1] > 230) & (bl_arr[:,:,2] > 220)
        bl_arr[bg_mask, 3] = 0
        bl_final = Image.fromarray(bl_arr)
        img.paste(bl_final, (0, FH - bl_h), bl_final)
        
        # Step 2: Draw all text and QR ON TOP of flowers
        draw = ImageDraw.Draw(img)
        
        # Heading
        tc(draw, "CAPTURE", serif_bf(int(55 * SX)), int(FH * 0.20), fill='#2C2C2C')
        tc(draw, "the love", script_f(int(65 * SX)), int(FH * 0.28), fill='#2C2C2C')
        
        # QR code
        qr_size = int(FW * 0.27)
        qr_img = make_qr_img(share_url, qr_size)
        qr_x = (FW - qr_size) // 2
        qr_y = int(FH * 0.47) - qr_size // 2
        draw.rectangle([qr_x - 4, qr_y - 4, qr_x + qr_size + 4, qr_y + qr_size + 4], outline='#D0CCC4', width=2)
        img.paste(qr_img, (qr_x, qr_y))
        draw = ImageDraw.Draw(img)
        
        # Instructions
        tc(draw, "Please share your photos with us!", sans_f(int(18 * SX)), int(FH * 0.67), fill='#555555')
        tc(draw, "Simply scan the QR code & upload.", sans_f(int(15 * SX)), int(FH * 0.70), fill='#777777')
        
        # Couple name (gold script)
        tc(draw, couple_name, script_f(int(48 * SX)), int(FH * 0.77), fill='#8B7536')
        
        # Date
        if date_str:
            tc(draw, date_str, serif_f(int(20 * SX)), int(FH * 0.85), fill='#555555')
        
        add_brand(draw)

    elif design == 2:
        # ── WAVY ── Fresh canvas + wavy border from original
        img = Image.new('RGB', (FW, FH), (255, 255, 255))
        draw = ImageDraw.Draw(img)
        
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
        
        # NOW overlay wavy border + decorations from original (edges only)
        tmpl = Image.open(str(TEMPLATES_DIR / "original_wavy.png")).convert('RGBA').resize((FW, FH), Image.LANCZOS)
        bw = int(FW * 0.06)  # border strip width
        bh = int(FH * 0.06)
        # Top
        top = tmpl.crop((0, 0, FW, bh))
        img.paste(top, (0, 0), top)
        # Bottom
        bot = tmpl.crop((0, FH - bh, FW, FH))
        img.paste(bot, (0, FH - bh), bot)
        # Left
        left = tmpl.crop((0, bh, bw, FH - bh))
        img.paste(left, (0, bh), left)
        # Right
        right = tmpl.crop((FW - bw, bh, FW, FH - bh))
        img.paste(right, (FW - bw, bh), right)
        # Top-left hearts decoration
        tl = tmpl.crop((0, 0, int(FW * 0.18), int(FH * 0.22)))
        img.paste(tl, (0, 0), tl)
        # Bottom-right heart decoration
        br = tmpl.crop((int(FW * 0.82), int(FH * 0.85), FW, FH))
        img.paste(br, (int(FW * 0.82), int(FH * 0.85)), br)
        # Camera icon from template
        cam = tmpl.crop((int(FW * 0.44), int(FH * 0.10), int(FW * 0.56), int(FH * 0.20)))
        img.paste(cam, (int(FW * 0.44), int(FH * 0.10)), cam)

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
    design_names = {1: "Floral", 2: "Wavy", 3: "Minimal"}
    
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

    if design_num not in (1, 2, 3):
        design_num = 1

    if design_num in _qr_preview_cache:
        buf = io.BytesIO(_qr_preview_cache[design_num])
        return StreamingResponse(buf, media_type="image/png")

    TEMPLATES_DIR = ROOT_DIR / "assets" / "qr_templates"
    names = {1: "design_1_floral.png", 2: "design_2_wavy.png", 3: "design_3_minimal.png"}
    img = Image.open(str(TEMPLATES_DIR / names[design_num])).convert('RGB')
    thumb = img.resize((480, 360), Image.LANCZOS)
    buf = io.BytesIO()
    thumb.save(buf, format="PNG", optimize=True)
    _qr_preview_cache[design_num] = buf.getvalue()
    buf.seek(0)
    return StreamingResponse(buf, media_type="image/png")

# ─── Media Serving ───
@api_router.get("/media/thumb/{gallery_id}/{subfolder_slug}/{filename}")
async def serve_thumb(gallery_id: str, subfolder_slug: str, filename: str):
    file_path = CACHE_DIR / gallery_id / subfolder_slug / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Thumbnail not found")
    return FileResponse(file_path, media_type="image/jpeg")

@api_router.get("/media/preview/{gallery_id}/{subfolder_slug}/{filename}")
async def serve_preview(gallery_id: str, subfolder_slug: str, filename: str):
    file_path = CACHE_DIR / gallery_id / subfolder_slug / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Preview not found")
    return FileResponse(file_path, media_type="image/jpeg")

@api_router.get("/media/original/{gallery_id}/{subfolder}/{filename}")
async def serve_original(gallery_id: str, subfolder: str, filename: str):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    file_path = get_gallery_path(gallery["folder_name"]) / subfolder / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

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
        # All subfolders except Guest Uploads for gallery shares
        subfolders_data = []
        for sf in gallery["subfolders"]:
            sf_files = await db.files.find({"gallery_id": gallery_id, "subfolder": sf}, {"_id": 0}).sort("uploaded_at", 1).to_list(50000)
            subfolders_data.append({"name": sf, "files": sf_files})

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
    
    target_dir = get_gallery_path(gallery["folder_name"]) / target_subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    
    copied = 0
    already_exists = 0
    
    for fav in favs:
        f = await db.files.find_one({"id": fav["file_id"], "gallery_id": gallery_id}, {"_id": 0})
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
        
        src_path = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
        if not src_path.exists():
            continue
        
        dest_name = safe_filename(f["filename"], target_dir)
        dest_path = target_dir / dest_name
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


@api_router.get("/share/{token}/download/{file_id}")
async def download_share_file(token: str, file_id: str, request: Request, session=Depends(get_share_session)):
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    # Enforce download permission
    if not session.get("allow_downloads", False):
        raise HTTPException(status_code=403, detail="Downloads not allowed on this share")
    f = await db.files.find_one({"id": file_id, "gallery_id": session["gallery_id"]}, {"_id": 0})
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    gallery = await db.galleries.find_one({"id": session["gallery_id"]}, {"_id": 0})
    file_path = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found on disk")
    
    # Log detailed download
    client_ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    await _log_download(session["gallery_id"], gallery.get("folder_name", "Unknown"),
                        share.get("label", token) if share else token, client_ip,
                        "single", [f["filename"]], f["subfolder"], 1, 1)
    
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
        query = {"gallery_id": gallery_id, "id": {"$in": file_ids}}
    else:
        query = {"gallery_id": gallery_id}
        if subfolder:
            query["subfolder"] = subfolder
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
    def iter_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for f in files:
                fp = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
                if fp.exists():
                    arcname = f"{f['subfolder']}/{f['filename']}"
                    zf.write(fp, arcname)
        buf.seek(0)
        while True:
            chunk = buf.read(1024 * 1024)  # 1MB chunks
            if not chunk:
                break
            yield chunk

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
    payload = verify_jwt(jwt_token)
    if not payload or payload.get("role") != "share" or payload.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    if not payload.get("allow_downloads", False):
        raise HTTPException(status_code=403, detail="Downloads not allowed")
    
    gallery_id = payload["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    
    query = {"gallery_id": gallery_id}
    if subfolder:
        query["subfolder"] = subfolder
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

    def iter_zip():
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for f in files:
                fp = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
                if fp.exists():
                    arcname = f["filename"] if subfolder else f"{f['subfolder']}/{f['filename']}"
                    zf.write(fp, arcname)
        buf.seek(0)
        while True:
            chunk = buf.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    folder_name = subfolder if subfolder else gallery['folder_name']
    zip_name = f"{folder_name.replace(' ', '_')}.zip"
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
    payload = verify_jwt(jwt_token)
    if not payload or payload.get("role") != "share" or payload.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
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
    files = await db.files.find({"gallery_id": gallery_id, "id": {"$in": fav_ids}}, {"_id": 0}).to_list(50000)
    
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
        with zipfile.ZipFile(buf, 'w', zipfile.ZIP_STORED) as zf:
            for f in files:
                fp = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
                if fp.exists():
                    zf.write(fp, f["filename"])
        buf.seek(0)
        while True:
            chunk = buf.read(1024 * 1024)
            if not chunk:
                break
            yield chunk

    zip_name = f"{gallery['folder_name'].replace(' ', '_')}_favourites.zip"
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
    target_dir = get_gallery_path(gallery["folder_name"]) / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)
    
    # Only check compression setting for non-photographer uploads
    compression_enabled = False if is_photographer_mode else await get_compression_setting()

    uploaded = []
    skipped_too_large = []
    for file in files:
        if is_photographer_mode:
            # PHOTOGRAPHER MODE: Stream directly to disk, preserve original filename, no size limit
            original_name = file.filename or "unnamed_file"
            # Preserve original filename but handle duplicates
            final_name = original_name
            file_path = target_dir / final_name
            counter = 1
            while file_path.exists():
                stem = Path(original_name).stem
                suffix = Path(original_name).suffix
                final_name = f"{stem}_{counter}{suffix}"
                file_path = target_dir / final_name
                counter += 1

            # Stream directly to disk in chunks - no memory buffering
            file_size = 0
            async with aiofiles.open(file_path, 'wb') as f_out:
                while True:
                    chunk = await file.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        break
                    await f_out.write(chunk)
                    file_size += len(chunk)

            file_type = "photo" if is_image(file.filename) else "video" if is_video(file.filename) else "other"
            
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
            # GUEST MODE: Original behaviour with memory read, size limit, compression
            content = await file.read()
            # Enforce 500MB limit for guest uploads
            if len(content) > MAX_GUEST_UPLOAD_SIZE:
                skipped_too_large.append(file.filename)
                continue

            final_name = safe_filename(file.filename, target_dir)
            file_path = target_dir / final_name
            async with aiofiles.open(file_path, 'wb') as f_out:
                await f_out.write(content)

            file_type = "photo" if is_image(file.filename) else "video" if is_video(file.filename) else "other"
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
                "file_size": len(content),
                "has_thumb": has_thumb,
                "has_preview": has_preview,
                "uploaded_by": "guest",
                "uploaded_at": datetime.now(timezone.utc).isoformat()
            }
            await db.files.insert_one(file_doc)
            uploaded.append({k: v for k, v in file_doc.items() if k != "_id"})
            
            # Schedule background compression for large guest videos if enabled
            if compression_enabled and file_type == "video" and len(content) > VIDEO_COMPRESSION_SIZE_THRESHOLD:
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
        f = await db.files.find_one({"id": file_id, "gallery_id": gallery_id}, {"_id": 0})
        if not f:
            continue
        # Delete physical file
        file_path = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
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

@api_router.get("/admin/activity")
async def get_admin_activity(limit: int = Query(50, le=200), gallery_id: str = Query(None), action: str = Query(None), admin=Depends(get_admin)):
    """Get recent activity across all galleries, optionally filtered."""
    query = {}
    if gallery_id:
        query["gallery_id"] = gallery_id
    if action:
        query["action"] = action
    activities = await db.activity_log.find(
        query, {"_id": 0}
    ).sort("timestamp", -1).limit(limit).to_list(limit)
    return {"activities": activities}

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
            backup_gallery_path = BACKUP_DIR / gallery_folder.name
            backup_gallery_path.mkdir(parents=True, exist_ok=True)
            
            # Walk through all subfolders and files
            for src_path in gallery_folder.rglob("*"):
                if src_path.is_file():
                    # Skip thumbnail/preview files
                    if '.thumb.' in src_path.name or '.preview.' in src_path.name:
                        continue
                    
                    # Calculate relative path and destination
                    rel_path = src_path.relative_to(gallery_folder)
                    dst_path = backup_gallery_path / rel_path
                    
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
    Uses H.264 codec with CRF 23 (visually lossless) and same resolution.
    """
    try:
        cmd = [
            'ffmpeg', '-y', '-i', str(input_path),
            '-c:v', 'libx264',      # H.264 codec (universal compatibility)
            '-crf', '23',           # Quality setting (18-23 is visually lossless)
            '-preset', 'medium',    # Balance between speed and compression
            '-c:a', 'aac',          # Audio codec
            '-b:a', '128k',         # Audio bitrate
            '-movflags', '+faststart',  # Enable streaming
            str(output_path)
        ]
        result = subprocess.run(cmd, capture_output=True, timeout=600)  # 10 min timeout
        return result.returncode == 0
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

app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
