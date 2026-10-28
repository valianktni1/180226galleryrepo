"""Opt-in WBM booking intake. Creates private galleries; never sends email.

Reservations and immutable payloads make interrupted requests safe to retry.
Existing galleries, shares and manual edits are never rewritten by a replay.
"""
import hashlib
import hmac
import json
import re
import secrets
import unicodedata
import uuid
from datetime import date, datetime, timedelta, timezone

from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel, Field, EmailStr, ConfigDict
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from album_selection import default_album_selection, set_album_mode
from security_paths import validate_path_component, UnsafePathError

KEY = 'wbm_booking_connection'
ORIGIN = 'https://weddingsbymark.uk'


def utcnow():
    return datetime.now(timezone.utc)


class ProvisionIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    booking_id: uuid.UUID
    first_name: str = Field(min_length=1, max_length=70)
    partner_first_name: str = Field(min_length=1, max_length=70)
    email: EmailStr
    wedding_date: date
    photography: bool
    video: bool
    full_day: bool
    selfie_booth: bool = False
    album_mode: str


class EnabledIn(BaseModel):
    model_config = ConfigDict(extra='forbid')
    enabled: bool


def normalise(payload):
    data = json.loads(payload.model_dump_json())
    if data['album_mode'] not in ('off', '40', '60'):
        raise HTTPException(422, 'Choose Off, 40 + cover, or 60 + cover for the album.')
    if not any(data[k] for k in ('photography', 'video', 'selfie_booth')):
        raise HTTPException(422, 'The package needs at least one delivery folder.')
    for key in ('first_name', 'partner_first_name'):
        data[key] = ' '.join(data[key].split())
        if not data[key]:
            raise HTTPException(422, 'Both first names are required.')
    data['email'] = str(data['email']).strip().lower()
    return data


def folder_name(data):
    day = date.fromisoformat(data['wedding_date'])
    try:
        return validate_path_component(f"{data['first_name']} & {data['partner_first_name']} {day:%d.%m.%y}", 'gallery folder name')
    except UnsafePathError as exc:
        raise HTTPException(422, str(exc)) from exc


def slug_base(data):
    names = unicodedata.normalize('NFKD', data['first_name'] + data['partner_first_name']).encode('ascii', 'ignore').decode().lower()
    names = re.sub('[^a-z0-9]', '', names)
    if not names:
        raise HTTPException(422, 'Add names that can form a guest-upload address.')
    return names + 'guestuploads'


def guest_expiry(data):
    # Match the established app rule exactly: 00:01 UTC on the third day after.
    day = date.fromisoformat(data['wedding_date'])
    return (datetime.combine(day, datetime.min.time(), timezone.utc) + timedelta(days=3, minutes=1)).isoformat()


async def provision(db, get_path, payload):
    data = normalise(payload)
    bid = data['booking_id']
    encoded = json.dumps(data, sort_keys=True, separators=(',', ':'))
    fingerprint = hashlib.sha256(encoded.encode()).hexdigest()
    now = utcnow()
    name = folder_name(data)
    gid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'wbm-booking-gallery:' + bid))
    try:
        await db.booking_gallery_jobs.insert_one({'_id':bid, 'fingerprint':fingerprint, 'payload':data,
            'gallery_id':gid, 'folder_name':name, 'status':'pending', 'lease_until':now})
    except DuplicateKeyError:
        pass
    job = await db.booking_gallery_jobs.find_one({'_id':bid})
    if job['fingerprint'] != fingerprint:
        raise HTTPException(409, 'This booking request changed. Review its existing gallery; it was not overwritten.')
    if job['status'] == 'complete':
        return await acknowledgement(db, job)
    claim = secrets.token_hex(16)
    claimed = await db.booking_gallery_jobs.find_one_and_update(
        {'_id':bid, 'lease_until':{'$lte':now}, 'status':{'$ne':'complete'}},
        {'$set':{'lease_until':now+timedelta(minutes=2), 'claim':claim}}, return_document=ReturnDocument.AFTER)
    if not claimed:
        raise HTTPException(503, 'The same booking is already being prepared. Retry shortly.')
    try:
        gallery = await db.galleries.find_one({'id':gid})
        if not gallery:
            path = get_path(name)
            owner = await db.booking_gallery_folders.find_one({'_id':name.casefold()})
            if not owner:
                if path.exists() or await db.galleries.find_one({'folder_name':name}):
                    raise HTTPException(409, 'A gallery folder with this name already exists. Link it manually; nothing was changed.')
                try:
                    await db.booking_gallery_folders.insert_one({'_id':name.casefold(), 'booking_id':bid})
                except DuplicateKeyError:
                    pass
                owner = await db.booking_gallery_folders.find_one({'_id':name.casefold()})
            if owner['booking_id'] != bid:
                raise HTTPException(409, 'This gallery name belongs to another booking. Review it manually.')
            folders = []
            for key,label in [('photography','Wedding Images'),('video','Video'),('selfie_booth','SelfieBooth')]:
                if data[key]: folders.append(label)
            if data['album_mode'] != 'off': folders.append('Album Favourites')
            if data['full_day']: folders.append('Guest Uploads')
            for subfolder in folders:
                (path / subfolder).mkdir(parents=True, exist_ok=True)
            album = set_album_mode({'album_selection':default_album_selection()}, data['album_mode'])
            created = now.isoformat()
            doc = {'id':gid, 'folder_name':name, 'client_email':data['email'], 'subfolders':folders,
                'template_id':None, 'theme':'classic_gold', 'album_selection':album,
                'file_counts':{sf:0 for sf in folders}, 'workflow_status':'uploading',
                'workflow_status_updated_at':created, 'workflow_history':[{'from':None,'to':'uploading','source':'wbm_booking','changed_at':created}],
                'created_at':created, 'updated_at':created, 'wbm_booking_id':bid}
            try:
                await db.galleries.insert_one(doc)
            except DuplicateKeyError:
                existing = await db.galleries.find_one({'id':gid})
                if not existing or existing.get('wbm_booking_id') != bid: raise
        elif gallery.get('wbm_booking_id') != bid:
            raise HTTPException(409, 'Gallery identity conflict. Review it manually.')
        if data['full_day']:
            sid = str(uuid.uuid5(uuid.NAMESPACE_URL, 'wbm-booking-guest-share:' + bid))
            share = await db.shares.find_one({'id':sid})
            if not share:
                base = slug_base(data)
                # Existing unique token index arbitrates concurrent identical names.
                for suffix in range(1,10001):
                    token = base + (str(suffix) if suffix > 1 else '')
                    if await db.shares.find_one({'token':token}): continue
                    share = {'id':sid, 'gallery_id':gid, 'token':token, 'subfolder':'Guest Uploads',
                        'password_hash':None, 'password_raw':'', 'has_password':False,
                        'access_level':'upload', 'allow_uploads':True, 'guest_upload_mode':True,
                        'allow_all_file_types':False, 'label':'Guest Uploads', 'expires_at':guest_expiry(data),
                        'is_active':True, 'created_at':now.isoformat(), 'wbm_booking_id':bid}
                    try:
                        await db.shares.insert_one(share)
                        break
                    except DuplicateKeyError:
                        share = await db.shares.find_one({'id':sid})
                        if share: break
                else:
                    raise HTTPException(409, 'No guest-upload address available. Review this gallery.')
            if share.get('gallery_id') != gid:
                raise HTTPException(409, 'Guest-share identity conflict.')
        await db.booking_gallery_jobs.update_one({'_id':bid,'claim':claim}, {'$set':{'status':'complete'}})
        return await acknowledgement(db, job)
    finally:
        await db.booking_gallery_jobs.update_one({'_id':bid,'claim':claim}, {'$set':{'lease_until':utcnow()}})


