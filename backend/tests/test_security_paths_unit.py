import tempfile
import unittest
from pathlib import Path

from security_paths import (
    UnsafePathError,
    contained_path,
    sanitise_upload_filename,
    validate_path_component,
)


class SecurityPathTests(unittest.TestCase):
    def test_normal_gallery_names_are_preserved(self):
        values = [
            "Natalie & Max 25.08.26",
            "Wedding Images",
            "DSC_1042 (edited)-final.jpg",
            "Gina + Mark's Album.webp",
        ]
        for value in values:
            with self.subTest(value=value):
                self.assertEqual(validate_path_component(value), value)

    def test_unsafe_path_components_are_rejected(self):
        for value in ["", ".", "..", "../outside", r"..\outside", "bad\x00name"]:
            with self.subTest(value=value):
                with self.assertRaises(UnsafePathError):
                    validate_path_component(value)

    def test_browser_supplied_path_is_reduced_to_its_filename(self):
        self.assertEqual(sanitise_upload_filename(r"C:\fakepath\IMG_0001.JPG"), "IMG_0001.JPG")
        self.assertEqual(sanitise_upload_filename("../../IMG_0002.JPG"), "IMG_0002.JPG")

    def test_contained_path_stays_below_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            expected = root / "Natalie & Max" / "Wedding Images" / "IMG_1.jpg"
            self.assertEqual(
                contained_path(root, "Natalie & Max", "Wedding Images", "IMG_1.jpg"),
                expected,
            )

    def test_contained_path_rejects_symlink_escape(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            outside = root.parent / f"{root.name}-outside"
            outside.mkdir()
            try:
                (root / "linked").symlink_to(outside, target_is_directory=True)
                with self.assertRaises(UnsafePathError):
                    contained_path(root, "linked", "photo.jpg")
            finally:
                outside.rmdir()


if __name__ == "__main__":
    unittest.main()
