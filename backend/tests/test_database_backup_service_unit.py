import hashlib
import tempfile
import unittest
import zipfile
from pathlib import Path

from bson import BSON, json_util

from database_backup_service import (
    DatabaseBackupError,
    SNAPSHOT_FORMAT,
    inspect_snapshot_archive,
)


class DatabaseBackupArchiveTests(unittest.TestCase):
    def _write_snapshot(self, path: Path, *, checksum_override=None):
        documents = [
            BSON.encode({"_id": 1, "name": "One"}),
            BSON.encode({"_id": 2, "name": "Two"}),
        ]
        checksum = hashlib.sha256(b"".join(documents)).hexdigest()
        manifest = {
            "format": SNAPSHOT_FORMAT,
            "database": "weddings_by_mark",
            "created_at": "2026-09-27T12:00:00+00:00",
            "documents_total": 2,
            "collections": [{
                "name": "galleries",
                "member": "collections/galleries.bson",
                "documents": 2,
                "sha256": checksum_override or checksum,
                "indexes": {"_id_": {"key": [["_id", 1]]}},
            }],
        }
        with zipfile.ZipFile(path, "w") as archive:
            archive.writestr("collections/galleries.bson", b"".join(documents))
            archive.writestr("manifest.json", json_util.dumps(manifest))

    def test_snapshot_archive_count_and_checksum_are_verified(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.zip"
            self._write_snapshot(snapshot)
            manifest = inspect_snapshot_archive(snapshot)
            self.assertEqual(manifest["documents_total"], 2)
            self.assertEqual(manifest["collections"][0]["name"], "galleries")

    def test_snapshot_archive_rejects_a_checksum_mismatch(self):
        with tempfile.TemporaryDirectory() as directory:
            snapshot = Path(directory) / "snapshot.zip"
            self._write_snapshot(snapshot, checksum_override="0" * 64)
            with self.assertRaises(DatabaseBackupError):
                inspect_snapshot_archive(snapshot)


if __name__ == "__main__":
    unittest.main()
