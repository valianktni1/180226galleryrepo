from fastapi import FastAPI, APIRouter, UploadFile, File, HTTPException, Depends, Form, Query, Header
from fastapi.responses import FileResponse, StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import io
import logging
import shutil
import zipfile
import hashlib
import secrets
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone, timedelta
import jwt
import bcrypt
from PIL import Image
import aiofiles

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# File storage config
UPLOAD_DIR = Path(os.environ.get('UPLOAD_DIR', '/app/uploads'))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# JWT config
JWT_SECRET = os.environ.get('JWT_SECRET', secrets.token_hex(32))
JWT_ALGORITHM = "HS256"
JWT_EXPIRY_HOURS = 24

# Max upload size (100MB)
MAX_UPLOAD_SIZE = 100 * 1024 * 1024

app = FastAPI()
api_router = APIRouter(prefix="/api")

# ─── Models ───
class AdminLogin(BaseModel):
    username: str
    password: str

class AdminSetup(BaseModel):
    username: str
    password: str
    display_name: str = "Weddings By Mark"

class GalleryCreate(BaseModel):
    title: str
    couple_names: str
    wedding_date: str
    password: str
    description: Optional[str] = ""
    is_active: bool = True

class GalleryUpdate(BaseModel):
    title: Optional[str] = None
    couple_names: Optional[str] = None
    wedding_date: Optional[str] = None
    password: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    cover_photo_id: Optional[str] = None

class ClientAccess(BaseModel):
    password: str

class FavouriteToggle(BaseModel):
    photo_id: str

# ─── Helpers ───
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

