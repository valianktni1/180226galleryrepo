"""Small, side-effect-free helpers for the admin system-health summary."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Dict, Iterable


STATUS_RANK = {"neutral": 0, "healthy": 0, "active": 0, "warning": 1, "critical": 2}


def storage_status(used_percent: float) -> str:
    """Classify capacity without treating normal disk use as a fault."""
    if used_percent >= 95:
        return "critical"
    if used_percent >= 85:
        return "warning"
    return "healthy"


def backup_health(status: Dict) -> Dict:
    """Reduce the backup worker state to safe, useful admin information."""
    state = status.get("status", "idle")
    if state in {"queued", "running"}:
        return {
            "status": "active",
            "title": "Backup queued" if state == "queued" else "Backup running",
            "detail": status.get("message") or "Gallery originals are being backed up.",
            "last_completed_at": status.get("finished_at"),
            "progress": {
                "galleries_done": status.get("galleries_done", 0),
                "galleries_total": status.get("galleries_total", 0),
            },
        }
    if state == "complete":
        return {
            "status": "healthy",
            "title": "Last backup completed",
            "detail": status.get("message") or "The last gallery backup completed.",
            "last_completed_at": status.get("finished_at"),
            "progress": None,
        }
    if state == "failed":
        return {
            "status": "warning",
            "title": "Last backup needs attention",
            "detail": "The last in-app gallery backup did not complete. Check the dashboard backup status.",
            "last_completed_at": status.get("finished_at"),
            "progress": None,
        }
    return {
        "status": "neutral",
        "title": "No recorded backup yet",
        "detail": "A result will appear here after the next in-app gallery backup.",
        "last_completed_at": None,
        "progress": None,
    }


def database_backup_health(result: Dict | None, *, warning_after_days: int = 14) -> Dict:
    """Describe the most recent snapshot that completed a temporary restore."""
    if not result or result.get("status") != "verified" or not result.get("verified_at"):
        return {
            "status": "warning",
            "title": "Database restore not verified",
            "detail": "Run the in-app backup to create and test a MongoDB restore snapshot.",
            "last_verified_at": None,
        }
    try:
        verified_at = datetime.fromisoformat(result["verified_at"].replace("Z", "+00:00"))
        age_days = max(0, (datetime.now(timezone.utc) - verified_at).days)
    except (TypeError, ValueError):
        age_days = warning_after_days + 1
    stale = age_days > warning_after_days
    return {
        "status": "warning" if stale else "healthy",
        "title": "Database restore verification is old" if stale else "Database restore verified",
        "detail": (
            f"{result.get('documents', 0):,} records across "
            f"{result.get('collections', 0):,} collections restored and checked."
        ),
        "last_verified_at": result.get("verified_at"),
        "snapshot_name": result.get("snapshot_name"),
        "snapshot_bytes": result.get("bytes", 0),
    }


def overall_status(monitored: Iterable[Dict]) -> str:
    """Return the highest actionable severity from monitored components."""
    highest = 0
    for item in monitored:
        highest = max(highest, STATUS_RANK.get(item.get("status", "neutral"), 0))
    if highest >= 2:
        return "critical"
    if highest == 1:
        return "warning"
    return "healthy"


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()
