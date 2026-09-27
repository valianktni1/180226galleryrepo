"""Small FIFO coordinator for disk and CPU intensive background work.

The gallery has several independent worker pools.  Without coordination, a
backup, ZIP preparation and two video transcodes can all hit the same storage
at once.  This module gives those workers one shared, bounded queue while
leaving lightweight API requests completely outside it.
"""

from __future__ import annotations

import copy
import threading
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Dict, Iterator


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class HeavyJobCoordinator:
    """Coordinate heavyweight jobs fairly, with optional exclusive work."""

    def __init__(self, max_parallel: int = 2):
        if max_parallel < 1:
            raise ValueError("max_parallel must be at least one")
        self.max_parallel = max_parallel
        self._condition = threading.Condition()
        self._waiting = []
        self._active: Dict[str, Dict] = {}

    def _can_start(self, request: Dict) -> bool:
        if not self._waiting or self._waiting[0]["id"] != request["id"]:
            return False
        if request["exclusive"]:
            return not self._active
        if any(item["exclusive"] for item in self._active.values()):
            return False
        return len(self._active) < self.max_parallel

    @contextmanager
    def acquire(self, kind: str, *, exclusive: bool = False) -> Iterator[None]:
        """Wait in FIFO order, run the job, then release its shared permit."""
        request = {
            "id": str(uuid.uuid4()),
            "kind": kind,
            "exclusive": bool(exclusive),
            "queued_at": _utc_now_iso(),
            "started_at": None,
        }
        with self._condition:
            self._waiting.append(request)
            self._condition.notify_all()
            while not self._can_start(request):
                self._condition.wait()
            self._waiting.pop(0)
            request["started_at"] = _utc_now_iso()
            self._active[request["id"]] = request
            self._condition.notify_all()

        try:
            yield
        finally:
            with self._condition:
                self._active.pop(request["id"], None)
                self._condition.notify_all()

    def snapshot(self) -> Dict:
        """Return aggregate, secret-free queue information for System Health."""
        with self._condition:
            waiting = copy.deepcopy(self._waiting)
            active = copy.deepcopy(list(self._active.values()))
        kinds = sorted({item["kind"] for item in waiting + active})
        return {
            "max_parallel": self.max_parallel,
            "active": len(active),
            "waiting": len(waiting),
            "exclusive_active": any(item["exclusive"] for item in active),
            "by_kind": {
                kind: {
                    "active": sum(item["kind"] == kind for item in active),
                    "waiting": sum(item["kind"] == kind for item in waiting),
                }
                for kind in kinds
            },
        }
