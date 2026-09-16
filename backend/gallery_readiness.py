"""Side-effect-free Gallery Ready checks.

These checks deliberately focus on photographs. Video delivery is a separate
workflow and must never delay Mark sending a finished image gallery.
"""

from __future__ import annotations

from typing import Dict, Iterable, List, Optional


def _check(key: str, status: str, title: str, detail: str) -> Dict:
    return {"key": key, "status": status, "title": title, "detail": detail}


def build_gallery_readiness(
    *,
    gallery: Dict,
    share: Optional[Dict],
    photo_records: Iterable[Dict],
    missing_photo_names: Iterable[str],
    missing_thumbnail_names: Iterable[str],
    backup_total: int,
    backup_matched: int,
    smtp_configured: bool,
    gallery_link: str = "",
) -> Dict:
    """Build the public, admin-only readiness result without changing data."""
    photos: List[Dict] = list(photo_records)
    missing_photos = list(missing_photo_names)
    missing_thumbnails = list(missing_thumbnail_names)
    checks: List[Dict] = []

    client_email = (gallery.get("client_email") or "").strip()
    checks.append(_check(
        "client_email",
        "healthy" if client_email else "critical",
        "Couple email is ready" if client_email else "Couple email is missing",
        client_email if client_email else "Add the couple's email before sending their gallery notification.",
    ))

    checks.append(_check(
        "main_share",
        "healthy" if share else "critical",
        "Main download link is ready" if share else "Main download link is missing",
        (
            "Whole-gallery download access is active and is not a guest-upload or single-folder link."
            if share else
            "Create or enable a whole-gallery Download share. Guest-upload links are never used here."
        ),
    ))

    checks.append(_check(
        "photographs",
        "healthy" if photos else "critical",
        f"{len(photos):,} photograph{'s' if len(photos) != 1 else ''} ready" if photos else "No finished photographs found",
        (
            "The image gallery contains finished photographs. Videos are intentionally not part of this check."
            if photos else
            "Upload the finished photographs before notifying the couple. Guest uploads and videos do not count."
        ),
    ))

    checks.append(_check(
        "photo_files",
        "healthy" if not missing_photos else "critical",
        "Every photograph exists on disk" if not missing_photos else f"{len(missing_photos):,} photograph file(s) missing",
        (
            "The database and live photograph files agree."
            if not missing_photos else
            "Missing: " + ", ".join(missing_photos[:5]) + ("…" if len(missing_photos) > 5 else "")
        ),
    ))

    checks.append(_check(
        "thumbnails",
        "healthy" if not missing_thumbnails else "warning",
        "Photograph previews are ready" if not missing_thumbnails else f"{len(missing_thumbnails):,} preview(s) still generating",
        (
            "All photograph thumbnails required by the gallery are present."
            if not missing_thumbnails else
            "You can still send the gallery, but these previews may need a little more time."
        ),
    ))

    if backup_total == 0:
        backup_status = "warning"
        backup_title = "No photographs checked against backup"
        backup_detail = "Run the gallery backup when convenient. This warning does not block delivery."
    elif backup_matched == backup_total:
        backup_status = "healthy"
        backup_title = "Photograph backup matches"
        backup_detail = f"All {backup_total:,} finished photographs have matching backup copies."
    else:
        unmatched = backup_total - backup_matched
        backup_status = "warning"
        backup_title = f"{unmatched:,} photograph(s) not yet matched in backup"
        backup_detail = "Run the gallery backup when convenient. This warning does not block delivery."
    checks.append(_check("backup", backup_status, backup_title, backup_detail))

    checks.append(_check(
        "email_service",
        "healthy" if smtp_configured else "critical",
        "Email service is configured" if smtp_configured else "Email service is not configured",
        (
            "The gallery notification can be sent from the configured account."
            if smtp_configured else
            "Complete Settings → Email before sending the notification."
        ),
    ))

    blockers = sum(item["status"] == "critical" for item in checks)
    warnings = sum(item["status"] == "warning" for item in checks)
    return {
        "ready": blockers == 0,
        "status": "ready" if blockers == 0 else "blocked",
        "blockers": blockers,
        "warnings": warnings,
        "checks": checks,
        "preview": {
            "recipient": client_email,
            "gallery_link": gallery_link if share else "",
            "password": (share or {}).get("password_raw") or "No password",
            "share_token": (share or {}).get("token") or "",
        },
        "note": "Videos are intentionally excluded so image delivery is never delayed.",
    }
