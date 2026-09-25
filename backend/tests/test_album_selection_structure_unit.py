import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = (ROOT / "server.py").read_text(encoding="utf-8")
SERVER_TREE = ast.parse(SERVER_SOURCE)
FRONTEND_SOURCE = (ROOT.parent / "frontend" / "src" / "pages" / "ShareView.js").read_text(encoding="utf-8")
ADMIN_SOURCE = (ROOT.parent / "frontend" / "src" / "pages" / "AdminGalleryDetail.js").read_text(encoding="utf-8")


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

    def test_client_album_controls_are_conditional_and_counted(self):
        self.assertIn("albumEnabled && <section", FRONTEND_SOURCE)
        self.assertIn("`${favCount}/${albumLimit}`", FRONTEND_SOURCE)
        self.assertIn("Submit Your Album", FRONTEND_SOURCE)
        self.assertIn("confirm-album-submission", FRONTEND_SOURCE)
        self.assertIn("albumLocked ? handleFavourite : null", FRONTEND_SOURCE)

    def test_admin_has_all_three_modes_and_reopen(self):
        self.assertIn("album-mode-${option.mode}", ADMIN_SOURCE)
        self.assertIn("40 + Cover", ADMIN_SOURCE)
        self.assertIn("60 + Cover", ADMIN_SOURCE)
        self.assertIn("Reopen Choices", ADMIN_SOURCE)
        self.assertIn("Email Album Instructions", ADMIN_SOURCE)

    def test_gallery_ready_email_obeys_the_gallery_album_plan(self):
        source = ast.unparse(async_function("send_gallery_notification"))
        self.assertIn("normalise_album_selection(gallery)", source)
        self.assertIn("album_state['mode'] != 'off'", source)
        self.assertIn("exactly <strong>{album_limit} album photos", source)


if __name__ == "__main__":
    unittest.main()
