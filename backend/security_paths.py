"""Filesystem safety helpers for gallery-owned files.

The gallery application intentionally preserves human-readable couple, folder,
and file names. These helpers keep that behaviour while preventing a supplied
name from escaping its configured storage root.
"""

from pathlib import Path


class UnsafePathError(ValueError):
    """Raised when an untrusted path component is unsafe."""


def validate_path_component(value: str, label: str = "path component") -> str:
    """Validate one literal path component without changing normal names."""
    if not isinstance(value, str):
        raise UnsafePathError(f"Invalid {label}")

    value = value.strip()
    if not value or value in {".", ".."}:
        raise UnsafePathError(f"Invalid {label}")
    if "/" in value or "\\" in value or "\x00" in value:
        raise UnsafePathError(f"Invalid {label}")
    if any(ord(char) < 32 for char in value):
        raise UnsafePathError(f"Invalid {label}")
    if len(value.encode("utf-8")) > 240:
        raise UnsafePathError(f"{label.capitalize()} is too long")
    return value


def sanitise_upload_filename(filename: str | None) -> str:
    """Return a safe basename while retaining ordinary punctuation and spacing."""
    if not filename:
        return "unnamed_file"

    # Browsers normally send a basename, but some clients include a local path.
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1]
    return validate_path_component(basename, "filename")


def contained_path(root: Path, *components: str, labels: tuple[str, ...] | None = None) -> Path:
    """Build a resolved path and prove that it remains below ``root``."""
    root_resolved = root.resolve()
    safe_components = []
    for index, component in enumerate(components):
        label = labels[index] if labels and index < len(labels) else "path component"
        safe_components.append(validate_path_component(component, label))

    candidate = root_resolved.joinpath(*safe_components).resolve()
    if candidate == root_resolved or root_resolved not in candidate.parents:
        raise UnsafePathError("Path escapes its storage root")
    return candidate
