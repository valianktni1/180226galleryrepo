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
    if state == "running":
        return {
            "status": "active",
            "title": "Backup running",
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
