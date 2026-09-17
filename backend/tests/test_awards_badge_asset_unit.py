"""Release 1.9.1 checks for the branded email awards artwork."""

import struct
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
ASSET_PATH = BACKEND_DIR / "assets" / "awards-badges.png"
SERVER_PATH = BACKEND_DIR / "server.py"


def test_awards_badge_is_optimised_real_png():
    payload = ASSET_PATH.read_bytes()

    assert payload.startswith(b"\x89PNG\r\n\x1a\n")
    assert len(payload) < 200_000

    width, height = struct.unpack(">II", payload[16:24])
    assert (width, height) == (960, 640)


def test_awards_badge_email_url_is_cache_busted():
    source = SERVER_PATH.read_text(encoding="utf-8")

    assert "awards-badges.png?v=20260916" in source
    assert '<img src="{get_awards_url(smtp)}"' in source
