#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from hashlib import sha256
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
RAW_DIR = ROOT / os.getenv("STREAMIFY_RAW_DIR", "data/raw/yamusic")
SOURCES = {"sample", "yandex_music"}
EVENT_TYPES = {"liked_track", "playlist_membership"}
DIAGNOSTIC_FIELDS = [
    "liked_shortcuts_seen",
    "liked_tracks_written",
    "liked_shortcuts_fetch_failed",
    "liked_shortcuts_missing_track_id",
    "liked_tracks_duplicate_skipped",
    "liked_albums_seen",
    "liked_albums_written",
    "liked_albums_missing_id",
    "liked_albums_duplicate_skipped",
    "liked_artists_seen",
    "liked_artists_written",
    "liked_artists_missing_id",
    "liked_artists_duplicate_skipped",
    "liked_playlists_seen",
    "liked_playlists_written",
    "liked_playlists_missing_id",
    "liked_playlists_duplicate_skipped",
    "playlists_seen",
    "playlists_written",
    "playlists_missing_id",
    "playlist_fetch_fallbacks",
    "playlist_tracks_seen",
    "playlist_tracks_written",
    "playlist_tracks_fetch_failed",
    "playlist_tracks_missing_track_id",
    "playlist_tracks_duplicate_skipped",
]

SCHEMAS: dict[str, dict[str, tuple[type, ...]]] = {
    "tracks": {
        "track_id": (str,),
        "title": (str,),
        "artist_ids": (list,),
        "artist_names": (list,),
        "liked": (bool,),
        "source": (str,),
        "ingested_at": (str,),
    },
    "artists": {
        "artist_id": (str,),
        "artist_name": (str,),
        "source": (str,),
        "ingested_at": (str,),
    },
    "albums": {
        "album_id": (str,),
        "source": (str,),
        "ingested_at": (str,),
    },
    "playlists": {
        "playlist_id": (str,),
        "playlist_title": (str,),
        "source": (str,),
        "ingested_at": (str,),
    },
    "playlist_tracks": {
        "playlist_id": (str,),
        "track_id": (str,),
        "position": (int,),
        "source": (str,),
        "ingested_at": (str,),
    },
    "user_library_events": {
        "event_id": (str,),
        "event_type": (str,),
        "track_id": (str,),
        "event_ts": (str,),
        "source": (str,),
        "ingested_at": (str,),
    },
}


def fail(message: str) -> None:
    raise AssertionError(message)


