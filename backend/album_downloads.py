"""Archive-name helpers for album downloads.

The live gallery filename must remain unchanged because it is referenced by the
database, thumbnails and previews.  These helpers only alter the name presented
inside a generated ZIP archive.
"""

ALBUM_FAVOURITES_FOLDER = "Album Favourites"
COVER_PREFIX = "COVER - "


def album_download_name(file_doc: dict, album_cover_choice: dict | None) -> str:
    """Return the ZIP entry filename, marking only the chosen album cover."""
    filename = file_doc["filename"]
    if not album_cover_choice:
        return filename
    if file_doc.get("subfolder") != ALBUM_FAVOURITES_FOLDER:
        return filename
    if file_doc.get("id") != album_cover_choice.get("file_id"):
        return filename
    if filename.casefold().startswith(COVER_PREFIX.casefold()):
        return filename
    return f"{COVER_PREFIX}{filename}"
