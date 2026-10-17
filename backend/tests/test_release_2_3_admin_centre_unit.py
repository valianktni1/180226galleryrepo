import ast
import unittest
from datetime import datetime, timezone
from pathlib import Path

from admin_notifications import daily_group_key
from gallery_workflow import normalise_gallery_workflow_status, workflow_change


ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = (ROOT / "server.py").read_text(encoding="utf-8")


class GalleryWorkflowTests(unittest.TestCase):
    def test_existing_delivered_and_album_galleries_are_inferred_safely(self):
        self.assertEqual(
            normalise_gallery_workflow_status({"notification_sent_at": "2026-01-01"}),
            "delivered",
        )
        self.assertEqual(
            normalise_gallery_workflow_status({
                "album_selection": {"mode": "40", "locked": True},
            }),
            "album_choices_received",
        )

    def test_album_stage_is_rejected_when_album_is_off(self):
        with self.assertRaisesRegex(ValueError, "switched off"):
            workflow_change(
                {"album_selection": {"mode": "off"}},
                "album_choices_received",
                source="admin",
            )

    def test_workflow_change_records_previous_status_and_source(self):
        change = workflow_change(
            {"workflow_status": "ready", "album_selection": {"mode": "40"}},
            "delivered",
            source="gallery_notification",
            now=datetime(2026, 1, 2, tzinfo=timezone.utc),
        )
        self.assertTrue(change["changed"])
        self.assertEqual(change["history"]["from"], "ready")
        self.assertEqual(change["history"]["to"], "delivered")


class AdminNotificationTests(unittest.TestCase):
    def test_daily_upload_groups_are_separate_by_type(self):
        now = datetime(2026, 1, 2, tzinfo=timezone.utc)
        self.assertEqual(daily_group_key("guest_upload", "gallery-1", now), "guest_upload:gallery-1:2026-01-02")
        self.assertEqual(daily_group_key("voice_message", "gallery-1", now), "voice_message:gallery-1:2026-01-02")

    def test_release_hooks_and_protected_endpoints_are_present(self):
        tree = ast.parse(SERVER_SOURCE)
        function_names = {
            node.name for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        for name in {
            "list_admin_notifications",
            "get_admin_notification_count",
            "mark_admin_notification_read",
            "mark_all_admin_notifications_read",
            "dismiss_admin_notification",
            "update_gallery_workflow_status",
        }:
            self.assertIn(name, function_names)
        self.assertIn('event_type="guest_upload"', SERVER_SOURCE)
        self.assertIn('event_type="voice_message"', SERVER_SOURCE)
        self.assertIn('event_type="album_submission"', SERVER_SOURCE)
        self.assertIn('event_type="download_complete"', SERVER_SOURCE)


if __name__ == "__main__":
    unittest.main()
