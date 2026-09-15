"""Pure helpers for durable, rate-limited broadcast campaigns."""

from __future__ import annotations

from typing import Dict, Iterable, List


ACTIVE_CAMPAIGN_STATUSES = {"queued", "running", "paused"}
TERMINAL_CAMPAIGN_STATUSES = {"complete", "cancelled", "failed"}


def unique_recipients(galleries: Iterable[Dict]) -> List[Dict]:
    """Deduplicate gallery email addresses while retaining useful admin labels."""
    recipients: List[Dict] = []
    by_email = {}
    for gallery in galleries:
        email = (gallery.get("client_email") or "").strip()
        if not email:
            continue
        key = email.casefold()
        gallery_name = (gallery.get("folder_name") or "Unknown gallery").strip()
        if key in by_email:
            existing = by_email[key]
            if gallery_name not in existing["gallery_names"]:
                existing["gallery_names"].append(gallery_name)
            continue
        recipient = {
            "email": email,
            "gallery_names": [gallery_name],
        }
        by_email[key] = recipient
        recipients.append(recipient)
    return recipients


def recipient_counts(recipients: Iterable[Dict]) -> Dict[str, int]:
    counts = {"pending": 0, "sending": 0, "sent": 0, "failed": 0}
    for recipient in recipients:
        status = recipient.get("status", "pending")
        if status in counts:
            counts[status] += 1
    counts["total"] = sum(counts.values())
    return counts


def public_campaign(campaign: Dict | None) -> Dict | None:
    """Expose progress without message content, SMTP data or recipient addresses."""
    if not campaign:
        return None
    counts = recipient_counts(campaign.get("recipients", []))
    total = counts["total"]
    finished = counts["sent"] + counts["failed"]
    percent = round((finished / total) * 100) if total else 0
    return {
        "id": campaign.get("id"),
        "status": campaign.get("status", "queued"),
        "subject": campaign.get("subject", ""),
        "total": total,
        "sent": counts["sent"],
        "failed": counts["failed"],
        "pending": counts["pending"] + counts["sending"],
        "percent": percent,
        "batch_size": campaign.get("batch_size", 10),
        "batch_delay_seconds": campaign.get("batch_delay_seconds", 120),
        "created_at": campaign.get("created_at"),
        "started_at": campaign.get("started_at"),
        "next_batch_at": campaign.get("next_batch_at"),
        "finished_at": campaign.get("finished_at"),
        "has_attachments": bool(campaign.get("attachments")),
        "message": campaign.get("message", ""),
    }


def pending_batch(campaign: Dict, batch_size: int) -> List[Dict]:
    return [
        recipient for recipient in campaign.get("recipients", [])
        if recipient.get("status", "pending") == "pending"
    ][:batch_size]
