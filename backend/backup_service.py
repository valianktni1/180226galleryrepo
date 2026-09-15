"""Low-impact incremental gallery backups.

The backup work deliberately runs outside FastAPI's event loop so a large copy
cannot freeze gallery API requests. Generated browser-playback videos are not
backed up because they can be recreated from the preserved original video.
"""

from __future__ import annotations

import copy
import json
import logging
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Dict, Optional, Tuple

from security_paths import UnsafePathError, contained_path


logger = logging.getLogger(__name__)
ProgressCallback = Callable[[Dict], None]


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def is_generated_backup_file(path: Path) -> bool:
    """Return True for disposable derivatives that must not enter backups."""
    name = path.name.lower()
    return (
        ".thumb." in name
        or ".preview." in name
        or name.endswith(".web.mp4")
        or name.endswith(".web.tmp.mp4")
    )


def incremental_backup(
    source_root: Path,
    backup_root: Path,
    progress: Optional[ProgressCallback] = None,
) -> Dict:
    """Copy changed originals while reporting lightweight progress updates."""
    gallery_folders = sorted(
        (path for path in source_root.iterdir() if path.is_dir() and not path.name.startswith(".")),
        key=lambda path: path.name.casefold(),
    )
    stats = {
        "copied": 0,
        "skipped": 0,
        "excluded": 0,
        "scanned": 0,
        "errors": [],
        "galleries_total": len(gallery_folders),
        "galleries_done": 0,
        "current_gallery": None,
    }

    def report() -> None:
        if progress:
            progress(copy.deepcopy(stats))

    report()
    for gallery_number, gallery_folder in enumerate(gallery_folders, start=1):
        stats["current_gallery"] = gallery_folder.name
        report()

        try:
            backup_gallery_path = contained_path(
                backup_root,
                gallery_folder.name,
                labels=("backup gallery folder name",),
            )
        except UnsafePathError as exc:
            stats["errors"].append(f"Skipped unsafe gallery path {gallery_folder.name}: {exc}")
            stats["galleries_done"] = gallery_number
            report()
            continue

        backup_gallery_path.mkdir(parents=True, exist_ok=True)

        for src_path in gallery_folder.rglob("*"):
            if not src_path.is_file():
                continue

            stats["scanned"] += 1
            if is_generated_backup_file(src_path):
                stats["excluded"] += 1
                if stats["scanned"] % 25 == 0:
                    report()
                continue

            rel_path = src_path.relative_to(gallery_folder)
            try:
                dst_path = contained_path(
                    backup_gallery_path,
                    *rel_path.parts,
                    labels=tuple("backup path component" for _ in rel_path.parts),
                )
            except UnsafePathError as exc:
                stats["errors"].append(f"Skipped unsafe backup path {rel_path}: {exc}")
                continue

            dst_path.parent.mkdir(parents=True, exist_ok=True)
            needs_copy = not dst_path.exists()
            if not needs_copy:
                src_stat = src_path.stat()
                dst_stat = dst_path.stat()
                needs_copy = (
                    src_stat.st_size != dst_stat.st_size
                    or src_stat.st_mtime > dst_stat.st_mtime
                )

            if needs_copy:
                try:
                    shutil.copy2(src_path, dst_path)
                    stats["copied"] += 1
                except Exception as exc:  # Continue backing up other originals.
                    stats["errors"].append(f"{src_path.name}: {exc}")
            else:
                stats["skipped"] += 1

            if stats["scanned"] % 25 == 0 or needs_copy:
                report()

        stats["galleries_done"] = gallery_number
        report()

    stats["current_gallery"] = None
    report()
    return stats


class BackupManager:
    """Own one background backup job and expose a thread-safe status snapshot."""

    def __init__(self, source_root: Path, backup_root: Path, state_file: Optional[Path] = None):
        self.source_root = source_root
        self.backup_root = backup_root
        self.state_file = Path(state_file) if state_file else None
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gallery-backup")
        self._lock = threading.Lock()
        self._state = self._load_state()

    @staticmethod
    def _idle_state() -> Dict:
        return {
            "status": "idle",
            "message": "No backup is currently running.",
            "started_at": None,
            "finished_at": None,
            "copied": 0,
            "skipped": 0,
            "excluded": 0,
            "scanned": 0,
            "errors": [],
            "galleries_total": 0,
            "galleries_done": 0,
            "current_gallery": None,
        }

    def status(self) -> Dict:
        with self._lock:
            return copy.deepcopy(self._state)

    def _load_state(self) -> Dict:
        if not self.state_file or not self.state_file.exists():
            return self._idle_state()
        try:
            state = json.loads(self.state_file.read_text(encoding="utf-8"))
            if not isinstance(state, dict):
                return self._idle_state()
            loaded = self._idle_state()
            loaded.update({key: state[key] for key in loaded if key in state})
            if loaded["status"] == "running":
                loaded.update(
                    status="failed",
                    message="The previous gallery backup was interrupted by an application restart.",
                    finished_at=utc_now_iso(),
                    current_gallery=None,
                )
            return loaded
        except (OSError, ValueError, TypeError):
            return self._idle_state()

    def _persist_state(self) -> None:
        if not self.state_file:
            return
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.state_file.with_suffix(self.state_file.suffix + ".tmp")
            temporary.write_text(json.dumps(self._state), encoding="utf-8")
            temporary.replace(self.state_file)
        except OSError:
            logger.warning("Could not persist gallery backup status", exc_info=True)

    def start(self) -> Tuple[bool, Dict]:
        with self._lock:
            if self._state["status"] == "running":
                return False, copy.deepcopy(self._state)

            self._state = self._idle_state()
            self._state.update(
                status="running",
                message="Backup started.",
                started_at=utc_now_iso(),
            )
            self._persist_state()
            state = copy.deepcopy(self._state)

        self._executor.submit(self._run)
        return True, state

    def _set_progress(self, stats: Dict) -> None:
        with self._lock:
            self._state.update(stats)
            self._state["status"] = "running"

    def _run(self) -> None:
        try:
            stats = incremental_backup(self.source_root, self.backup_root, self._set_progress)
            message = (
                f"Backup complete. {stats['copied']} original files copied, "
                f"{stats['skipped']} unchanged, {stats['excluded']} generated files excluded."
            )
            with self._lock:
                self._state.update(stats)
                self._state.update(
                    status="complete",
                    message=message,
                    finished_at=utc_now_iso(),
                    current_gallery=None,
                )
                self._persist_state()
            logger.info(message)
        except Exception as exc:
            logger.exception("Gallery backup failed")
            with self._lock:
                self._state.update(
                    status="failed",
                    message=f"Backup failed: {exc}",
                    finished_at=utc_now_iso(),
                    current_gallery=None,
                )
                self._persist_state()
