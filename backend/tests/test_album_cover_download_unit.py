import ast
import unittest
from pathlib import Path

from album_downloads import album_download_name


BACKEND_DIR = Path(__file__).resolve().parents[1]


class AlbumCoverDownloadNameTests(unittest.TestCase):
    def setUp(self):
        self.file_doc = {
            "id": "cover-file-id",
            "subfolder": "Album Favourites",
            "filename": "IMG_1234.jpg",
        }
        self.choice = {"file_id": "cover-file-id"}

    def test_chosen_album_favourite_is_clearly_marked_in_zip(self):
        self.assertEqual(
            album_download_name(self.file_doc, self.choice),
            "COVER - IMG_1234.jpg",
        )

    def test_non_chosen_album_favourite_keeps_original_name(self):
        self.assertEqual(
            album_download_name(self.file_doc, {"file_id": "another-file-id"}),
            "IMG_1234.jpg",
        )

    def test_same_id_outside_album_favourites_is_not_renamed(self):
        file_doc = {**self.file_doc, "subfolder": "Wedding Images"}
        self.assertEqual(album_download_name(file_doc, self.choice), "IMG_1234.jpg")

    def test_missing_choice_keeps_original_name(self):
        self.assertEqual(album_download_name(self.file_doc, None), "IMG_1234.jpg")

    def test_existing_cover_prefix_is_not_duplicated(self):
        file_doc = {**self.file_doc, "filename": "cover - IMG_1234.jpg"}
        self.assertEqual(
            album_download_name(file_doc, self.choice),
            "cover - IMG_1234.jpg",
        )

    def test_download_builder_reads_original_disk_name_but_uses_archive_helper(self):
        tree = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))
        function = next(
            node for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef) and node.name == "_download_entries"
        )
        source = ast.unparse(function)
        self.assertIn("get_gallery_file_path", source)
        self.assertIn("file_doc['filename']", source)
        self.assertIn("album_download_name(file_doc, gallery.get('album_cover_choice'))", source)
        self.assertIn("f\"{file_doc['subfolder']}/{download_name}\"", source)


if __name__ == "__main__":
    unittest.main()
