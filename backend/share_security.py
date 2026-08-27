"""Pure share-session checks used by the API and unit tests."""

from datetime import datetime, timezone


class ShareSessionError(ValueError):
    """Raised when a share JWT no longer matches an active share document."""


def share_is_expired(share: dict, now: datetime | None = None) -> bool:
    if not share.get("is_active"):
        return True
    expires_at = share.get("expires_at")
    if not expires_at:
        return False
    try:
        expiry_date = datetime.fromisoformat(expires_at.replace("Z", "+00:00"))
        return (now or datetime.now(timezone.utc)) > expiry_date
    except (ValueError, TypeError):
        # Preserve the application's existing treatment of malformed legacy dates.
        return False


def refresh_share_claims(
    payload: dict,
    share: dict | None,
    expected_token: str | None = None,
    now: datetime | None = None,
) -> dict:
    """Validate identity/scope and refresh permissions from the live share."""
    if payload.get("role") != "share" or not payload.get("share_id"):
        raise ShareSessionError("Invalid session")
    if not share or share_is_expired(share, now=now):
        raise ShareSessionError("Share session is no longer active")
    if share.get("id") != payload.get("share_id"):
        raise ShareSessionError("Invalid session")
    if share.get("gallery_id") != payload.get("gallery_id"):
        raise ShareSessionError("Invalid session")
    if share.get("token") != payload.get("token"):
        raise ShareSessionError("Invalid session")
    if expected_token is not None and share.get("token") != expected_token:
        raise ShareSessionError("Access denied")

    access_level = share.get("access_level", "download")
    return {
        **payload,
        "subfolder": share.get("subfolder"),
        "access_level": access_level,
        "allow_uploads": access_level in ("upload", "full"),
        "allow_downloads": access_level in ("download", "upload", "full"),
        "allow_delete": access_level == "full",
    }
