import ast
import unittest
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
SERVER_TREE = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))


def _async_function(name: str) -> ast.AsyncFunctionDef:
    return next(
        node
        for node in ast.walk(SERVER_TREE)
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )


class AddSubfolderTests(unittest.TestCase):
    def test_route_is_admin_protected_and_validates_the_name(self):
        function = _async_function("create_subfolder")
        source = ast.unparse(function)
        decorators = [ast.unparse(item) for item in function.decorator_list]

        self.assertIn(
            "api_router.post('/admin/galleries/{gallery_id}/subfolders')",
            decorators,
        )
        self.assertIn("admin=Depends(get_admin)", source)
        self.assertIn("require_safe_component(data.name, 'subfolder name')", source)

    def test_duplicate_names_are_refused_case_insensitively(self):
        source = ast.unparse(_async_function("create_subfolder"))
        self.assertIn("name.casefold() == subfolder_name.casefold()", source)
        self.assertIn("A folder with this name already exists", source)

    def test_only_additive_folder_operations_are_used(self):
        source = ast.unparse(_async_function("create_subfolder"))
        self.assertIn("get_gallery_subfolder_path", source)
        self.assertIn("folder_path.mkdir(parents=True, exist_ok=True)", source)
        self.assertIn("updated_subfolders", source)
        self.assertIn("updated_counts[subfolder_name] = 0", source)
        self.assertNotIn("unlink", source)
        self.assertNotIn("rmtree", source)
        self.assertNotIn("delete_", source)


if __name__ == "__main__":
    unittest.main()
