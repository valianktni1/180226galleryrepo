"""Disk-backed gallery ZIP jobs with bounded, thread-safe progress tracking."""

from __future__ import annotations

import copy
import secrets
import shutil
import threading
import time
import uuid
import zipfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


class DownloadJobError(ValueError):
    """Raised when a download job cannot be accessed or used."""


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_download_name(value: str) -> str:
    cleaned = value.replace("/", "_").replace("\\", "_")
    cleaned = cleaned.replace("\r", "_").replace("\n", "_").replace('"', "_")
    return cleaned or "gallery-download.zip"


class DownloadJobManager:
    """Prepare ZIP files off the request thread and stream them with progress."""

    def __init__(self, cache_dir: Path, ttl_seconds: int = 4 * 60 * 60):
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = ttl_seconds
        # One preparer keeps large archive work from saturating the gallery disks.
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gallery-download")
        self._lock = threading.Lock()
        self._jobs: Dict[str, Dict] = {}
        self.remove_stale_archives()

    def remove_stale_archives(self) -> None:
        """Remove abandoned archives left behind by an interrupted container."""
        cutoff = time.time() - self.ttl_seconds
        with self._lock:
            active_paths = {job["archive_path"] for job in self._jobs.values()}
        for path in self.cache_dir.glob("*.zip"):
            try:
                if path not in active_paths and path.stat().st_mtime < cutoff:
                    path.unlink()
            except OSError:
                pass

    def _cleanup_expired(self) -> None:
        now = time.time()
        expired: List[Tuple[str, Path]] = []
        with self._lock:
            for job_id, job in list(self._jobs.items()):
                if job["status"] in {"preparing", "downloading"}:
                    continue
                if now - job["created_ts"] > self.ttl_seconds:
                    expired.append((job_id, job["archive_path"]))
                    del self._jobs[job_id]
        for _, path in expired:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass
        self.remove_stale_archives()

    @staticmethod
    def _public(job: Dict) -> Dict:
        state = {
            key: copy.deepcopy(value)
            for key, value in job.items()
            if key not in {"ticket", "archive_path", "entries", "owner_kind", "owner_id", "share_token", "created_ts", "claimed"}
        }
        if job["status"] == "preparing":
            total = job["source_bytes_total"]
            state["percent"] = min(100, round((job["bytes_prepared"] / total) * 100)) if total else 0
        elif job["status"] in {"ready", "complete"}:
            state["percent"] = 100
        elif job["status"] == "downloading":
            total = job["bytes_total"]
            state["percent"] = min(100, round((job["bytes_sent"] / total) * 100)) if total else 0
        else:
            state["percent"] = 0
        return state

    def start(
        self,
        *,
        owner_kind: str,
        owner_id: str,
        gallery_id: str,
        label: str,
        filename: str,
        entries: Iterable[Tuple[Path, str]],
        share_token: str | None = None,
    ) -> Tuple[Dict, str]:
        self._cleanup_expired()
        entry_list = [(Path(path), arcname) for path, arcname in entries]
        if not entry_list:
            raise DownloadJobError("No files are available to download")

        with self._lock:
            owner_job = next((
                job for job in self._jobs.values()
                if job["owner_kind"] == owner_kind
                and job["owner_id"] == owner_id
                and job["status"] in {"queued", "preparing", "ready", "downloading"}
            ), None)
            active_jobs = sum(
                job["status"] in {"queued", "preparing", "ready", "downloading"}
                for job in self._jobs.values()
            )
            if owner_job and owner_job["gallery_id"] == gallery_id and owner_job["label"] == label:
                return self._public(owner_job), owner_job["ticket"]
        if owner_job:
            raise DownloadJobError("A folder download is already in progress")
        if active_jobs >= 3:
            raise DownloadJobError("The download service is busy. Please try again shortly")

        source_bytes_total = sum(path.stat().st_size for path, _ in entry_list)
        required_free_space = source_bytes_total + (512 * 1024 * 1024)
        if shutil.disk_usage(self.cache_dir).free < required_free_space:
            raise DownloadJobError("There is not enough temporary space to prepare this download")

        job_id = str(uuid.uuid4())
        ticket = secrets.token_urlsafe(32)
        archive_path = self.cache_dir / f"{job_id}.zip"
        job = {
            "id": job_id,
            "owner_kind": owner_kind,
            "owner_id": owner_id,
            "share_token": share_token,
            "gallery_id": gallery_id,
            "label": label,
            "filename": _safe_download_name(filename),
            "status": "queued",
            "message": "Waiting to prepare your ZIP file…",
            "files_total": len(entry_list),
            "files_done": 0,
            "source_bytes_total": source_bytes_total,
            "bytes_prepared": 0,
            "bytes_total": 0,
            "bytes_sent": 0,
            "created_at": _utc_now_iso(),
            "finished_at": None,
            "error": None,
            "ticket": ticket,
            "archive_path": archive_path,
            "entries": entry_list,
            "created_ts": time.time(),
            "claimed": False,
        }
        with self._lock:
            self._jobs[job_id] = job
            initial_state = self._public(job)
        self._executor.submit(self._prepare, job_id)
        return initial_state, ticket

    def _prepare(self, job_id: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if not job:
                return
            job["status"] = "preparing"
            job["message"] = "Preparing ZIP…"
            entries = list(job["entries"])
            archive_path = job["archive_path"]

        try:
            with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_STORED, allowZip64=True) as archive:
                for file_number, (source_path, arcname) in enumerate(entries, start=1):
                    info = zipfile.ZipInfo.from_file(source_path, arcname=arcname)
                    info.compress_type = zipfile.ZIP_STORED
                    with source_path.open("rb") as source, archive.open(info, "w", force_zip64=True) as target:
                        while True:
                            chunk = source.read(8 * 1024 * 1024)
                            if not chunk:
                                break
                            target.write(chunk)
                            with self._lock:
                                current = self._jobs.get(job_id)
                                if not current:
                                    return
                                current["bytes_prepared"] += len(chunk)
                    with self._lock:
                        current = self._jobs.get(job_id)
                        if not current:
                            return
                        current["files_done"] = file_number

            with self._lock:
                current = self._jobs.get(job_id)
                if not current:
                    return
                current["bytes_total"] = archive_path.stat().st_size
                current["status"] = "ready"
                current["message"] = "ZIP ready. Your browser download is starting…"
        except Exception as exc:
            try:
                archive_path.unlink(missing_ok=True)
            except OSError:
                pass
            with self._lock:
                current = self._jobs.get(job_id)
                if current:
                    current["status"] = "failed"
                    current["error"] = str(exc)
                    current["message"] = "The ZIP could not be prepared. Please try again."
                    current["finished_at"] = _utc_now_iso()

    def status(self, job_id: str, *, owner_kind: str, owner_id: str) -> Dict:
        self._cleanup_expired()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or job["owner_kind"] != owner_kind or job["owner_id"] != owner_id:
                raise DownloadJobError("Download job not found")
            return self._public(job)

    def claim(self, job_id: str, ticket: str) -> Tuple[Path, str]:
        self._cleanup_expired()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not secrets.compare_digest(job["ticket"], ticket):
                raise DownloadJobError("Download job not found")
            if job["status"] != "ready" or job["claimed"]:
                raise DownloadJobError("Download is not ready")
            job["claimed"] = True
            job["status"] = "downloading"
            job["message"] = "Downloading ZIP…"
            job["bytes_sent"] = 0
            return job["archive_path"], job["filename"]

    def iter_download(self, job_id: str, ticket: str, chunk_size: int = 1024 * 1024):
        archive_path, _ = self.claim(job_id, ticket)
        completed = False
        try:
            with archive_path.open("rb") as archive:
                while True:
                    chunk = archive.read(chunk_size)
                    if not chunk:
                        completed = True
                        break
                    with self._lock:
                        job = self._jobs.get(job_id)
                        if job:
                            job["bytes_sent"] += len(chunk)
                    yield chunk
        finally:
            with self._lock:
                job = self._jobs.get(job_id)
                if job:
                    if completed:
                        job["status"] = "complete"
                        job["message"] = "Download complete."
                        job["finished_at"] = _utc_now_iso()
                    else:
                        job["status"] = "failed"
                        job["message"] = "Download interrupted. Please press Download All to try again."
                        job["finished_at"] = _utc_now_iso()
                        job["claimed"] = False
            try:
                archive_path.unlink(missing_ok=True)
            except OSError:
                pass

    def download_metadata(self, job_id: str, ticket: str) -> Dict:
        """Return immutable response metadata before the stream claims the job."""
        self._cleanup_expired()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not secrets.compare_digest(job["ticket"], ticket):
                raise DownloadJobError("Download job not found")
            if job["status"] != "ready" or job["claimed"]:
                raise DownloadJobError("Download is not ready")
            return {"filename": job["filename"], "bytes_total": job["bytes_total"]}

    def access_context(self, job_id: str, ticket: str) -> Dict:
        """Return the minimum private context needed to revalidate a share."""
        self._cleanup_expired()
        with self._lock:
            job = self._jobs.get(job_id)
            if not job or not secrets.compare_digest(job["ticket"], ticket):
                raise DownloadJobError("Download job not found")
            return {
                "owner_kind": job["owner_kind"],
                "gallery_id": job["gallery_id"],
                "label": job["label"],
                "share_token": job["share_token"],
            }

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