async def get_client_session(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = authorization.replace("Bearer ", "")
    payload = verify_jwt(token)
    if payload.get("role") != "client":
        raise HTTPException(status_code=403, detail="Not a client session")
    return payload

def generate_slug(title: str) -> str:
    slug = title.lower().strip()
    slug = ''.join(c if c.isalnum() or c == ' ' else '' for c in slug)
    slug = '-'.join(slug.split())
    return slug

def make_thumbnail(input_path: Path, output_path: Path, size=(400, 400)):
    try:
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail(size, Image.LANCZOS)
            img.save(output_path, "JPEG", quality=85)
        return True
    except Exception as e:
        logger.error(f"Thumbnail error: {e}")
        return False

def make_preview(input_path: Path, output_path: Path, size=(1200, 1200)):
    try:
        with Image.open(input_path) as img:
            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')
            img.thumbnail(size, Image.LANCZOS)
            img.save(output_path, "JPEG", quality=90)
        return True
    except Exception as e:
        logger.error(f"Preview error: {e}")
        return False

def is_image(filename: str) -> bool:
    return filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp', '.bmp', '.tiff'))

def is_video(filename: str) -> bool:
    return filename.lower().endswith(('.mp4', '.mov', '.avi', '.mkv', '.webm'))

# ─── Admin Auth Routes ───
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

@api_router.get("/admin/me")
async def admin_me(admin=Depends(get_admin)):
    admin_doc = await db.admins.find_one({"id": admin["sub"]}, {"_id": 0, "password": 0})
    return admin_doc

# ─── Gallery CRUD ───
@api_router.post("/admin/galleries")
async def create_gallery(data: GalleryCreate, admin=Depends(get_admin)):
    slug = generate_slug(data.title)
    existing = await db.galleries.find_one({"slug": slug})
    if existing:
        slug = f"{slug}-{secrets.token_hex(3)}"
    hashed_pw = bcrypt.hashpw(data.password.encode(), bcrypt.gensalt()).decode()
    gallery_doc = {
        "id": str(uuid.uuid4()),
        "title": data.title,
        "slug": slug,
        "couple_names": data.couple_names,
        "wedding_date": data.wedding_date,
        "description": data.description or "",
        "password": hashed_pw,
        "is_active": data.is_active,
        "cover_photo_id": None,
        "photo_count": 0,
        "video_count": 0,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat()
    }
    gallery_dir = UPLOAD_DIR / "galleries" / gallery_doc["id"]
    (gallery_dir / "originals").mkdir(parents=True, exist_ok=True)
    (gallery_dir / "thumbnails").mkdir(parents=True, exist_ok=True)
    (gallery_dir / "previews").mkdir(parents=True, exist_ok=True)
    await db.galleries.insert_one(gallery_doc)
    result = {k: v for k, v in gallery_doc.items() if k not in ("_id", "password")}
    return result

@api_router.get("/admin/galleries")
async def list_galleries(admin=Depends(get_admin)):
    galleries = await db.galleries.find({}, {"_id": 0, "password": 0}).sort("created_at", -1).to_list(1000)
    return galleries

@api_router.get("/admin/galleries/{gallery_id}")
async def get_gallery(gallery_id: str, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    result = {k: v for k, v in gallery.items() if k != "password"}
    photos = await db.photos.find({"gallery_id": gallery_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(10000)
    result["photos"] = photos
    return result

@api_router.put("/admin/galleries/{gallery_id}")
async def update_gallery(gallery_id: str, data: GalleryUpdate, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    update = {"updated_at": datetime.now(timezone.utc).isoformat()}
    for field, value in data.model_dump(exclude_unset=True).items():
        if value is not None:
            if field == "password":
                update["password"] = bcrypt.hashpw(value.encode(), bcrypt.gensalt()).decode()
            elif field == "title":
                update["title"] = value
                update["slug"] = generate_slug(value)
            else:
                update[field] = value
    await db.galleries.update_one({"id": gallery_id}, {"$set": update})
    updated = await db.galleries.find_one({"id": gallery_id}, {"_id": 0, "password": 0})
    return updated

@api_router.delete("/admin/galleries/{gallery_id}")
async def delete_gallery(gallery_id: str, admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    gallery_dir = UPLOAD_DIR / "galleries" / gallery_id
    if gallery_dir.exists():
        shutil.rmtree(gallery_dir)
    await db.photos.delete_many({"gallery_id": gallery_id})
    await db.favourites.delete_many({"gallery_id": gallery_id})
    await db.galleries.delete_one({"id": gallery_id})
    return {"success": True}

# ─── Photo Upload & Management ───
@api_router.post("/admin/galleries/{gallery_id}/upload")
async def upload_photos(gallery_id: str, files: List[UploadFile] = File(...), admin=Depends(get_admin)):
    gallery = await db.galleries.find_one({"id": gallery_id})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")

    gallery_dir = UPLOAD_DIR / "galleries" / gallery_id
    (gallery_dir / "originals").mkdir(parents=True, exist_ok=True)
    (gallery_dir / "thumbnails").mkdir(parents=True, exist_ok=True)
    (gallery_dir / "previews").mkdir(parents=True, exist_ok=True)

    uploaded = []
    photo_inc = 0
    video_inc = 0
    for file in files:
        file_id = str(uuid.uuid4())
        ext = Path(file.filename).suffix.lower()
        safe_name = f"{file_id}{ext}"
        original_path = gallery_dir / "originals" / safe_name

        content = await file.read()
        if len(content) > MAX_UPLOAD_SIZE:
            continue

        async with aiofiles.open(original_path, 'wb') as f:
            await f.write(content)

        file_type = "photo" if is_image(file.filename) else "video" if is_video(file.filename) else "other"
        thumb_path = None
        preview_path = None

        if file_type == "photo":
            thumb_name = f"{file_id}.jpg"
            preview_name = f"{file_id}.jpg"
            t_path = gallery_dir / "thumbnails" / thumb_name
            p_path = gallery_dir / "previews" / preview_name
            if make_thumbnail(original_path, t_path):
                thumb_path = f"thumbnails/{thumb_name}"
            if make_preview(original_path, p_path):
                preview_path = f"previews/{preview_name}"
            photo_inc += 1
        elif file_type == "video":
            video_inc += 1

        photo_doc = {
            "id": file_id,
            "gallery_id": gallery_id,
            "filename": file.filename,
            "safe_name": safe_name,
            "file_type": file_type,
            "file_size": len(content),
            "original_path": f"originals/{safe_name}",
            "thumbnail_path": thumb_path,
            "preview_path": preview_path,
            "uploaded_at": datetime.now(timezone.utc).isoformat(),
            "sort_order": 0
        }
        await db.photos.insert_one(photo_doc)
        result = {k: v for k, v in photo_doc.items() if k != "_id"}
        uploaded.append(result)

    await db.galleries.update_one({"id": gallery_id}, {
        "$inc": {"photo_count": photo_inc, "video_count": video_inc}
    })

    if not gallery.get("cover_photo_id") and uploaded:
        first_photo = next((p for p in uploaded if p["file_type"] == "photo"), None)
        if first_photo:
            await db.galleries.update_one({"id": gallery_id}, {"$set": {"cover_photo_id": first_photo["id"]}})

    return {"uploaded": uploaded, "count": len(uploaded)}

@api_router.delete("/admin/galleries/{gallery_id}/photos/{photo_id}")
async def delete_photo(gallery_id: str, photo_id: str, admin=Depends(get_admin)):
    photo = await db.photos.find_one({"id": photo_id, "gallery_id": gallery_id}, {"_id": 0})
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    gallery_dir = UPLOAD_DIR / "galleries" / gallery_id
    for path_key in ["original_path", "thumbnail_path", "preview_path"]:
        if photo.get(path_key):
            fp = gallery_dir / photo[path_key]
            if fp.exists():
                fp.unlink()

    await db.photos.delete_one({"id": photo_id})
    await db.favourites.delete_many({"photo_id": photo_id})

    dec_field = "photo_count" if photo["file_type"] == "photo" else "video_count"
    await db.galleries.update_one({"id": gallery_id}, {"$inc": {dec_field: -1}})

    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    if gallery and gallery.get("cover_photo_id") == photo_id:
        next_photo = await db.photos.find_one({"gallery_id": gallery_id, "file_type": "photo"}, {"_id": 0})
        new_cover = next_photo["id"] if next_photo else None
        await db.galleries.update_one({"id": gallery_id}, {"$set": {"cover_photo_id": new_cover}})

    return {"success": True}

# ─── Media Serving ───
@api_router.get("/media/{gallery_id}/{path_type}/{filename}")
async def serve_media(gallery_id: str, path_type: str, filename: str):
    if path_type not in ("originals", "thumbnails", "previews"):
        raise HTTPException(status_code=400, detail="Invalid path type")
    file_path = UPLOAD_DIR / "galleries" / gallery_id / path_type / filename
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path)

# ─── Client Gallery Access ───
@api_router.get("/galleries/{slug}")
async def get_gallery_info(slug: str):
    gallery = await db.galleries.find_one({"slug": slug, "is_active": True}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    cover_url = None
    if gallery.get("cover_photo_id"):
        cover = await db.photos.find_one({"id": gallery["cover_photo_id"]}, {"_id": 0})
        if cover and cover.get("preview_path"):
            cover_url = f"/api/media/{gallery['id']}/{cover['preview_path']}"
    return {
        "title": gallery["title"],
        "couple_names": gallery["couple_names"],
        "wedding_date": gallery["wedding_date"],
        "description": gallery.get("description", ""),
        "cover_url": cover_url,
        "photo_count": gallery.get("photo_count", 0),
        "video_count": gallery.get("video_count", 0)
    }

@api_router.post("/galleries/{slug}/access")
async def access_gallery(slug: str, data: ClientAccess):
    gallery = await db.galleries.find_one({"slug": slug, "is_active": True}, {"_id": 0})
    if not gallery:
        raise HTTPException(status_code=404, detail="Gallery not found")
    if not bcrypt.checkpw(data.password.encode(), gallery["password"].encode()):
        raise HTTPException(status_code=401, detail="Invalid password")
    session_id = str(uuid.uuid4())
    token = create_jwt({
        "sub": session_id,
        "role": "client",
        "gallery_id": gallery["id"],
        "gallery_slug": slug
    }, expires_hours=72)
    return {"token": token, "gallery_id": gallery["id"], "title": gallery["title"]}

@api_router.get("/galleries/{slug}/photos")
async def get_gallery_photos(slug: str, session=Depends(get_client_session)):
    if session.get("gallery_slug") != slug:
        raise HTTPException(status_code=403, detail="Access denied")
    gallery_id = session["gallery_id"]
    photos = await db.photos.find({"gallery_id": gallery_id}, {"_id": 0}).sort("uploaded_at", 1).to_list(10000)
    favourites = await db.favourites.find({"session_id": session["sub"], "gallery_id": gallery_id}, {"_id": 0}).to_list(10000)
    fav_ids = {f["photo_id"] for f in favourites}
    for photo in photos:
        photo["is_favourite"] = photo["id"] in fav_ids
    return {"photos": photos, "gallery_id": gallery_id}

@api_router.post("/galleries/{slug}/favourite")
async def toggle_favourite(slug: str, data: FavouriteToggle, session=Depends(get_client_session)):
    if session.get("gallery_slug") != slug:
        raise HTTPException(status_code=403, detail="Access denied")
    existing = await db.favourites.find_one({
        "session_id": session["sub"],
        "photo_id": data.photo_id,
        "gallery_id": session["gallery_id"]
    })
    if existing:
        await db.favourites.delete_one({"_id": existing["_id"]})
        return {"favourited": False}
    else:
        await db.favourites.insert_one({
            "id": str(uuid.uuid4()),
            "session_id": session["sub"],
            "photo_id": data.photo_id,
            "gallery_id": session["gallery_id"],
            "created_at": datetime.now(timezone.utc).isoformat()
        })
        return {"favourited": True}

@api_router.get("/galleries/{slug}/download/{photo_id}")
async def download_photo(slug: str, photo_id: str, session=Depends(get_client_session)):
    if session.get("gallery_slug") != slug:
        raise HTTPException(status_code=403, detail="Access denied")
    photo = await db.photos.find_one({"id": photo_id, "gallery_id": session["gallery_id"]}, {"_id": 0})
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    file_path = UPLOAD_DIR / "galleries" / session["gallery_id"] / photo["original_path"]
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(file_path, filename=photo["filename"], media_type="application/octet-stream")

@api_router.post("/galleries/{slug}/download-zip")
async def download_zip(slug: str, photo_ids: List[str] = [], session=Depends(get_client_session)):
    if session.get("gallery_slug") != slug:
        raise HTTPException(status_code=403, detail="Access denied")
    gallery_id = session["gallery_id"]
    if photo_ids:
        query = {"gallery_id": gallery_id, "id": {"$in": photo_ids}}
    else:
        query = {"gallery_id": gallery_id}
    photos = await db.photos.find(query, {"_id": 0}).to_list(10000)
    if not photos:
        raise HTTPException(status_code=404, detail="No photos found")

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for photo in photos:
            file_path = UPLOAD_DIR / "galleries" / gallery_id / photo["original_path"]
            if file_path.exists():
                zf.write(file_path, photo["filename"])
    zip_buffer.seek(0)

    gallery = await db.galleries.find_one({"id": gallery_id}, {"_id": 0})
    zip_name = f"{gallery['title'].replace(' ', '_')}_photos.zip" if gallery else "photos.zip"
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{zip_name}"'}
    )

# Include the router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
