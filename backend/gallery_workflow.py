"""Gallery delivery-journey rules shared by admin endpoints."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


WORKFLOW_STATUSES = (
    "uploading",
    "ready",
    "delivered",
    "album_choices_received",
    "archived",
)


def normalise_gallery_workflow_status(gallery: dict) -> str:
    stored = gallery.get("workflow_status")
    if stored in WORKFLOW_STATUSES:
        return stored
    album = gallery.get("album_selection") or {}
    if album.get("mode") in {"40", "60"} and album.get("locked") is True:
        return "album_choices_received"
    if gallery.get("notification_sent_at"):
        return "delivered"
    return "uploading"


def workflow_change(
    gallery: dict,
    status: str,
    *,
    source: str,
    now: Optional[datetime] = None,
) -> dict:
    if status not in WORKFLOW_STATUSES:
        raise ValueError("Invalid gallery status")
    album = gallery.get("album_selection") or {}
    if status == "album_choices_received" and album.get("mode") not in {"40", "60"}:
        raise ValueError("Album choices are switched off for this gallery")
    changed_at = (now or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
    previous = normalise_gallery_workflow_status(gallery)
    return {
        "previous": previous,
        "status": status,
        "changed": previous != status,
        "changed_at": changed_at,
        "history": {
            "from": previous,
            "to": status,
            "source": source,
            "changed_at": changed_at,
        },
    }
