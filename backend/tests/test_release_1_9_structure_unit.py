import ast
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
TREE = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))


def async_function(name):
    return next(node for node in ast.walk(TREE) if isinstance(node, ast.AsyncFunctionDef) and node.name == name)


def function(name):
    return next(node for node in ast.walk(TREE) if isinstance(node, ast.FunctionDef) and node.name == name)


class Release19StructureTests(unittest.TestCase):
    def test_readiness_is_admin_only_and_explicitly_photo_only(self):
        route = ast.unparse(async_function("get_gallery_readiness"))
        context = ast.unparse(async_function("_gallery_readiness_context"))
        self.assertIn("admin=Depends(get_admin)", route)
        self.assertIn("'file_type': 'photo'", context)
        self.assertNotIn("video_health", context)
        self.assertIn("main_gallery_share_query(gallery_id)", context)
        self.assertIn("not is_share_expired(candidate)", context)

    def test_notify_rechecks_readiness_and_blocks_critical_failures(self):
        source = ast.unparse(async_function("send_gallery_notification"))
        self.assertIn("_gallery_readiness_context(gallery, request)", source)
        self.assertIn("if not readiness['ready']", source)
        self.assertIn("readiness['preview']['gallery_link']", source)

    def test_maintenance_scan_is_admin_only_read_only_and_off_event_loop(self):
        source = ast.unparse(async_function("get_maintenance_scan"))
        self.assertIn("admin=Depends(get_admin)", source)
        self.assertIn("await asyncio.to_thread", source)
        maintenance_source = (BACKEND_DIR / "maintenance_scan.py").read_text(encoding="utf-8")
        for destructive_call in ("unlink(", "rmtree(", "remove(", "rename(", "replace("):
            self.assertNotIn(destructive_call, maintenance_source)

    def test_video_jobs_are_visible_from_the_moment_they_are_queued(self):
        queue_source = ast.unparse(function("queue_video_transcode"))
        health_source = ast.unparse(async_function("get_system_health"))
        self.assertIn("'status': 'queued'", queue_source)
        self.assertIn("'video_queue': video_queue", health_source)


if __name__ == "__main__":
    unittest.main()
