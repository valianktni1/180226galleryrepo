import ast
import unittest
from pathlib import Path

from system_health import backup_health, overall_status, storage_status


BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVER_TREE = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))


class SystemHealthTests(unittest.TestCase):
    def test_storage_thresholds_are_clear(self):
        self.assertEqual(storage_status(50), "healthy")
        self.assertEqual(storage_status(85), "warning")
        self.assertEqual(storage_status(95), "critical")

    def test_external_and_active_items_do_not_create_false_warnings(self):
        self.assertEqual(overall_status([{"status": "healthy"}, {"status": "neutral"}, {"status": "active"}]), "healthy")
        self.assertEqual(overall_status([{"status": "warning"}]), "warning")
        self.assertEqual(overall_status([{"status": "critical"}, {"status": "warning"}]), "critical")

    def test_backup_failure_does_not_expose_raw_error_text(self):
        result = backup_health({"status": "failed", "message": "secret path and internal exception", "finished_at": "now"})
        self.assertEqual(result["status"], "warning")
        self.assertNotIn("secret", result["detail"])

    def test_health_route_is_admin_only_and_read_only(self):
        route = next(
            node for node in ast.walk(SERVER_TREE)
            if isinstance(node, ast.AsyncFunctionDef) and node.name == "get_system_health"
        )
        decorators = ast.unparse(route.decorator_list)
        arguments = ast.unparse(route.args)
        source = ast.unparse(route)
        self.assertIn("/admin/system-health", decorators)
        self.assertIn("Depends(get_admin)", arguments)
        self.assertNotIn("update_one", source)
        self.assertNotIn("delete_one", source)
        self.assertNotIn("insert_one", source)
        self.assertNotIn("subprocess", source)
        self.assertNotIn("active_visitors[key]", source)


if __name__ == "__main__":
    unittest.main()
