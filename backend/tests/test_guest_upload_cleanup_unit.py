import ast
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVER_TREE = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))


def _cleanup_function() -> ast.AsyncFunctionDef:
    return next(
        node
        for node in ast.walk(SERVER_TREE)
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "run_guest_upload_cleanup"
    )


def _assigned_call_argument(function: ast.AsyncFunctionDef, target_name: str):
    for node in ast.walk(function):
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        target = node.targets[0]
        if not isinstance(target, ast.Name) or target.id != target_name:
            continue
        if not isinstance(node.value, ast.Call):
            return None
        if not isinstance(node.value.func, ast.Name):
            return None
        return node.value.func.id, [ast.unparse(arg) for arg in node.value.args]
    return None


def _has_guarded_unlink(function: ast.AsyncFunctionDef, variable_name: str) -> bool:
    expected_test = f"{variable_name}.exists()"
    expected_action = f"{variable_name}.unlink()"
    return any(
        isinstance(node, ast.If)
        and ast.unparse(node.test) == expected_test
        and any(ast.unparse(statement) == expected_action for statement in node.body)
        for node in ast.walk(function)
    )


class GuestUploadCleanupTests(unittest.TestCase):
    def test_cleanup_query_remains_scoped_to_guest_uploads(self):
        source = ast.unparse(_cleanup_function())
        self.assertIn("'subfolder': 'Guest Uploads'", source)
        self.assertIn(
            "get_gallery_file_path(folder_name, 'Guest Uploads', filename)",
            source,
        )
        self.assertIn(
            "get_backup_file_path(folder_name, 'Guest Uploads', filename)",
            source,
        )

    def test_live_generated_video_is_deleted_with_expired_guest_original(self):
        call = _assigned_call_argument(_cleanup_function(), "web_path")
        self.assertEqual(call, ("get_web_version_path", ["file_path"]))
        self.assertTrue(_has_guarded_unlink(_cleanup_function(), "web_path"))

    def test_backup_generated_video_is_deleted_with_expired_guest_original(self):
        call = _assigned_call_argument(_cleanup_function(), "backup_web_file")
        self.assertEqual(call, ("get_web_version_path", ["backup_file"]))
        self.assertTrue(_has_guarded_unlink(_cleanup_function(), "backup_web_file"))


if __name__ == "__main__":
    unittest.main()
