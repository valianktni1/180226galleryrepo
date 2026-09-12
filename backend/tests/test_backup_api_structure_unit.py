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


class BackupApiStructureTests(unittest.TestCase):
    def test_backup_request_only_starts_background_manager(self):
        source = ast.unparse(_async_function("run_backup"))
        self.assertIn("backup_manager.start()", source)
        self.assertNotIn("rglob", source)
        self.assertNotIn("shutil.copy2", source)

    def test_status_endpoint_reads_manager_state(self):
        source = ast.unparse(_async_function("get_backup_status"))
        self.assertIn("backup_manager.status()", source)


if __name__ == "__main__":
    unittest.main()
