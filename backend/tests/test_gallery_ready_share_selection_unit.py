"""Regression tests for the gallery-ready email share-selection hotfix."""

import ast
import sys
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from share_selection import main_gallery_share_query


def test_main_gallery_share_query_excludes_guest_and_subfolder_shares():
    query = main_gallery_share_query("gallery-123")

    assert query == {
        "gallery_id": "gallery-123",
        "is_active": True,
        "guest_upload_mode": {"$ne": True},
        "subfolder": None,
        "access_level": {"$in": ["download", "full"]},
    }


def test_gallery_ready_endpoint_uses_guarded_main_share_query():
    tree = ast.parse((BACKEND_DIR / "server.py").read_text(encoding="utf-8"))
    notify_function = next(
        node
        for node in tree.body
        if isinstance(node, ast.AsyncFunctionDef)
        and node.name == "send_gallery_notification"
    )

    assert "main_gallery_share_query(gallery_id)" in ast.unparse(notify_function)
