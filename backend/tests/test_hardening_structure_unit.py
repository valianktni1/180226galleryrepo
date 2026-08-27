import ast
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVER_TREE = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))


def _async_function(name: str) -> ast.AsyncFunctionDef:
    return next(
        node
        for node in ast.walk(SERVER_TREE)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )


class HardeningStructureTests(unittest.TestCase):
    def test_guest_upload_streams_in_chunks_without_whole_file_read(self):
        source = ast.unparse(_async_function("guest_upload"))
        self.assertNotIn("content = await file.read()", source)
        self.assertIn("await file.read(1024 * 1024)", source)
        self.assertIn(".partial", source)
        self.assertIn("MAX_GUEST_UPLOAD_SIZE", source)

    def test_protected_share_dependency_revalidates_live_share(self):
        source = ast.unparse(_async_function("get_share_session"))
        self.assertIn("validate_live_share_session(payload)", source)

    def test_original_media_requires_authentication_and_database_record(self):
        source = ast.unparse(_async_function("serve_original"))
        self.assertIn("raise HTTPException(status_code=401", source)
        self.assertIn("validate_live_share_session(payload)", source)
        self.assertIn("db.files.find_one", source)

    def test_auto_share_password_is_not_written_to_logs(self):
        source = ast.unparse(_async_function("upload_files"))
        self.assertNotIn("pw={auto_password}", source)
        self.assertNotIn("password: {auto_password}", source)


if __name__ == "__main__":
    unittest.main()
