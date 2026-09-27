import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = (ROOT / "server.py").read_text(encoding="utf-8")
TREE = ast.parse(SERVER_SOURCE)


def async_function(name):
    return next(
        node for node in ast.walk(TREE)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )


class Release212CleanupStructureTests(unittest.TestCase):
    def test_cleanup_is_admin_only_and_requires_exact_confirmation(self):
        source = ast.unparse(async_function("run_maintenance_cleanup"))
        self.assertIn("admin=Depends(get_admin)", source)
        self.assertIn("DELETE GENERATED FILES", source)
        self.assertIn("clean_generated_files", source)
        self.assertNotIn("db.files.delete", source)
        self.assertNotIn("db.galleries.delete", source)

    def test_individual_admin_video_delete_removes_generated_companions(self):
        source = ast.unparse(async_function("delete_file"))
        self.assertIn("get_web_version_path(file_path).unlink", source)
        self.assertIn("get_web_temporary_path(file_path).unlink", source)
        self.assertIn("get_web_version_path(backup_file).unlink", source)

    def test_guest_video_delete_removes_generated_companions(self):
        source = ast.unparse(async_function("guest_delete_files"))
        self.assertIn("get_web_version_path(file_path).unlink", source)
        self.assertIn("get_web_temporary_path(file_path).unlink", source)


if __name__ == "__main__":
    unittest.main()
