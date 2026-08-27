"""Share-selection rules used by client-facing gallery emails."""


def main_gallery_share_query(gallery_id: str) -> dict:
    """Return the MongoDB query for an active, downloadable whole-gallery share.

    Guest-upload/QR shares and subfolder-only shares must never be used by the
    "Your Wedding Gallery is Ready" email.
    """
    return {
        "gallery_id": gallery_id,
        "is_active": True,
        "guest_upload_mode": {"$ne": True},
        "subfolder": None,
        "access_level": {"$in": ["download", "full"]},
    }
