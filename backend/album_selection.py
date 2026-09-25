"""Pure rules for the optional per-gallery wedding-album workflow.

The selection is stored on the gallery rather than against a browser session so
both members of a couple see the same progress and a refresh/device change does
not create a second set of choices.
"""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone


ALBUM_MODES = {"off": 0, "40": 40, "60": 60}
MAX_HISTORY_ITEMS = 50


class AlbumSelectionError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def default_album_selection() -> dict:
    return {
        "mode": "off",
        "limit": 40,
        "selected_file_ids": [],
        "cover_file_id": None,
        "cover_filename": None,
        "status": "open",
        "locked": False,
        "submitted_at": None,
        "revision": 0,
        "history": [],
    }


def normalise_album_selection(gallery: dict | None) -> dict:
    """Return a complete, backwards-compatible selection state."""
    state = default_album_selection()
    raw = (gallery or {}).get("album_selection") or {}
    if isinstance(raw, dict):
        state.update(deepcopy(raw))

    mode = str(state.get("mode", "off"))
    if mode not in ALBUM_MODES:
        mode = "off"
    state["mode"] = mode
    state["limit"] = ALBUM_MODES[mode] or (
        int(state.get("limit", 40)) if state.get("limit") in (40, 60) else 40
    )
    state["selected_file_ids"] = list(dict.fromkeys(
        str(file_id) for file_id in (state.get("selected_file_ids") or []) if file_id
    ))
    state["locked"] = bool(state.get("locked", False))
    state["status"] = "submitted" if state["locked"] else "open"
    state["revision"] = max(0, int(state.get("revision", 0) or 0))
    state["history"] = list(state.get("history") or [])[-MAX_HISTORY_ITEMS:]
    return state


def album_selection_available(gallery: dict, share: dict | None) -> bool:
    """Only a full, downloadable couple gallery may expose album controls."""
    state = normalise_album_selection(gallery)
    if state["mode"] == "off" or not share:
        return False
    return (
        not share.get("guest_upload_mode", False)
        and share.get("subfolder") is None
        and share.get("access_level", "download") in ("download", "full")
    )


def public_album_selection(gallery: dict, share: dict | None) -> dict:
    state = normalise_album_selection(gallery)
    submitted_cover = (gallery or {}).get("album_cover_choice") or {}
    available = album_selection_available(gallery, share)
    if not available:
        return {"enabled": False}
    selected_count = len(state["selected_file_ids"])
    return {
        "enabled": True,
        "mode": state["mode"],
        "limit": state["limit"],
        "selected_count": selected_count,
        "selected_file_ids": state["selected_file_ids"],
        "cover_file_id": state.get("cover_file_id"),
        "cover_output_file_id": submitted_cover.get("file_id") if state["locked"] else None,
        "cover_filename": state.get("cover_filename"),
        "cover_selected": bool(state.get("cover_file_id")),
        "status": state["status"],
        "locked": state["locked"],
        "submitted_at": state.get("submitted_at"),
        "revision": state["revision"],
        "ready_to_submit": (
            not state["locked"]
            and selected_count == state["limit"]
            and bool(state.get("cover_file_id"))
        ),
    }


def _history(state: dict, action: str, *, at: str | None = None, **details) -> None:
    state["history"] = [
        *(state.get("history") or []),
        {"action": action, "at": at or utc_now_iso(), **details},
    ][-MAX_HISTORY_ITEMS:]


def set_album_mode(gallery: dict, mode: str, *, at: str | None = None) -> dict:
    if mode not in ALBUM_MODES:
        raise AlbumSelectionError("Album mode must be Off, 40 photos + cover, or 60 photos + cover")

    state = normalise_album_selection(gallery)
    selected_count = len(state["selected_file_ids"])
    new_limit = ALBUM_MODES[mode] or state["limit"]
    if mode == "40" and selected_count > 40:
        raise AlbumSelectionError(
            f"This couple has already selected {selected_count} photos. Remove choices before changing the plan to 40.",
            409,
        )

    previous_mode = state["mode"]
    previous_limit = state["limit"]
    state["mode"] = mode
    if mode != "off":
        state["limit"] = new_limit
        # A completed 40-photo submission cannot remain "complete" after an
        # upgrade to 60 (and vice versa). Reopen it automatically while keeping
        # every choice, so the couple can finish the newly selected plan.
        if state["locked"] and new_limit != previous_limit:
            state["locked"] = False
            state["status"] = "open"
            _history(
                state,
                "reopened_for_plan_change",
                at=at,
                from_limit=previous_limit,
                to_limit=new_limit,
                revision=state["revision"],
            )
    _history(
        state,
        "mode_changed",
        at=at,
        from_mode=previous_mode,
        to_mode=mode,
        selected_count=selected_count,
    )
    return state


def toggle_album_photo(gallery: dict, file_id: str, *, at: str | None = None) -> tuple[dict, bool]:
    state = normalise_album_selection(gallery)
    if state["mode"] == "off":
        raise AlbumSelectionError("Album selection is not enabled for this gallery", 403)
    if state["locked"]:
        raise AlbumSelectionError("These album choices have been submitted and are locked", 423)

    selected = list(state["selected_file_ids"])
    if file_id in selected:
        selected.remove(file_id)
        selected_now = False
    else:
        if len(selected) >= state["limit"]:
            raise AlbumSelectionError(
                f"You have selected all {state['limit']} album photos. Remove one before choosing another.",
                409,
            )
        selected.append(file_id)
        selected_now = True
    state["selected_file_ids"] = selected
    return state, selected_now


def choose_album_cover_state(
    gallery: dict,
    file_id: str,
    filename: str,
    *,
    at: str | None = None,
) -> dict:
    state = normalise_album_selection(gallery)
    if state["mode"] == "off":
        raise AlbumSelectionError("Album selection is not enabled for this gallery", 403)
    if state["locked"]:
        raise AlbumSelectionError("These album choices have been submitted and are locked", 423)
    state["cover_file_id"] = file_id
    state["cover_filename"] = filename
    state["cover_chosen_at"] = at or utc_now_iso()
    return state


def mark_album_submitted(gallery: dict, *, at: str | None = None) -> dict:
    state = normalise_album_selection(gallery)
    selected_count = len(state["selected_file_ids"])
    if state["mode"] == "off":
        raise AlbumSelectionError("Album selection is not enabled for this gallery", 403)
    if state["locked"]:
        raise AlbumSelectionError("These album choices have already been submitted", 409)
    if selected_count != state["limit"]:
        raise AlbumSelectionError(
            f"Please choose exactly {state['limit']} album photos before submitting. You currently have {selected_count}.",
            409,
        )
    if not state.get("cover_file_id"):
        raise AlbumSelectionError("Please choose one separate cover photo before submitting", 409)

    submitted_at = at or utc_now_iso()
    state["locked"] = True
    state["status"] = "submitted"
    state["submitted_at"] = submitted_at
    state["revision"] += 1
    _history(
        state,
        "submitted",
        at=submitted_at,
        revision=state["revision"],
        selected_count=selected_count,
        cover_filename=state.get("cover_filename"),
    )
    return state


def reopen_album_selection(gallery: dict, *, at: str | None = None) -> dict:
    state = normalise_album_selection(gallery)
    if state["mode"] == "off":
        raise AlbumSelectionError("Enable an album plan before reopening choices", 409)
    if not state["locked"]:
        raise AlbumSelectionError("Album choices are already open", 409)
    state["locked"] = False
    state["status"] = "open"
    _history(state, "reopened", at=at, revision=state["revision"])
    return state
