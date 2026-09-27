"""Verified MongoDB metadata snapshots for the couples gallery.

Each in-app backup writes an atomic BSON snapshot to the mounted backup
dataset, restores it into a uniquely named temporary MongoDB database, checks
document fingerprints and indexes, and then removes the temporary database.
The live database is never written to by the verification step.
"""

from __future__ import annotations

import hashlib
import json
import logging
import struct
import uuid
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import BinaryIO, Dict, Iterable, Iterator, List, Tuple
from urllib.parse import quote

from bson import BSON, json_util
from pymongo import MongoClient


logger = logging.getLogger(__name__)
SNAPSHOT_FORMAT = 1
MAX_BSON_DOCUMENT_BYTES = 16 * 1024 * 1024 + 1024


class DatabaseBackupError(RuntimeError):
    """Raised when a database snapshot cannot be created or verified."""


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _collection_member(collection_name: str) -> str:
    return f"collections/{quote(collection_name, safe='')}.bson"


def _iter_bson_stream(stream: BinaryIO) -> Iterator[Tuple[dict, bytes]]:
    """Read concatenated BSON documents without loading a collection at once."""
    while True:
        length_bytes = stream.read(4)
        if not length_bytes:
            return
        if len(length_bytes) != 4:
            raise DatabaseBackupError("Snapshot contains a truncated BSON document")
        length = struct.unpack("<i", length_bytes)[0]
        if length < 5 or length > MAX_BSON_DOCUMENT_BYTES:
            raise DatabaseBackupError("Snapshot contains an invalid BSON document length")
        remainder = stream.read(length - 4)
        if len(remainder) != length - 4:
            raise DatabaseBackupError("Snapshot contains a truncated BSON document")
        raw = length_bytes + remainder
        yield BSON(raw).decode(), raw


def inspect_snapshot_archive(snapshot_path: Path) -> Dict:
    """Verify archive members, counts and checksums without touching MongoDB."""
    try:
        with zipfile.ZipFile(snapshot_path, "r") as archive:
            manifest = json_util.loads(archive.read("manifest.json").decode("utf-8"))
            if manifest.get("format") != SNAPSHOT_FORMAT:
                raise DatabaseBackupError("Unsupported database snapshot format")

            total_documents = 0
            for collection in manifest.get("collections", []):
                checksum = hashlib.sha256()
                count = 0
                with archive.open(collection["member"], "r") as stream:
                    for _, raw in _iter_bson_stream(stream):
                        checksum.update(raw)
                        count += 1
                if count != collection.get("documents"):
                    raise DatabaseBackupError(
                        f"Snapshot count mismatch for collection {collection.get('name', 'unknown')}"
                    )
                if checksum.hexdigest() != collection.get("sha256"):
                    raise DatabaseBackupError(
                        f"Snapshot checksum mismatch for collection {collection.get('name', 'unknown')}"
                    )
                total_documents += count

            if total_documents != manifest.get("documents_total"):
                raise DatabaseBackupError("Snapshot total document count does not match its manifest")
            return manifest
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as exc:
        if isinstance(exc, DatabaseBackupError):
            raise
        raise DatabaseBackupError("Database snapshot archive is unreadable") from exc


