import tempfile
import threading
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import backup_service
from backup_service import BackupManager, incremental_backup, is_generated_backup_file


class BackupServiceTests(unittest.TestCase):
    def test_generated_web_video_is_excluded_but_original_is_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            backup = root / "backup"
            video_dir = source / "Test Couple" / "Video"
            video_dir.mkdir(parents=True)
            backup.mkdir()

            (video_dir / "highlights.mp4").write_bytes(b"original-video")
            (video_dir / "highlights.web.mp4").write_bytes(b"generated-playback-copy")

            result = incremental_backup(source, backup)

            self.assertEqual(
                (backup / "Test Couple" / "Video" / "highlights.mp4").read_bytes(),
                b"original-video",
            )
            self.assertFalse((backup / "Test Couple" / "Video" / "highlights.web.mp4").exists())
            self.assertEqual(result["copied"], 1)

    def test_existing_generated_copy_is_not_deleted_from_backup(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            backup = root / "backup"
            source_video = source / "Test Couple" / "Video"
            backup_video = backup / "Test Couple" / "Video"
            source_video.mkdir(parents=True)
            backup_video.mkdir(parents=True)

            (source_video / "highlights.mp4").write_bytes(b"original-video")
            (source_video / "highlights.web.mp4").write_bytes(b"new-generated-copy")
            existing = backup_video / "highlights.web.mp4"
            existing.write_bytes(b"existing-backup-copy")

            incremental_backup(source, backup)

            self.assertEqual(existing.read_bytes(), b"existing-backup-copy")

    def test_generated_file_name_rules_are_case_insensitive(self):
        self.assertTrue(is_generated_backup_file(Path("Highlights.WEB.MP4")))
        self.assertTrue(is_generated_backup_file(Path("Highlights.web.tmp.mp4")))
        self.assertTrue(is_generated_backup_file(Path("Photo.thumb.jpg")))
        self.assertTrue(is_generated_backup_file(Path("Photo.preview.jpg")))
        self.assertFalse(is_generated_backup_file(Path("Highlights.mp4")))
        self.assertFalse(is_generated_backup_file(Path("Wedding Photo.jpg")))

    def test_manager_starts_in_background_and_refuses_an_overlap(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            backup = root / "backup"
            source.mkdir()
            backup.mkdir()
            entered = threading.Event()
            release = threading.Event()

            def controlled_backup(*_args, **_kwargs):
                entered.set()
                release.wait(timeout=2)
                return {
                    "copied": 1,
                    "skipped": 0,
                    "excluded": 1,
                    "scanned": 2,
                    "errors": [],
                    "galleries_total": 1,
                    "galleries_done": 1,
                    "current_gallery": None,
                }

            manager = BackupManager(source, backup)
            try:
                with patch.object(backup_service, "incremental_backup", controlled_backup):
                    started, status = manager.start()
                    self.assertTrue(started)
                    self.assertEqual(status["status"], "running")
                    self.assertTrue(entered.wait(timeout=1))

                    started_again, overlapping_status = manager.start()
                    self.assertFalse(started_again)
                    self.assertEqual(overlapping_status["status"], "running")

                    release.set()
                    deadline = time.monotonic() + 2
                    while manager.status()["status"] == "running" and time.monotonic() < deadline:
                        time.sleep(0.01)
                    final_status = manager.status()
                    self.assertEqual(final_status["status"], "complete")
                    self.assertEqual(final_status["copied"], 1)
                    self.assertEqual(final_status["excluded"], 1)
            finally:
                release.set()
                manager._executor.shutdown(wait=True)

    def test_incremental_backup_skips_unchanged_original(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            backup = root / "backup"
            photo_dir = source / "Test Couple" / "Wedding Images"
            photo_dir.mkdir(parents=True)
            backup.mkdir()
            (photo_dir / "photo.jpg").write_bytes(b"photo")

            first = incremental_backup(source, backup)
            second = incremental_backup(source, backup)

            self.assertEqual(first["copied"], 1)
            self.assertEqual(second["copied"], 0)
            self.assertEqual(second["skipped"], 1)

    def test_completed_status_is_restored_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            backup = root / "backup"
            state_file = root / ".cache" / "backup-status.json"
            source.mkdir()
            backup.mkdir()
            (source / "Couple").mkdir()
            (source / "Couple" / "photo.jpg").write_bytes(b"photo")

            manager = BackupManager(source, backup, state_file)
            try:
                started, _ = manager.start()
                self.assertTrue(started)
                deadline = time.monotonic() + 2
                while manager.status()["status"] == "running" and time.monotonic() < deadline:
                    time.sleep(0.01)
                self.assertEqual(manager.status()["status"], "complete")
            finally:
                manager._executor.shutdown(wait=True)

            restored = BackupManager(source, backup, state_file)
            try:
                self.assertEqual(restored.status()["status"], "complete")
                self.assertIsNotNone(restored.status()["finished_at"])
            finally:
                restored._executor.shutdown(wait=True)

if __name__ == "__main__":
    unittest.main()