async def acknowledgement(db, job):
    gid = job['gallery_id']
    gallery = await db.galleries.find_one({'id':gid})
    if not gallery:
        raise HTTPException(409, 'The linked gallery was removed. It has not been recreated.')
    share = await db.shares.find_one({'gallery_id':gid, 'wbm_booking_id':job['_id']})
    if job['payload']['full_day'] and not share:
        raise HTTPException(409, 'The linked guest share was removed. It has not been recreated.')
    return {'booking_id':job['_id'], 'gallery_id':gid, 'status':'created',
        'admin_url':ORIGIN+'/admin/gallery/'+gid,
        'guest_url':ORIGIN+'/s/'+share['token'] if share else None,
        'guest_expires_at':share.get('expires_at') if share else None}


def register_booking_connection(router, db, get_admin, get_path):
    async def auth(authorization: str = Header(default='')):
        row = await db.settings.find_one({'key':KEY}) or {}
        config = row.get('value',{})
        token = authorization[7:] if authorization.startswith('Bearer ') else ''
        digest = hashlib.sha256(token.encode()).hexdigest()
        if not config.get('enabled') or not token or not hmac.compare_digest(digest, config.get('key_hash','')):
            raise HTTPException(401, 'Booking connection is disabled or its key was rejected.')

    @router.get('/admin/booking-connection')
    async def settings(admin=Depends(get_admin)):
        row = await db.settings.find_one({'key':KEY}) or {}
        config = row.get('value',{})
        return {'enabled':bool(config.get('enabled')), 'key_saved':bool(config.get('key_hash'))}

    @router.post('/admin/booking-connection/key')
    async def new_key(admin=Depends(get_admin)):
        key = 'wbm_gallery_' + secrets.token_urlsafe(40)
        await db.settings.update_one({'key':KEY}, {'$set':{'value':{'enabled':False,
            'key_hash':hashlib.sha256(key.encode()).hexdigest()}}}, upsert=True)
        return {'key':key, 'enabled':False}

    @router.put('/admin/booking-connection')
    async def enabled(payload: EnabledIn, admin=Depends(get_admin)):
        row = await db.settings.find_one({'key':KEY}) or {}
        if payload.enabled and not row.get('value',{}).get('key_hash'):
            raise HTTPException(422, 'Create a connection key first.')
        await db.settings.update_one({'key':KEY}, {'$set':{'value.enabled':payload.enabled}}, upsert=True)
        return {'enabled':payload.enabled}

    @router.get('/integrations/wbm/status', dependencies=[Depends(auth)])
    async def status():
        return {'ready':True, 'capabilities':{'gallery_provisioning':1}}

    @router.post('/integrations/wbm/galleries', dependencies=[Depends(auth)])
    async def create(payload: ProvisionIn):
        if payload.wedding_date < utcnow().date():
            raise HTTPException(422, 'A past wedding needs manual gallery creation.')
        # Indexes are required here as well as startup: never provision without uniqueness.
        await db.galleries.create_index('id', unique=True)
        await db.shares.create_index('token', unique=True)
        await db.shares.create_index('id', unique=True)
        return await provision(db, get_path, payload)
