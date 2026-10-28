"""No live Mongo, filesystem, galleries, SMTP or booking requests."""
import asyncio
import uuid
from datetime import datetime, timezone, timedelta

import pytest
from fastapi import FastAPI, APIRouter, Header, HTTPException
from fastapi.testclient import TestClient
from mongomock_motor import AsyncMongoMockClient
from pymongo.errors import DuplicateKeyError

import booking_connection as bridge
from share_security import share_is_expired


def payload(**changes):
    return {'booking_id':str(uuid.uuid4()), 'first_name':'John', 'partner_first_name':'Nikki',
        'email':'john@example.com', 'wedding_date':'2027-10-20', 'photography':True,
        'video':False, 'full_day':True, 'album_mode':'40', **changes}


@pytest.fixture
def connection(tmp_path):
    db=AsyncMongoMockClient().db
    async def admin(authorization:str=Header(default='')):
        if authorization!='Bearer admin-fixture':raise HTTPException(401,'Admin required')
        return {}
    app=FastAPI();router=APIRouter(prefix='/api');bridge.register_booking_connection(router,db,admin,lambda name:tmp_path/name);app.include_router(router)
    with TestClient(app) as c:
        auth={'Authorization':'Bearer admin-fixture'}
        key=c.post('/api/admin/booking-connection/key',headers=auth).json()['key']
        assert c.put('/api/admin/booking-connection',headers=auth,json={'enabled':True}).status_code==200
        yield c,db,tmp_path,{'Authorization':'Bearer '+key},auth


def post(c,auth,data):return c.post('/api/integrations/wbm/galleries',headers=auth,json=data)


def test_existing_startup_index_and_share_survive_creation_and_replay(connection):
    c,db,root,auth,_=connection
    legacy={'id':'legacy-share','token':'legacy-token','gallery_id':'legacy-gallery'}
    async def seed():
        await db.shares.create_index('id')
        await db.shares.insert_one(dict(legacy))
    asyncio.run(seed())
    data=payload()
    first=post(c,auth,data)
    assert first.status_code==200,first.text
    assert post(c,auth,data).json()==first.json()
    async def check():
        # Re-running the established startup index declaration still succeeds.
        await db.shares.create_index('id')
        indexes=await db.shares.index_information()
        assert not indexes['id_1'].get('unique')
        assert indexes['wbm_booking_share_id_unique']['unique']
        assert await db.shares.find_one({'id':'legacy-share'},{'_id':0})==legacy
        assert await db.shares.count_documents({})==2
        assert await db.galleries.count_documents({})==1
        with pytest.raises(DuplicateKeyError):
            await db.shares.insert_one({'id':'legacy-share','token':'different-token'})
    asyncio.run(check())


def test_existing_unique_share_index_is_reused(connection):
    c,db,root,auth,_=connection
    asyncio.run(db.shares.create_index('id',unique=True))
    assert post(c,auth,payload()).status_code==200
    indexes=asyncio.run(db.shares.index_information())
    assert indexes['id_1']['unique']
    assert 'wbm_booking_share_id_unique' not in indexes


def test_duplicate_legacy_share_ids_stop_before_gallery_creation(connection):
    c,db,root,auth,_=connection
    async def seed():
        await db.shares.create_index('id')
        await db.shares.insert_many([
            {'id':'duplicate','token':'one'}, {'id':'duplicate','token':'two'}])
    asyncio.run(seed())
    with pytest.raises(DuplicateKeyError):
        post(c,auth,payload())
    assert asyncio.run(db.galleries.count_documents({}))==0
    assert asyncio.run(db.shares.count_documents({}))==2
    assert not list(root.iterdir())


