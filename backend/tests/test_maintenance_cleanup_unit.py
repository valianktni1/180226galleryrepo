import tempfile
import unittest
from pathlib import Path

from maintenance_cleanup import MaintenanceCleanupError, clean_generated_files


class MaintenanceCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.uploads = self.root / "uploads"
        self.thumbs = self.uploads / ".cache" / "thumbs"
        self.downloads = self.uploads / ".cache" / "downloads"
        self.gallery = self.uploads / "Test Couple" / "Wedding Images"
        self.gallery.mkdir(parents=True)
        self.thumbs.mkdir(parents=True)
        self.downloads.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_cleanup_deletes_only_supplied_generated_candidates(self):
        original_photo = self.gallery / "IMG_0001.jpg"
        original_video = self.gallery / "Highlights.mp4"
        protected_web = self.gallery / "only-copy.web.mp4"
        safe_web = self.gallery / "Highlights.web.mp4"
        stale_temp = self.gallery / "Interrupted.web.tmp.mp4"
        orphan_thumb = self.thumbs / "old.thumb.jpg"
        stale_zip = self.downloads / "expired.zip"
        payloads = {
            original_photo: b"photo",
            original_video: b"video",
            protected_web: b"protected",
            safe_web: b"generated",
            stale_temp: b"temporary",
            orphan_thumb: b"thumbnail",
            stale_zip: b"archive",
        }
        for path, payload in payloads.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)

        result = clean_generated_files(
            upload_root=self.uploads,
            thumbnail_root=self.thumbs,
            download_cache_root=self.downloads,
            candidates={
                "orphan_derivatives": [orphan_thumb],
                "orphan_web_videos": [safe_web],
                "temporary_video_files": [stale_temp],
                "stale_download_archives": [stale_zip],
            },
        )

        self.assertEqual(result["deleted"], 4)
        for path in (orphan_thumb, safe_web, stale_temp, stale_zip):
            self.assertFalse(path.exists())
        for path in (original_photo, original_video, protected_web):
            self.assertTrue(path.exists())

    def test_cleanup_rejects_a_candidate_outside_its_safe_root(self):
        outside = self.root / "outside.thumb.jpg"
        outside.write_bytes(b"keep")
        with self.assertRaises(MaintenanceCleanupError):
            clean_generated_files(
                upload_root=self.uploads,
                thumbnail_root=self.thumbs,
                download_cache_root=self.downloads,
                candidates={"orphan_derivatives": [outside]},
            )
        self.assertTrue(outside.exists())

    def test_cleanup_rejects_an_original_video_suffix(self):
        original = self.gallery / "Highlights.mp4"
        original.write_bytes(b"keep")
        with self.assertRaises(MaintenanceCleanupError):
            clean_generated_files(
                upload_root=self.uploads,
                thumbnail_root=self.thumbs,
                download_cache_root=self.downloads,
                candidates={"orphan_web_videos": [original]},
            )
        self.assertTrue(original.exists())


if __name__ == "__main__":
    unittest.main()
