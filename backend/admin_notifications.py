"""Persistent, grouped admin notifications for the gallery dashboard."""

from __future__ import annotations

import math
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional


NOTIFICATION_TYPES = {
    "guest_upload",
    "voice_message",
    "album_submission",
    "share_expiring",
    "download_complete",
}

UPLOAD_NOTIFICATION_TYPES = {"guest_upload", "voice_message"}


def utc_now_iso(now: Optional[datetime] = None) -> str:
    return (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()


def daily_group_key(event_type: str, gallery_id: str, now: Optional[datetime] = None) -> str:
    if event_type not in NOTIFICATION_TYPES:
        raise ValueError("Unsupported notification type")
    day = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).date().isoformat()
    return f"{event_type}:{gallery_id}:{day}"


async def record_admin_notification(
    database,
    *,
    event_type: str,
    gallery_id: str,
    gallery_name: str,
    title: str,
    message: str,
    target_url: str,
    group_key: Optional[str] = None,
    count: int = 1,
    metadata: Optional[dict] = None,
    coalesce: bool = False,
    now: Optional[datetime] = None,
) -> str:
    """Create one notification or add a new occurrence to an unread group."""
    if event_type not in NOTIFICATION_TYPES:
        raise ValueError("Unsupported notification type")
    occurred_at = utc_now_iso(now)
    if group_key:
        existing = await database.admin_notifications.find_one(
            {"group_key": group_key, "dismissed_at": None},
            {"_id": 0, "id": 1},
        )
        if existing:
            if coalesce:
                await database.admin_notifications.update_one(
                    {"id": existing["id"]},
                    {
                        "$inc": {"count": max(1, int(count))},
                        "$set": {
                            "title": title,
                            "message": message,
                            "updated_at": occurred_at,
                            "read_at": None,
                            "metadata": metadata or {},
                        },
                    },
                )
            return existing["id"]

    notification_id = str(uuid.uuid4())
    await database.admin_notifications.insert_one({
        "id": notification_id,
        "type": event_type,
        "gallery_id": gallery_id,
        "gallery_name": gallery_name,
        "title": title,
        "message": message,
        "target_url": target_url,
        "group_key": group_key,
        "count": max(1, int(count)),
        "metadata": metadata or {},
        "created_at": occurred_at,
        "updated_at": occurred_at,
        "read_at": None,
        "dismissed_at": None,
    })
    return notification_id


def _parse_datetime(value: str) -> Optional[datetime]:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    except (AttributeError, TypeError, ValueError):
        return None


async def sync_expiring_share_notifications(
    database,
    *,
    warning_days: int = 14,
    now: Optional[datetime] = None,
) -> None:
    """Create idempotent warnings for every currently expiring active link."""
    current = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    cutoff = current + timedelta(days=warning_days)
    shares = await database.shares.find(
        {
            "is_active": True,
            "expires_at": {
                "$exists": True,
                "$ne": None,
                "$gte": current.isoformat(),
                "$lte": cutoff.isoformat(),
            },
        },
        {"_id": 0},
    ).to_list(1000)

    gallery_ids = list({share.get("gallery_id") for share in shares if share.get("gallery_id")})
    galleries = await database.galleries.find(
        {"id": {"$in": gallery_ids}},
        {"_id": 0, "id": 1, "folder_name": 1},
    ).to_list(1000) if gallery_ids else []
    gallery_names = {gallery["id"]: gallery.get("folder_name", "Gallery") for gallery in galleries}

    active_group_keys = []
    for share in shares:
        expiry = _parse_datetime(share.get("expires_at"))
        if not expiry:
            continue
        gallery_id = share.get("gallery_id")
        gallery_name = gallery_names.get(gallery_id, share.get("label") or "Gallery")
        group_key = f"share_expiring:{share.get('id')}:{share.get('expires_at')}"
        active_group_keys.append(group_key)
        remaining_days = max(0, math.ceil((expiry - current).total_seconds() / 86400))
        link_kind = "Guest upload link" if share.get("guest_upload_mode") else "Gallery link"
        await record_admin_notification(
            database,
            event_type="share_expiring",
            gallery_id=gallery_id,
            gallery_name=gallery_name,
            title=f"{link_kind} expires soon",
            message=(
                f"{share.get('label') or gallery_name} expires on "
                f"{expiry.day} {expiry.strftime('%B %Y')} ({remaining_days} day"
                f"{'s' if remaining_days != 1 else ''} remaining)."
            ),
            target_url=f"/admin/gallery/{gallery_id}",
            group_key=group_key,
            metadata={"share_id": share.get("id"), "expires_at": share.get("expires_at")},
            coalesce=False,
            now=current,
        )

    stale_query = {
        "type": "share_expiring",
        "dismissed_at": None,
        "group_key": {"$nin": active_group_keys},
    }
    await database.admin_notifications.update_many(
        stale_query,
        {"$set": {"dismissed_at": current.isoformat()}},
    )
