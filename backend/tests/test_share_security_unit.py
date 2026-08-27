import unittest
from datetime import datetime, timedelta, timezone

from share_security import ShareSessionError, refresh_share_claims


def _payload(**overrides):
    return {
        "role": "share",
        "share_id": "share-1",
        "gallery_id": "gallery-1",
        "token": "couple-gallery",
        "subfolder": None,
        "access_level": "download",
        "allow_uploads": False,
        "allow_downloads": True,
        **overrides,
    }


def _share(**overrides):
    return {
        "id": "share-1",
        "gallery_id": "gallery-1",
        "token": "couple-gallery",
        "subfolder": None,
        "access_level": "download",
        "is_active": True,
        "expires_at": None,
        **overrides,
    }


class ShareSecurityTests(unittest.TestCase):
    def test_disabled_share_revokes_an_existing_jwt(self):
        with self.assertRaisesRegex(ShareSessionError, "no longer active"):
            refresh_share_claims(_payload(), _share(is_active=False))

    def test_expired_share_revokes_an_existing_jwt(self):
        now = datetime(2026, 8, 27, tzinfo=timezone.utc)
        expired = (now - timedelta(seconds=1)).isoformat()
        with self.assertRaisesRegex(ShareSessionError, "no longer active"):
            refresh_share_claims(_payload(), _share(expires_at=expired), now=now)

    def test_live_permissions_replace_stale_jwt_permissions(self):
        refreshed = refresh_share_claims(
            _payload(access_level="full", allow_uploads=True, allow_delete=True),
            _share(access_level="view", subfolder="Wedding Images"),
        )
        self.assertEqual(refreshed["subfolder"], "Wedding Images")
        self.assertEqual(refreshed["access_level"], "view")
        self.assertFalse(refreshed["allow_uploads"])
        self.assertFalse(refreshed["allow_downloads"])
        self.assertFalse(refreshed["allow_delete"])

    def test_token_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ShareSessionError, "Invalid session"):
            refresh_share_claims(_payload(), _share(token="different-token"))


if __name__ == "__main__":
    unittest.main()
