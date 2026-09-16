import unittest

from gallery_readiness import build_gallery_readiness


class GalleryReadinessTests(unittest.TestCase):
    def _build(self, **overrides):
        values = {
            "gallery": {"client_email": "couple@example.com"},
            "share": {"token": "couple-gallery", "password_raw": "Memory123"},
            "photo_records": [{"id": "photo-1"}, {"id": "photo-2"}],
            "missing_photo_names": [],
            "missing_thumbnail_names": [],
            "backup_total": 2,
            "backup_matched": 2,
            "smtp_configured": True,
            "gallery_link": "https://weddingsbymark.uk/s/couple-gallery",
        }
        values.update(overrides)
        return build_gallery_readiness(**values)

    def test_ready_result_previews_exact_recipient_link_and_password(self):
        result = self._build()
        self.assertTrue(result["ready"])
        self.assertEqual(result["preview"], {
            "recipient": "couple@example.com",
            "gallery_link": "https://weddingsbymark.uk/s/couple-gallery",
            "password": "Memory123",
            "share_token": "couple-gallery",
        })

    def test_missing_backup_is_advisory_and_never_blocks_prompt_delivery(self):
        result = self._build(backup_matched=0)
        self.assertTrue(result["ready"])
        self.assertEqual(result["blockers"], 0)
        backup = next(item for item in result["checks"] if item["key"] == "backup")
        self.assertEqual(backup["status"], "warning")

    def test_missing_live_photograph_blocks_notification(self):
        result = self._build(missing_photo_names=["IMG_0100.jpg"])
        self.assertFalse(result["ready"])
        self.assertEqual(result["blockers"], 1)

    def test_missing_preview_warns_but_does_not_block(self):
        result = self._build(missing_thumbnail_names=["IMG_0100.jpg"])
        self.assertTrue(result["ready"])
        previews = next(item for item in result["checks"] if item["key"] == "thumbnails")
        self.assertEqual(previews["status"], "warning")

    def test_email_share_photographs_and_smtp_are_required(self):
        result = self._build(
            gallery={"client_email": ""},
            share=None,
            photo_records=[],
            backup_total=0,
            backup_matched=0,
            smtp_configured=False,
        )
        self.assertFalse(result["ready"])
        critical = {item["key"] for item in result["checks"] if item["status"] == "critical"}
        self.assertEqual(critical, {"client_email", "main_share", "photographs", "email_service"})


if __name__ == "__main__":
    unittest.main()
