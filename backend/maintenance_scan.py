"""Read-only filesystem checks for the gallery maintenance screen."""

from __future__ import annotations

import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Set, Tuple


def _sample_label(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return path.name


def _bucket(paths, root: Path, sample_limit: int = 8) -> Dict:
    paths = list(paths)
    size = 0
    for path in paths:
        try:
            size += path.stat().st_size
        except OSError:
            pass
    return {
        "count": len(paths),
        "bytes": size,
        "samples": [_sample_label(path, root) for path in paths[:sample_limit]],
    }


def scan_gallery_maintenance(
    *,
    upload_root: Path,
    thumbnail_root: Path,
    download_cache_root: Path,
    expected_originals: Iterable[Tuple[Path, str]],
    known_original_paths: Set[Path],
    expected_derivatives: Set[Path],
    expected_web_videos: Set[Path],
    stale_download_seconds: int = 4 * 60 * 60,
) -> Dict:
    """Inspect known paths without deleting, renaming or writing anything."""
    upload_root = Path(upload_root)
    thumbnail_root = Path(thumbnail_root)
    download_cache_root = Path(download_cache_root)

    missing_labels = []
    originals_checked = 0
    for path, label in expected_originals:
        originals_checked += 1
        if not path.is_file():
            missing_labels.append(label)

    derivative_files = []
    if thumbnail_root.exists():
        derivative_files = [path for path in thumbnail_root.rglob("*") if path.is_file()]
    orphan_derivatives = [path for path in derivative_files if path not in expected_derivatives]

    orphan_web = []
    temporary_video = []
    for gallery_path in upload_root.iterdir() if upload_root.exists() else []:
        if not gallery_path.is_dir() or gallery_path.name.startswith("."):
            continue
        orphan_web.extend(
            path for path in gallery_path.rglob("*.web.mp4")
            if path not in expected_web_videos and path not in known_original_paths
        )
        temporary_video.extend(
            path for path in gallery_path.rglob("*.web.tmp.mp4")
            if path not in known_original_paths
        )

    cutoff = time.time() - stale_download_seconds
    stale_archives = []
    if download_cache_root.exists():
        for path in download_cache_root.glob("*.zip"):
            try:
                if path.stat().st_mtime < cutoff:
                    stale_archives.append(path)
            except OSError:
                pass

    derivatives = _bucket(orphan_derivatives, upload_root)
    web_videos = _bucket(orphan_web, upload_root)
    temporary = _bucket(temporary_video, upload_root)
    archives = _bucket(stale_archives, upload_root)
    issue_count = len(missing_labels) + derivatives["count"] + web_videos["count"] + temporary["count"] + archives["count"]
    reclaimable = derivatives["bytes"] + web_videos["bytes"] + temporary["bytes"] + archives["bytes"]

    return {
        "status": "clean" if issue_count == 0 else "attention",
        "read_only": True,
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "issues": issue_count,
            "originals_checked": originals_checked,
            "reclaimable_bytes": reclaimable,
        },
        "missing_originals": {
            "count": len(missing_labels),
            "bytes": 0,
            "samples": missing_labels[:8],
        },
        "orphan_derivatives": derivatives,
        "orphan_web_videos": web_videos,
        "temporary_video_files": temporary,
        "stale_download_archives": archives,
    }
