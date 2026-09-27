"""Narrow deletion boundary for generated gallery housekeeping files."""

from __future__ import annotations

from pathlib import Path
from typing import Dict, Iterable


class MaintenanceCleanupError(ValueError):
    """Raised when a cleanup candidate falls outside its permitted boundary."""


def _contained_candidate(path: Path, root: Path, suffix: str) -> Path:
    candidate = Path(path)
    boundary = Path(root).resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(boundary)
    except ValueError as exc:
        raise MaintenanceCleanupError("Cleanup candidate is outside its permitted directory") from exc
    if not candidate.name.casefold().endswith(suffix):
        raise MaintenanceCleanupError("Cleanup candidate has an unexpected file type")
    return candidate


def _delete_candidates(paths: Iterable[Path], root: Path, suffix: str) -> Dict:
    validated = [_contained_candidate(value, root, suffix) for value in paths]
    deleted = 0
    released = 0
    skipped = 0
    for path in validated:
        try:
            if not path.is_file():
                skipped += 1
                continue
            size = path.stat().st_size
            path.unlink()
            deleted += 1
            released += size
        except FileNotFoundError:
            skipped += 1
    return {"deleted": deleted, "bytes": released, "skipped": skipped}


def clean_generated_files(
    *,
    upload_root: Path,
    thumbnail_root: Path,
    download_cache_root: Path,
    candidates: Dict[str, Iterable[Path]],
) -> Dict:
    """Delete only pre-classified generated files from their exact safe roots."""
    categories = {
        "orphan_derivatives": _delete_candidates(
            candidates.get("orphan_derivatives", []), thumbnail_root, ".jpg"
        ),
        "orphan_web_videos": _delete_candidates(
            candidates.get("orphan_web_videos", []), upload_root, ".web.mp4"
        ),
        "temporary_video_files": _delete_candidates(
            candidates.get("temporary_video_files", []), upload_root, ".web.tmp.mp4"
        ),
        "stale_download_archives": _delete_candidates(
            candidates.get("stale_download_archives", []), download_cache_root, ".zip"
        ),
    }
    return {
        "deleted": sum(item["deleted"] for item in categories.values()),
        "bytes": sum(item["bytes"] for item in categories.values()),
        "skipped": sum(item["skipped"] for item in categories.values()),
        "categories": categories,
    }
