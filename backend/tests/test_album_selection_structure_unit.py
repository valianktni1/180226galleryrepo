import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = (ROOT / "server.py").read_text(encoding="utf-8")
SERVER_TREE = ast.parse(SERVER_SOURCE)


def async_function(name):
    return next(
        node for node in ast.walk(SERVER_TREE)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )


class AlbumSelectionStructureTests(unittest.TestCase):
    def test_admin_mode_and_reopen_routes_are_protected(self):
        for function_name in ("update_album_selection_settings", "reopen_gallery_album_selection"):
            source = ast.unparse(async_function(function_name))
            self.assertIn("admin=Depends(get_admin)", source)

    def test_submit_validates_then_creates_separate_cover_and_locks(self):
        source = ast.unparse(async_function("submit_favourites_to_album"))
        self.assertIn("mark_album_submitted(gallery)", source)
        self.assertIn("client_album_cover", source)
        self.assertIn("COVER - ", source)
        self.assertIn("cover_source['filename']", source)
        self.assertIn("album_selection", source)
        self.assertIn("album_cover_choice", source)

    def test_gallery_ready_email_obeys_the_gallery_album_plan(self):
        source = ast.unparse(async_function("send_gallery_notification"))
        self.assertIn("normalise_album_selection(gallery)", source)
        self.assertIn("album_state['mode'] != 'off'", source)
        self.assertIn("exactly <strong>{album_limit} album photos", source)


if __name__ == "__main__":
    unittest.main()