def test_exact_creation_expiry_no_email_and_replay(connection):
    c,db,root,auth,_=connection;data=payload()
    r=post(c,auth,data);assert r.status_code==200,r.text
    result=r.json();assert result['guest_url']=='https://weddingsbymark.uk/s/johnnikkiguestuploads'
    assert result['guest_expires_at']=='2027-10-23T00:01:00+00:00'
    folder=root/'John & Nikki 20.10.27';assert sorted(p.name for p in folder.iterdir())==['Album Favourites','Guest Uploads','Wedding Images']
    async def check():
        g=await db.galleries.find_one({'id':result['gallery_id']});assert g['client_email']==data['email'];assert g['album_selection']['mode']=='40'
        assert g['workflow_status']=='uploading';assert await db.shares.count_documents({})==1
        assert await db.email_log.count_documents({})==0
        share=await db.shares.find_one({});assert share['access_level']=='upload';assert share['subfolder']=='Guest Uploads';assert not share['allow_all_file_types']
        assert not share_is_expired(share,datetime(2027,10,23,0,0,tzinfo=timezone.utc));assert share_is_expired(share,datetime(2027,10,23,0,2,tzinfo=timezone.utc))
        # Manual changes survive a replay, including share expiry and album choices.
        await db.galleries.update_one({'id':g['id']},{'$set':{'client_email':'manual@example.com','album_selection.mode':'60'}})
        await db.shares.update_one({'id':share['id']},{'$set':{'expires_at':'2027-10-25T00:01:00+00:00'}})
    asyncio.run(check())
    again=post(c,auth,data);assert again.status_code==200;assert again.json()['gallery_id']==result['gallery_id']
    async def check_replay():
        assert await db.galleries.count_documents({})==1
        g=await db.galleries.find_one({});assert g['client_email']=='manual@example.com';assert g['album_selection']['mode']=='60'
    asyncio.run(check_replay())


def test_identical_names_different_dates_get_suffixes(connection):
    c,db,root,auth,_=connection
    for day,suffix in [('2027-10-20',''),('2027-10-21','2'),('2027-10-22','3')]:
        r=post(c,auth,payload(wedding_date=day));assert r.status_code==200,r.text
        assert r.json()['guest_url'].endswith('johnnikkiguestuploads'+suffix)


def test_same_folder_different_booking_and_existing_disk_rejected(connection):
    c,db,root,auth,_=connection
    assert post(c,auth,payload()).status_code==200
    assert post(c,auth,payload()).status_code==409
    existing=root/'Sarah & Dan 20.10.27';existing.mkdir();(existing/'keep.txt').write_text('retained')
    assert post(c,auth,payload(first_name='Sarah',partner_first_name='Dan')).status_code==409
    assert (existing/'keep.txt').read_text()=='retained'


def test_half_day_video_paid_album_no_guest_share(connection):
    c,db,root,auth,_=connection
    r=post(c,auth,payload(full_day=False,video=True,album_mode='60'));assert r.status_code==200,r.text
    assert r.json()['guest_url'] is None
    assert sorted(p.name for p in (root/'John & Nikki 20.10.27').iterdir())==['Album Favourites','Video','Wedding Images']


def test_removed_gallery_not_recreated_and_changed_request_rejected(connection):
    c,db,root,auth,_=connection;data=payload();assert post(c,auth,data).status_code==200
    assert post(c,auth,{**data,'album_mode':'60'}).status_code==409
    asyncio.run(db.galleries.delete_many({}))
    assert post(c,auth,data).status_code==409
    assert asyncio.run(db.galleries.count_documents({}))==0


def test_interrupted_after_gallery_insert_recovers_share_only(connection):
    c,db,root,auth,_=connection;data=payload();original=bridge.slug_base
    def fail(_):raise RuntimeError('simulated crash before share')
    bridge.slug_base=fail
    try:
        with pytest.raises(RuntimeError):post(c,auth,data)
    finally:bridge.slug_base=original
    assert asyncio.run(db.galleries.count_documents({}))==1
    r=post(c,auth,data);assert r.status_code==200,r.text
    assert asyncio.run(db.galleries.count_documents({}))==1
    assert asyncio.run(db.shares.count_documents({}))==1


def test_auth_pause_rotation_validation(connection):
    c,db,root,auth,admin=connection
    assert post(c,{},payload()).status_code==401
    assert c.post('/api/admin/booking-connection/key').status_code==401
    assert post(c,auth,payload(album_mode='100')).status_code==422
    assert post(c,auth,payload(first_name='../John')).status_code in (400,422)
    assert post(c,auth,payload(email='invalid')).status_code==422
    assert post(c,auth,{**payload(),'send_email':True}).status_code==422
    c.put('/api/admin/booking-connection',headers=admin,json={'enabled':False})
    assert post(c,auth,payload()).status_code==401
    c.post('/api/admin/booking-connection/key',headers=admin)
    c.put('/api/admin/booking-connection',headers=admin,json={'enabled':True})
    assert post(c,auth,payload()).status_code==401

