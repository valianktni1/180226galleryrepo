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
import bcrypt
from PIL import Image
import aiofiles
import qrcode

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
MAX_LOGIN_ATTEMPTS = 5
LOGIN_WINDOW_SECONDS = 300  # 5 minutes

# Session timeout (24 hours for admin, 72 hours for share access)
ADMIN_SESSION_HOURS = 24
SHARE_SESSION_HOURS = 72
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 48
MAX_UPLOAD_SIZE = 40 * 1024 * 1024 * 1024  # 40GB for admin

app = FastAPI()
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

DEFAULT_SUBFOLDERS = ["Wedding Images", "Video", "SelfieBooth", "Album Favourites", "Guest Uploads"]

# ─── Models ───
class AdminLogin(BaseModel):
    username: str
    password: str

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

class FavouriteToggle(BaseModel):
    file_id: str

class ShareAccessBody(BaseModel):
    password: str

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

# ─── Auth Helpers ───
def create_jwt(data: dict, expires_hours: int = JWT_EXPIRY_HOURS) -> str:
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
async def admin_login(data: AdminLogin):
    admin = await db.admins.find_one({"username": data.username}, {"_id": 0})
    if not admin:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if not bcrypt.checkpw(data.password.encode(), admin["password"].encode()):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_jwt({"sub": admin["id"], "role": "admin", "username": data.username})
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
async def list_galleries(admin=Depends(get_admin)):
    galleries = await db.galleries.find({}, {"_id": 0}).sort("created_at", -1).to_list(1000)
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

        # Generate thumbnails for images
        has_thumb = False
        has_preview = False
        if file_type == "photo":
            thumb_p = get_thumb_path(gallery_id, subfolder, final_name)
            preview_p = get_preview_path(gallery_id, subfolder, final_name)
            has_thumb = make_thumbnail(file_path, thumb_p)
            has_preview = make_preview(file_path, preview_p)

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
            "uploaded_by": "admin",
            "uploaded_at": datetime.now(timezone.utc).isoformat()
        }
        await db.files.insert_one(file_doc)
        uploaded.append({k: v for k, v in file_doc.items() if k != "_id"})

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

    session_id = str(uuid.uuid4())
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
    return {"jwt": jwt_token, "gallery_name": (await db.galleries.find_one({"id": share["gallery_id"]}, {"_id": 0}))["folder_name"]}

@api_router.get("/share/{token}/open-access")
async def open_access_share(token: str):
    """For shares without password - get JWT directly."""
    share = await db.shares.find_one({"token": token}, {"_id": 0})
    if not share:
        raise HTTPException(status_code=404, detail="Share not found")
    if is_share_expired(share):
        raise HTTPException(status_code=410, detail="This share link has expired")
    if share.get("has_password"):
        raise HTTPException(status_code=401, detail="Password required")
    session_id = str(uuid.uuid4())
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
    return {"jwt": jwt_token, "gallery_name": gallery["folder_name"] if gallery else ""}

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

    return {
        "gallery_id": gallery_id,
        "gallery_name": gallery["folder_name"],
        "subfolders": subfolders_data,
        "access_level": session.get("access_level", "download"),
        "allow_uploads": session.get("allow_uploads", False),
        "allow_downloads": session.get("allow_downloads", True),
        "allow_delete": session.get("allow_delete", False)
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

@api_router.get("/share/{token}/download/{file_id}")
async def download_share_file(token: str, file_id: str, session=Depends(get_share_session)):
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
    return FileResponse(file_path, filename=f["filename"], media_type="application/octet-stream")

@api_router.post("/share/{token}/download-zip")
async def download_share_zip(token: str, file_ids: List[str] = [], session=Depends(get_share_session)):
    if session.get("token") != token:
        raise HTTPException(status_code=403, detail="Access denied")
    # Enforce download permission
    if not session.get("allow_downloads", False):
        raise HTTPException(status_code=403, detail="Downloads not allowed on this share")
    gallery_id = session["gallery_id"]
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    if file_ids:
        query = {"gallery_id": gallery_id, "id": {"$in": file_ids}}
    else:
        subfolder = session.get("subfolder")
        query = {"gallery_id": gallery_id}
        if subfolder:
            query["subfolder"] = subfolder
    files = await db.files.find(query, {"_id": 0}).to_list(50000)

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            fp = get_gallery_path(gallery["folder_name"]) / f["subfolder"] / f["filename"]
            if fp.exists():
                arcname = f"{f['subfolder']}/{f['filename']}"
                zf.write(fp, arcname)
    zip_buffer.seek(0)
    zip_name = f"{gallery['folder_name'].replace(' ', '_')}.zip"
    return StreamingResponse(zip_buffer, media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'})

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

    subfolder = session.get("subfolder") or "Guest Uploads"
    target_dir = get_gallery_path(gallery["folder_name"]) / subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    uploaded = []
    for file in files:
        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
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

    count = await db.files.count_documents({"gallery_id": gallery_id, "subfolder": subfolder})
    await db.galleries.update_one(
        {"id": gallery_id},
        {"$set": {f"file_counts.{subfolder}": count}}
    )
    return {"uploaded": uploaded, "count": len(uploaded)}

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
