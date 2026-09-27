import os
import tempfile
import time
import unittest
from pathlib import Path

from maintenance_scan import scan_gallery_maintenance


class MaintenanceScanTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.uploads = self.root / "uploads"
        self.thumbs = self.uploads / ".cache" / "thumbs"
        self.downloads = self.uploads / ".cache" / "downloads"
        self.gallery = self.uploads / "A Couple" / "Wedding Images"
        self.gallery.mkdir(parents=True)
        self.thumbs.mkdir(parents=True)
        self.downloads.mkdir(parents=True)

    def tearDown(self):
        self.temporary.cleanup()

    def test_scan_reports_issues_but_does_not_change_any_file(self):
        original = self.gallery / "IMG_0001.jpg"
        original.write_bytes(b"photo")
        missing = self.gallery / "IMG_0002.jpg"
        expected_thumb = self.thumbs / "gallery" / "wedding-images" / "IMG_0001.thumb.jpg"
        expected_thumb.parent.mkdir(parents=True)
        expected_thumb.write_bytes(b"thumb")
        orphan_thumb = expected_thumb.parent / "old.preview.jpg"
        orphan_thumb.write_bytes(b"old-preview")
        orphan_web = self.gallery / "old.web.mp4"
        orphan_web.write_bytes(b"old-web")
        temporary_video = self.gallery / "interrupted.web.tmp.mp4"
        temporary_video.write_bytes(b"partial")
        stale_zip = self.downloads / "abandoned.zip"
        stale_zip.write_bytes(b"zip")
        old = time.time() - 8 * 60 * 60
        os.utime(temporary_video, (old, old))
        os.utime(stale_zip, (old, old))

        result = scan_gallery_maintenance(
            upload_root=self.uploads,
            thumbnail_root=self.thumbs,
            download_cache_root=self.downloads,
            expected_originals=[
                (original, "A Couple/Wedding Images/IMG_0001.jpg"),
                (missing, "A Couple/Wedding Images/IMG_0002.jpg"),
            ],
            known_original_paths={original, missing},
            expected_derivatives={expected_thumb},
            expected_web_videos=set(),
            stale_download_seconds=3600,
        )

        self.assertTrue(result["read_only"])
        self.assertEqual(result["missing_originals"]["count"], 1)
        self.assertEqual(result["orphan_derivatives"]["count"], 1)
        self.assertEqual(result["orphan_web_videos"]["count"], 0)
        self.assertEqual(result["protected_web_videos"]["count"], 1)
        self.assertEqual(result["temporary_video_files"]["count"], 1)
        self.assertEqual(result["stale_download_archives"]["count"], 1)
        self.assertEqual(result["summary"]["cleanable_items"], 3)
        for path in (original, orphan_thumb, orphan_web, temporary_video, stale_zip):
            self.assertTrue(path.exists())

    def test_known_files_produce_a_clean_result(self):
        original = self.gallery / "IMG_0001.jpg"
        original.write_bytes(b"photo")
        result = scan_gallery_maintenance(
            upload_root=self.uploads,
            thumbnail_root=self.thumbs,
            download_cache_root=self.downloads,
            expected_originals=[(original, "IMG_0001.jpg")],
            known_original_paths={original},
            expected_derivatives=set(),
            expected_web_videos=set(),
        )
        self.assertEqual(result["status"], "clean")
        self.assertEqual(result["summary"]["issues"], 0)

    def test_web_copy_without_an_original_is_protected(self):
        protected = self.gallery / "only-copy.web.mp4"
        protected.write_bytes(b"only remaining playback copy")
        safe_original = self.gallery / "safe-source.MOV"
        safe_original.write_bytes(b"source video")
        safe_web = self.gallery / "safe-source.web.mp4"
        safe_web.write_bytes(b"generated copy")

        result = scan_gallery_maintenance(
            upload_root=self.uploads,
            thumbnail_root=self.thumbs,
            download_cache_root=self.downloads,
            expected_originals=[],
            known_original_paths=set(),
            expected_derivatives=set(),
            expected_web_videos=set(),
            include_cleanup_candidates=True,
        )

        self.assertEqual(result["orphan_web_videos"]["count"], 1)
        self.assertEqual(result["protected_web_videos"]["count"], 1)
        self.assertIn(safe_web, result["_cleanup_candidates"]["orphan_web_videos"])
        self.assertNotIn(protected, result["_cleanup_candidates"]["orphan_web_videos"])

    def test_recent_temporary_video_is_not_offered_for_cleanup(self):
        recent = self.gallery / "working.web.tmp.mp4"
        recent.write_bytes(b"active")
        result = scan_gallery_maintenance(
            upload_root=self.uploads,
            thumbnail_root=self.thumbs,
            download_cache_root=self.downloads,
            expected_originals=[],
            known_original_paths=set(),
            expected_derivatives=set(),
            expected_web_videos=set(),
        )
        self.assertEqual(result["temporary_video_files"]["count"], 0)

    def test_expired_guest_web_copy_is_cleanable_without_an_original(self):
        guest_folder = self.uploads / "A Couple" / "Guest Uploads"
        guest_folder.mkdir(parents=True)
        expired = guest_folder / "guest-clip.web.mp4"
        expired.write_bytes(b"expired generated guest copy")
        old = time.time() - 91 * 24 * 60 * 60
        os.utime(expired, (old, old))

        result = scan_gallery_maintenance(
            upload_root=self.uploads,
            thumbnail_root=self.thumbs,
            download_cache_root=self.downloads,
            expected_originals=[],
            known_original_paths=set(),
            expected_derivatives=set(),
            expected_web_videos=set(),
            include_cleanup_candidates=True,
        )

        self.assertEqual(result["orphan_web_videos"]["count"], 1)
        self.assertEqual(result["protected_web_videos"]["count"], 0)
        self.assertIn(expired, result["_cleanup_candidates"]["orphan_web_videos"])


if __name__ == "__main__":
    unittest.main()
