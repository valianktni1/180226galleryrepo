import tempfile
import time
import unittest
import zipfile
from pathlib import Path

from download_job_service import DownloadJobError, DownloadJobManager


class DownloadJobManagerTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.source_dir = root / "source"
        self.source_dir.mkdir()
        self.cache_dir = root / ".cache" / "downloads"
        self.manager = DownloadJobManager(self.cache_dir, ttl_seconds=60)

    def tearDown(self):
        self.manager.shutdown()
        self.temp_dir.cleanup()

    def _wait_until_ready(self, job_id):
        deadline = time.time() + 3
        while time.time() < deadline:
            state = self.manager.status(job_id, owner_kind="share", owner_id="viewer")
            if state["status"] in {"ready", "failed"}:
                return state
            time.sleep(0.01)
        self.fail("Download job did not finish preparing")

    def test_prepares_streams_and_removes_disk_archive(self):
        first = self.source_dir / "one.jpg"
        second = self.source_dir / "two.mp4"
        first.write_bytes(b"photo" * 100)
        second.write_bytes(b"video" * 200)

        state, ticket = self.manager.start(
            owner_kind="share",
            owner_id="viewer",
            gallery_id="gallery-1",
            label="Wedding Images",
            filename="Couple - Wedding Images.zip",
            entries=[(first, "one.jpg"), (second, "two.mp4")],
        )
        self.assertEqual(state["status"], "queued")
        ready = self._wait_until_ready(state["id"])
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["files_done"], 2)
        self.assertEqual(ready["percent"], 100)

        metadata = self.manager.download_metadata(state["id"], ticket)
        archive_bytes = b"".join(self.manager.iter_download(state["id"], ticket, chunk_size=17))
        self.assertEqual(len(archive_bytes), metadata["bytes_total"])

        saved = Path(self.temp_dir.name) / "result.zip"
        saved.write_bytes(archive_bytes)
        with zipfile.ZipFile(saved) as archive:
            self.assertEqual(set(archive.namelist()), {"one.jpg", "two.mp4"})
            self.assertEqual(archive.read("one.jpg"), first.read_bytes())

        complete = self.manager.status(state["id"], owner_kind="share", owner_id="viewer")
        self.assertEqual(complete["status"], "complete")
        self.assertEqual(complete["bytes_sent"], complete["bytes_total"])
        self.assertFalse((self.cache_dir / f"{state['id']}.zip").exists())

    def test_status_is_scoped_to_the_authenticated_owner(self):
        source = self.source_dir / "one.jpg"
        source.write_bytes(b"photo")
        state, _ = self.manager.start(
            owner_kind="admin",
            owner_id="admin-1",
            gallery_id="gallery-1",
            label="Wedding Images",
            filename="download.zip",
            entries=[(source, "one.jpg")],
        )
        with self.assertRaises(DownloadJobError):
            self.manager.status(state["id"], owner_kind="admin", owner_id="admin-2")
        with self.assertRaises(DownloadJobError):
            self.manager.status(state["id"], owner_kind="share", owner_id="admin-1")

    def test_wrong_ticket_cannot_claim_archive(self):
        source = self.source_dir / "one.jpg"
        source.write_bytes(b"photo")
        state, _ = self.manager.start(
            owner_kind="share",
            owner_id="viewer",
            gallery_id="gallery-1",
            label="Wedding Images",
            filename="download.zip",
            entries=[(source, "one.jpg")],
        )
        self._wait_until_ready(state["id"])
        with self.assertRaises(DownloadJobError):
            self.manager.download_metadata(state["id"], "not-the-ticket")

    def test_share_context_is_private_but_available_for_live_revalidation(self):
        source = self.source_dir / "one.jpg"
        source.write_bytes(b"photo")
        state, ticket = self.manager.start(
            owner_kind="share", owner_id="viewer", gallery_id="gallery-1",
            label="Wedding Images", filename="download.zip",
            entries=[(source, "one.jpg")], share_token="couple-share",
            scope_subfolder="Wedding Images",
        )
        self.assertNotIn("share_token", state)
        self.assertNotIn("scope_subfolder", state)
        context = self.manager.access_context(state["id"], ticket)
        self.assertEqual(context["share_token"], "couple-share")
        self.assertEqual(context["label"], "Wedding Images")
        self.assertEqual(context["scope_subfolder"], "Wedding Images")

    def test_same_owner_can_recover_an_active_job_after_page_refresh(self):
        source = self.source_dir / "one.jpg"
        source.write_bytes(b"photo" * 100)
        first, first_ticket = self.manager.start(
            owner_kind="share", owner_id="viewer", gallery_id="gallery-1",
            label="Wedding Images", filename="download.zip",
            entries=[(source, "one.jpg")],
        )
        second, second_ticket = self.manager.start(
            owner_kind="share", owner_id="viewer", gallery_id="gallery-1",
            label="Wedding Images", filename="download.zip",
            entries=[(source, "one.jpg")],
        )
        self.assertEqual(second["id"], first["id"])
        self.assertEqual(second_ticket, first_ticket)

    def test_interrupted_delivery_fails_safely_and_removes_archive(self):
        source = self.source_dir / "large.jpg"
        source.write_bytes(b"photo" * 1000)
        state, ticket = self.manager.start(
            owner_kind="share", owner_id="viewer", gallery_id="gallery-1",
            label="Wedding Images", filename="download.zip",
            entries=[(source, "large.jpg")],
        )
        self._wait_until_ready(state["id"])
        stream = self.manager.iter_download(state["id"], ticket, chunk_size=16)
        next(stream)
        stream.close()
        failed = self.manager.status(state["id"], owner_kind="share", owner_id="viewer")
        self.assertEqual(failed["status"], "failed")
        self.assertFalse((self.cache_dir / f"{state['id']}.zip").exists())

    def test_health_snapshot_is_aggregate_and_contains_no_private_access_data(self):
        source = self.source_dir / "one.jpg"
        source.write_bytes(b"photo" * 100)
        self.manager.start(
            owner_kind="share", owner_id="viewer-secret", gallery_id="gallery-secret",
            label="Wedding Images", filename="download.zip",
            entries=[(source, "one.jpg")], share_token="private-share-token",
        )
        snapshot = self.manager.health_snapshot()
        rendered = repr(snapshot)
        self.assertGreaterEqual(snapshot["active"], 1)
        self.assertIn("by_status", snapshot)
        self.assertIn("cache_bytes", snapshot)
        self.assertNotIn("viewer-secret", rendered)
        self.assertNotIn("gallery-secret", rendered)
        self.assertNotIn("private-share-token", rendered)


if __name__ == "__main__":
    unittest.main()
