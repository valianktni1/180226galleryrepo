import ast
import unittest
from pathlib import Path

from broadcast_service import pending_batch, public_campaign, recipient_counts, unique_recipients


BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVER_TREE = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))


def function_source(name):
    node = next(
        item for item in ast.walk(SERVER_TREE)
        if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)) and item.name == name
    )
    return node, ast.unparse(node)


class BroadcastCampaignTests(unittest.TestCase):
    def test_recipient_addresses_are_deduplicated_case_insensitively(self):
        recipients = unique_recipients([
            {"client_email": "Couple@example.com", "folder_name": "First Gallery"},
            {"client_email": " couple@example.com ", "folder_name": "Second Gallery"},
            {"client_email": "other@example.com", "folder_name": "Other Gallery"},
            {"client_email": "", "folder_name": "No Email"},
        ])
        self.assertEqual(len(recipients), 2)
        self.assertEqual(recipients[0]["email"], "Couple@example.com")
        self.assertEqual(recipients[0]["gallery_names"], ["First Gallery", "Second Gallery"])

    def test_batch_is_bounded_and_uses_only_pending_recipients(self):
        campaign = {"recipients": [
            {"id": str(index), "status": "sent" if index == 0 else "pending"}
            for index in range(25)
        ]}
        batch = pending_batch(campaign, 10)
        self.assertEqual(len(batch), 10)
        self.assertTrue(all(recipient["status"] == "pending" for recipient in batch))

    def test_public_progress_contains_no_message_body_or_addresses(self):
        campaign = {
            "id": "campaign-1", "status": "queued", "subject": "News",
            "html_content": "secret body", "attachments": [{"storage_name": "private.bin"}],
            "recipients": [
                {"email": "private@example.com", "status": "sent"},
                {"email": "other@example.com", "status": "pending"},
            ],
        }
        result = public_campaign(campaign)
        rendered = repr(result)
        self.assertEqual(result["sent"], 1)
        self.assertEqual(result["pending"], 1)
        self.assertEqual(result["percent"], 50)
        self.assertNotIn("private@example.com", rendered)
        self.assertNotIn("secret body", rendered)
        self.assertNotIn("private.bin", rendered)

    def test_counts_keep_delivery_states_separate(self):
        counts = recipient_counts([
            {"status": "pending"}, {"status": "sending"},
            {"status": "sent"}, {"status": "failed"},
        ])
        self.assertEqual(counts, {"pending": 1, "sending": 1, "sent": 1, "failed": 1, "total": 4})

    def test_broadcast_route_queues_instead_of_sending_inline(self):
        node, source = function_source("send_broadcast_email")
        self.assertIn("Depends(get_admin)", ast.unparse(node.args))
        self.assertIn("broadcast_campaigns.insert_one(campaign)", source)
        self.assertIn("html.escape", source)
        self.assertNotIn("send_smtp_email", source)

    def test_worker_uses_threaded_smtp_and_configured_batch_size(self):
        _, source = function_source("process_due_broadcast_campaign")
        self.assertIn("pending_batch", source)
        self.assertIn("asyncio.to_thread(send_smtp_email", source)
        self.assertIn("BROADCAST_BATCH_DELAY_SECONDS", source)

    def test_controls_are_admin_authenticated(self):
        for name in (
            "get_current_broadcast_campaign", "pause_broadcast_campaign",
            "resume_broadcast_campaign", "cancel_broadcast_campaign",
        ):
            node, _ = function_source(name)
            self.assertIn("Depends(get_admin)", ast.unparse(node.args))


if __name__ == "__main__":
    unittest.main()