def rows_for(dataset: str) -> list[dict[str, Any]]:
    path = RAW_DIR / f"{dataset}.jsonl"
    if not path.exists():
        fail(f"Missing raw dataset: {path}")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                fail(f"{dataset}.jsonl:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_row(dataset: str, row: dict[str, Any], row_number: int) -> None:
    for field, expected_types in SCHEMAS[dataset].items():
        if field not in row:
            fail(f"{dataset}.jsonl:{row_number} missing required field {field!r}")
        value = row[field]
        if value is None:
            fail(f"{dataset}.jsonl:{row_number} required field {field!r} must not be null")
        if not isinstance(value, expected_types):
            type_names = ", ".join(expected_type.__name__ for expected_type in expected_types)
            fail(f"{dataset}.jsonl:{row_number} field {field!r} must be {type_names}, got {type(value).__name__}")

    if row.get("source") not in SOURCES:
        fail(f"{dataset}.jsonl:{row_number} source must be one of {sorted(SOURCES)}")
    if dataset == "user_library_events" and row.get("event_type") not in EVENT_TYPES:
        fail(f"{dataset}.jsonl:{row_number} event_type must be one of {sorted(EVENT_TYPES)}")


def require_non_empty_id(dataset: str, row: dict[str, Any], row_number: int, field: str) -> None:
    value = row.get(field)
    if isinstance(value, str) and not value.strip():
        fail(f"{dataset}.jsonl:{row_number} field {field!r} must not be empty")


def require_unique(rows: list[dict[str, Any]], dataset: str, fields: tuple[str, ...]) -> None:
    seen: dict[tuple[Any, ...], int] = {}
    for row_number, row in enumerate(rows, start=1):
        key = tuple(row.get(field) for field in fields)
        if key in seen:
            field_label = ", ".join(fields)
            fail(f"{dataset}.jsonl:{row_number} duplicate {field_label} {key!r}; first seen at row {seen[key]}")
        seen[key] = row_number


def validate_integrity(rows_by_dataset: dict[str, list[dict[str, Any]]]) -> None:
    for dataset, fields in {
        "tracks": ("track_id",),
        "artists": ("artist_id",),
        "albums": ("album_id",),
        "playlists": ("playlist_id",),
        "user_library_events": ("event_id",),
    }.items():
        for row_number, row in enumerate(rows_by_dataset[dataset], start=1):
            require_non_empty_id(dataset, row, row_number, fields[0])
        require_unique(rows_by_dataset[dataset], dataset, fields)

    track_ids = {row["track_id"] for row in rows_by_dataset["tracks"]}
    playlist_ids = {row["playlist_id"] for row in rows_by_dataset["playlists"]}

    playlist_tracks = rows_by_dataset["playlist_tracks"]
    require_unique(playlist_tracks, "playlist_tracks", ("playlist_id", "track_id"))
    require_unique(playlist_tracks, "playlist_tracks", ("playlist_id", "position"))
    for row_number, row in enumerate(playlist_tracks, start=1):
        require_non_empty_id("playlist_tracks", row, row_number, "playlist_id")
        require_non_empty_id("playlist_tracks", row, row_number, "track_id")
        if row["playlist_id"] not in playlist_ids:
            fail(f"playlist_tracks.jsonl:{row_number} playlist_id {row['playlist_id']!r} is not present in playlists.jsonl")
        if row["track_id"] not in track_ids:
            fail(f"playlist_tracks.jsonl:{row_number} track_id {row['track_id']!r} is not present in tracks.jsonl")

    for row_number, row in enumerate(rows_by_dataset["user_library_events"], start=1):
        require_non_empty_id("user_library_events", row, row_number, "event_id")
        require_non_empty_id("user_library_events", row, row_number, "track_id")
        if row["track_id"] not in track_ids:
            fail(f"user_library_events.jsonl:{row_number} track_id {row['track_id']!r} is not present in tracks.jsonl")
        if row["event_type"] == "playlist_membership":
            playlist_id = row.get("playlist_id")
            if not isinstance(playlist_id, str) or not playlist_id.strip():
                fail(f"user_library_events.jsonl:{row_number} playlist_membership event must include playlist_id")
            if playlist_id not in playlist_ids:
                fail(f"user_library_events.jsonl:{row_number} playlist_id {playlist_id!r} is not present in playlists.jsonl")


def validate_diagnostic_consistency(
    diagnostics: dict[str, int],
    row_counts: dict[str, int],
    rows_by_dataset: dict[str, list[dict[str, Any]]],
) -> None:
    liked_track_rows = sum(1 for row in rows_by_dataset["tracks"] if row.get("liked") is True)
    liked_event_rows = sum(1 for row in rows_by_dataset["user_library_events"] if row.get("event_type") == "liked_track")
    playlist_event_rows = sum(1 for row in rows_by_dataset["user_library_events"] if row.get("event_type") == "playlist_membership")

    expected_equalities = {
        "liked_tracks_written": liked_track_rows,
        "playlist_tracks_written": row_counts["playlist_tracks"],
    }
    for field, expected in expected_equalities.items():
        if diagnostics[field] != expected:
            fail(f"_manifest.json diagnostics.{field}={diagnostics[field]} must match written row count {expected}")

    if liked_event_rows > diagnostics["liked_tracks_written"]:
        fail("_manifest.json liked_track event rows cannot exceed diagnostics.liked_tracks_written")
    if playlist_event_rows > diagnostics["playlist_tracks_written"]:
        fail("_manifest.json playlist_membership event rows cannot exceed diagnostics.playlist_tracks_written")
    if diagnostics["liked_shortcuts_seen"] != (
        diagnostics["liked_tracks_written"]
        + diagnostics["liked_shortcuts_missing_track_id"]
        + diagnostics["liked_tracks_duplicate_skipped"]
    ):
        fail("_manifest.json liked shortcut diagnostics must add up to liked_shortcuts_seen")
    if diagnostics["liked_albums_seen"] != (
        diagnostics["liked_albums_written"]
        + diagnostics["liked_albums_missing_id"]
        + diagnostics["liked_albums_duplicate_skipped"]
    ):
        fail("_manifest.json liked album diagnostics must add up to liked_albums_seen")
    if diagnostics["liked_artists_seen"] != (
        diagnostics["liked_artists_written"]
        + diagnostics["liked_artists_missing_id"]
        + diagnostics["liked_artists_duplicate_skipped"]
    ):
        fail("_manifest.json liked artist diagnostics must add up to liked_artists_seen")
    if diagnostics["liked_playlists_seen"] != (
        diagnostics["liked_playlists_written"]
        + diagnostics["liked_playlists_missing_id"]
        + diagnostics["liked_playlists_duplicate_skipped"]
    ):
        fail("_manifest.json liked playlist diagnostics must add up to liked_playlists_seen")
    if diagnostics["playlists_seen"] != diagnostics["playlists_written"] + diagnostics["playlists_missing_id"]:
        fail("_manifest.json playlist diagnostics must add up to playlists_seen")
    if row_counts["playlists"] != diagnostics["playlists_written"] + diagnostics["liked_playlists_written"]:
        fail("_manifest.json playlist rows must match playlists_written + liked_playlists_written")
    if diagnostics["playlist_tracks_seen"] != (
        diagnostics["playlist_tracks_written"]
        + diagnostics["playlist_tracks_missing_track_id"]
        + diagnostics["playlist_tracks_duplicate_skipped"]
    ):
        fail("_manifest.json playlist-track diagnostics must add up to playlist_tracks_seen")
    if row_counts["tracks"] > diagnostics["liked_tracks_written"] + diagnostics["playlist_tracks_written"]:
        fail("_manifest.json track rows cannot exceed liked_tracks_written + playlist_tracks_written")


def validate_manifest(row_counts: dict[str, int], rows_by_dataset: dict[str, list[dict[str, Any]]]) -> None:
    manifest_path = RAW_DIR / "_manifest.json"
    if not manifest_path.exists():
        fail(f"Missing raw manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if "token" in json.dumps(manifest).lower():
        fail("_manifest.json must not contain token material")
    if manifest.get("source") not in SOURCES:
        fail(f"_manifest.json source must be one of {sorted(SOURCES)}")
    if not isinstance(manifest.get("generated_at"), str) or not manifest["generated_at"].strip():
        fail("_manifest.json must contain generated_at")
    adapter = manifest.get("adapter")
    if not isinstance(adapter, dict):
        fail("_manifest.json must contain adapter object")
    for field in ["adapter_name", "adapter_version", "client_library"]:
        if not isinstance(adapter.get(field), str) or not adapter[field].strip():
            fail(f"_manifest.json adapter.{field} must be a non-empty string")
    diagnostics = manifest.get("diagnostics")
    if not isinstance(diagnostics, dict):
        fail("_manifest.json must contain diagnostics object")
    for field in DIAGNOSTIC_FIELDS:
        value = diagnostics.get(field)
        if not isinstance(value, int) or value < 0:
            fail(f"_manifest.json diagnostics.{field} must be a non-negative integer")
    validate_diagnostic_consistency(diagnostics, row_counts, rows_by_dataset)
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict):
        fail("_manifest.json must contain datasets object")
    for dataset, actual_count in row_counts.items():
        dataset_manifest = datasets.get(dataset, {})
        expected_count = dataset_manifest.get("row_count")
        if expected_count != actual_count:
            fail(f"_manifest.json row_count mismatch for {dataset}: manifest={expected_count}, actual={actual_count}")
        expected_sha256 = dataset_manifest.get("jsonl_sha256")
        if not isinstance(expected_sha256, str) or len(expected_sha256) != 64:
            fail(f"_manifest.json datasets.{dataset}.jsonl_sha256 must be a 64-character sha256 hex digest")
        actual_sha256 = file_sha256(RAW_DIR / f"{dataset}.jsonl")
        if expected_sha256 != actual_sha256:
            fail(f"_manifest.json sha256 mismatch for {dataset}: manifest={expected_sha256}, actual={actual_sha256}")


def main() -> int:
    row_counts: dict[str, int] = {}
    rows_by_dataset: dict[str, list[dict[str, Any]]] = {}
    for dataset in SCHEMAS:
        rows = rows_for(dataset)
        rows_by_dataset[dataset] = rows
        row_counts[dataset] = len(rows)
        for index, row in enumerate(rows, start=1):
            validate_row(dataset, row, index)
    validate_integrity(rows_by_dataset)
    validate_manifest(row_counts, rows_by_dataset)
    print("OK: Yandex Music raw schema contract is valid.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
