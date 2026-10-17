import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SERVER_SOURCE = (ROOT / "server.py").read_text(encoding="utf-8")
SERVER_TREE = ast.parse(SERVER_SOURCE)


def async_function(name: str) -> ast.AsyncFunctionDef:
    return next(
        node
        for node in SERVER_TREE.body
        if isinstance(node, ast.AsyncFunctionDef) and node.name == name
    )


def rendered_function(name: str) -> str:
    return ast.unparse(async_function(name))


def awaited_database_calls_inside_loops(name: str):
    function = async_function(name)
    calls = []
    for node in ast.walk(function):
        if not isinstance(node, (ast.For, ast.AsyncFor, ast.While)):
            continue
        for child in ast.walk(node):
            if isinstance(child, ast.Await):
                calls.append(ast.unparse(child.value))
    return calls


class Release223PerformanceTests(unittest.TestCase):
    def test_gallery_cards_use_batched_share_and_cover_queries(self):
        source = rendered_function("list_galleries")
        self.assertIn("db.shares.aggregate", source)
        self.assertIn("db.files.aggregate", source)
        self.assertIn("chosen_cover_ids", source)
        self.assertIn("first_photos", source)
        self.assertNotIn("count_documents", source)
        self.assertEqual(awaited_database_calls_inside_loops("list_galleries"), [])

    def test_gallery_stats_use_one_visitor_aggregation(self):
        source = rendered_function("get_all_galleries_stats")
        self.assertIn("db.activity_log.aggregate", source)
        self.assertIn("total_views", source)
        self.assertIn("total_downloads", source)
        self.assertNotIn(".distinct", source)
        self.assertNotIn("find_one", source)
        self.assertEqual(
            awaited_database_calls_inside_loops("get_all_galleries_stats"), []
        )


if __name__ == "__main__":
    unittest.main()
