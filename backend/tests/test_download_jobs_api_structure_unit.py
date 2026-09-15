import ast
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVER_TREE = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))


def _async_function(name: str) -> ast.AsyncFunctionDef:
    return next(
        node for node in ast.walk(SERVER_TREE)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )


class DownloadJobApiStructureTests(unittest.TestCase):
    def test_admin_start_and_status_require_admin_authentication(self):
        start = ast.unparse(_async_function("start_admin_download_job"))
        status = ast.unparse(_async_function("get_admin_download_job"))
        self.assertIn("admin=Depends(get_admin)", start)
        self.assertIn("admin=Depends(get_admin)", status)
        self.assertIn("owner_id=str(admin['sub'])", start)
        self.assertIn("owner_id=str(admin['sub'])", status)

    def test_share_jobs_are_scoped_to_live_session_and_folder(self):
        start = ast.unparse(_async_function("start_share_download_job"))
        status = ast.unparse(_async_function("get_share_download_job"))
        self.assertIn("session=Depends(get_share_session)", start)
        self.assertIn("expected_token=token", start)
        self.assertIn("share_subfolder", start)
        self.assertIn("owner_id = f\"{token}:{session['sub']}\"", start)
        self.assertIn("session=Depends(get_share_session)", status)

    def test_file_delivery_uses_ticket_and_content_length(self):
        source = ast.unparse(_async_function("download_prepared_job"))
        self.assertIn("ticket: str=Query(...)", source)
        self.assertIn("access_context(job_id, ticket)", source)
        self.assertIn("download_metadata(job_id, ticket)", source)
        self.assertIn("iter_download(job_id, ticket)", source)
        self.assertIn("not share.get('is_active', True)", source)
        self.assertIn("is_share_expired(share)", source)
        self.assertIn("'Content-Length'", source)
        self.assertIn("'Cache-Control': 'no-store'", source)


if __name__ == "__main__":
    unittest.main()