class DatabaseBackupService:
    """Create and restore-verify bounded-retention MongoDB snapshots."""

    def __init__(
        self,
        mongo_url: str,
        database_name: str,
        backup_root: Path,
        *,
        keep_snapshots: int = 14,
    ):
        self.mongo_url = mongo_url
        self.database_name = database_name
        self.backup_root = Path(backup_root)
        self.keep_snapshots = max(2, int(keep_snapshots))

    def _client(self) -> MongoClient:
        return MongoClient(
            self.mongo_url,
            serverSelectionTimeoutMS=10_000,
            connectTimeoutMS=10_000,
            socketTimeoutMS=120_000,
        )

    def _write_snapshot(self, client: MongoClient, destination: Path) -> Dict:
        source = client[self.database_name]
        collections = sorted(
            name for name in source.list_collection_names()
            if not name.startswith("system.")
        )
        manifest = {
            "format": SNAPSHOT_FORMAT,
            "database": self.database_name,
            "created_at": _utc_now_iso(),
            "collections": [],
            "documents_total": 0,
        }

        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_suffix(destination.suffix + ".tmp")
        temporary.unlink(missing_ok=True)
        try:
            with zipfile.ZipFile(
                temporary,
                "w",
                compression=zipfile.ZIP_DEFLATED,
                compresslevel=6,
                allowZip64=True,
            ) as archive:
                for name in collections:
                    collection = source[name]
                    checksum = hashlib.sha256()
                    documents = 0
                    member = _collection_member(name)
                    with archive.open(member, "w", force_zip64=True) as target:
                        for document in collection.find({}).sort("_id", 1):
                            raw = BSON.encode(document)
                            target.write(raw)
                            checksum.update(raw)
                            documents += 1

                    index_information = collection.index_information()
                    manifest["collections"].append({
                        "name": name,
                        "member": member,
                        "documents": documents,
                        "sha256": checksum.hexdigest(),
                        "indexes": index_information,
                    })
                    manifest["documents_total"] += documents

                archive.writestr(
                    "manifest.json",
                    json_util.dumps(manifest, json_options=json_util.CANONICAL_JSON_OPTIONS),
                )
            temporary.replace(destination)
            return manifest
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

    @staticmethod
    def _restore_indexes(collection, indexes: Dict) -> None:
        for index_name, information in indexes.items():
            if index_name == "_id_":
                continue
            keys = [tuple(item) for item in information.get("key", [])]
            if not keys:
                continue
            options = {
                key: value
                for key, value in information.items()
                if key not in {"key", "v", "ns"}
            }
            options["name"] = index_name
            collection.create_index(keys, **options)

    def _restore_and_verify(self, client: MongoClient, snapshot_path: Path, manifest: Dict) -> Dict:
        verification_name = f"{self.database_name}_restore_verify_{uuid.uuid4().hex}"
        restored = client[verification_name]
        try:
            with zipfile.ZipFile(snapshot_path, "r") as archive:
                for expected in manifest["collections"]:
                    name = expected["name"]
                    if name not in restored.list_collection_names():
                        restored.create_collection(name)
                    collection = restored[name]
                    batch: List[dict] = []
                    with archive.open(expected["member"], "r") as stream:
                        for document, _ in _iter_bson_stream(stream):
                            batch.append(document)
                            if len(batch) >= 500:
                                collection.insert_many(batch, ordered=True)
                                batch = []
                    if batch:
                        collection.insert_many(batch, ordered=True)
                    self._restore_indexes(collection, expected.get("indexes", {}))

            restored_names = set(restored.list_collection_names())
            expected_names = {item["name"] for item in manifest["collections"]}
            if restored_names != expected_names:
                raise DatabaseBackupError("Restored collection list does not match the snapshot")

            verified_documents = 0
            for expected in manifest["collections"]:
                collection = restored[expected["name"]]
                checksum = hashlib.sha256()
                count = 0
                for document in collection.find({}).sort("_id", 1):
                    checksum.update(BSON.encode(document))
                    count += 1
                if count != expected["documents"] or checksum.hexdigest() != expected["sha256"]:
                    raise DatabaseBackupError(
                        f"Restored data did not match collection {expected['name']}"
                    )
                expected_indexes = set(expected.get("indexes", {}))
                actual_indexes = set(collection.index_information())
                if not expected_indexes.issubset(actual_indexes):
                    raise DatabaseBackupError(
                        f"Restored indexes did not match collection {expected['name']}"
                    )
                verified_documents += count

            return {
                "collections": len(expected_names),
                "documents": verified_documents,
                "verified_at": _utc_now_iso(),
            }
        finally:
            client.drop_database(verification_name)

    def _apply_retention(self) -> None:
        snapshots = sorted(
            self.backup_root.glob("gallery-database-*.zip"),
            key=lambda path: path.stat().st_mtime,
            reverse=True,
        )
        for old_snapshot in snapshots[self.keep_snapshots:]:
            try:
                old_snapshot.unlink()
            except OSError:
                logger.warning("Could not remove old database snapshot %s", old_snapshot.name)

    def run(self) -> Dict:
        """Create one snapshot, perform a real temporary restore, then retain it."""
        timestamp = _utc_now().strftime("%Y%m%d-%H%M%SZ")
        snapshot_path = self.backup_root / f"gallery-database-{timestamp}.zip"
        client = self._client()
        try:
            client.admin.command("ping")
            manifest = self._write_snapshot(client, snapshot_path)
            inspected = inspect_snapshot_archive(snapshot_path)
            if inspected["documents_total"] != manifest["documents_total"]:
                raise DatabaseBackupError("Snapshot inspection did not match its manifest")
            verification = self._restore_and_verify(client, snapshot_path, manifest)
            self._apply_retention()
            return {
                "status": "verified",
                "snapshot_name": snapshot_path.name,
                "created_at": manifest["created_at"],
                "verified_at": verification["verified_at"],
                "collections": verification["collections"],
                "documents": verification["documents"],
                "bytes": snapshot_path.stat().st_size,
            }
        except Exception:
            snapshot_path.unlink(missing_ok=True)
            raise
        finally:
            client.close()
