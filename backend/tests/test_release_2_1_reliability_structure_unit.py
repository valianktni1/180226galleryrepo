import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = (ROOT / "server.py").read_text(encoding="utf-8")
SERVER_TREE = ast.parse(SERVER_SOURCE)


class Release21ReliabilityStructureTests(unittest.TestCase):
    def test_legacy_memory_zip_routes_are_removed(self):
        for legacy_path in (
            "/download-subfolder",
            "/download-zip",
            "/download-album",
            "/download-favourites",
        ):
            self.assertNotIn(legacy_path, SERVER_SOURCE)
        self.assertNotIn("zipfile.ZipFile", SERVER_SOURCE)

    def test_favourites_use_disk_backed_download_jobs(self):
        self.assertIn('/share/{token}/favourites-download-jobs', SERVER_SOURCE)

    def test_backup_is_wired_to_database_restore_verification_and_queue(self):
        self.assertIn("DatabaseBackupService", SERVER_SOURCE)
        self.assertIn("database_backup=database_backup_service.run", SERVER_SOURCE)
        self.assertIn("coordinator=heavy_job_coordinator", SERVER_SOURCE)
        self.assertIn('heavy_job_coordinator.acquire("video")', SERVER_SOURCE)

    def test_database_restore_cleanup_is_in_finally(self):
        tree = ast.parse((ROOT / "database_backup_service.py").read_text(encoding="utf-8"))
        restore = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_restore_and_verify"
        )
        final_bodies = [node.finalbody for node in ast.walk(restore) if isinstance(node, ast.Try)]
        rendered = "\n".join(ast.unparse(body) for body in final_bodies if body)
        self.assertIn("drop_database", rendered)


if __name__ == "__main__":
    unittest.main()
