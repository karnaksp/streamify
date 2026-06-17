#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
RAW_DIR = ROOT / os.getenv("STREAMIFY_RAW_DIR", "data/raw/yamusic")
DUCKDB_PATH = ROOT / os.getenv("STREAMIFY_DUCKDB_PATH", "data/streamify.duckdb")
REPORT_PATH = ROOT / os.getenv("STREAMIFY_REPORT_PATH", "data/streamify_summary.md")
SNAPSHOT_PATH = ROOT / os.getenv("STREAMIFY_SNAPSHOT_PATH", "data/streamify_snapshot.json")
RECOMMENDATIONS_DIR = ROOT / os.getenv("STREAMIFY_RECOMMENDATIONS_DIR", "data/recommendations")

REQUIRED_RAW_DATASETS = [
    "tracks",
    "artists",
    "albums",
    "playlists",
    "playlist_tracks",
    "user_library_events",
]
REQUIRED_MARTS = [
    "stg_yamusic_manifest",
    "yamusic_dim_tracks",
    "yamusic_dim_artists",
    "yamusic_dim_albums",
    "yamusic_dim_playlists",
    "yamusic_fact_library_events",
    "yamusic_fact_playlist_tracks",
    "yamusic_artist_affinity",
    "yamusic_library_profile",
    "yamusic_track_signals",
    "yamusic_period_activity",
    "yamusic_genre_profile",
    "yamusic_genre_periods",
    "yamusic_playlist_overlap",
    "yamusic_playlist_signals",
]
AUDIO_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".alac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}


def fail(message: str) -> None:
    raise AssertionError(message)


def read_manifest() -> dict[str, Any]:
    path = RAW_DIR / "_manifest.json"
    if not path.exists():
        fail(f"Missing ingestion manifest: {path}")
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if manifest.get("source") not in {"sample", "yandex_music"}:
        fail("Manifest source must be sample or yandex_music")
    if "token" in json.dumps(manifest).lower():
        fail("Manifest must not contain token material")
    return manifest


def count_jsonl(path: Path) -> int:
    rows = 0
    with path.open(encoding="utf-8") as file:
        for line in file:
            if line.strip():
                json.loads(line)
                rows += 1
    return rows


def audit_raw(manifest: dict[str, Any]) -> dict[str, int]:
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict):
        fail("Manifest datasets must be an object")
    counts: dict[str, int] = {}
    for dataset in REQUIRED_RAW_DATASETS:
        path = RAW_DIR / f"{dataset}.jsonl"
        if not path.exists():
            fail(f"Missing raw JSONL dataset: {path}")
        row_count = count_jsonl(path)
        manifest_count = datasets.get(dataset, {}).get("row_count")
        if manifest_count != row_count:
            fail(f"Manifest row count mismatch for {dataset}: manifest={manifest_count}, actual={row_count}")
        counts[dataset] = row_count
    return counts


def audit_duckdb(manifest: dict[str, Any], raw_counts: dict[str, int]) -> dict[str, Any]:
    if not DUCKDB_PATH.exists():
        fail(f"Missing local DuckDB database: {DUCKDB_PATH}")
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        missing = sorted(set(REQUIRED_MARTS) - tables)
        if missing:
            fail(f"Missing local mart tables: {', '.join(missing)}")
        profile = conn.execute("select * from yamusic_library_profile").fetchdf()
        if len(profile.index) != 1:
            fail(f"yamusic_library_profile must contain exactly one row, found {len(profile.index)}")
        row = profile.iloc[0]
        total_tracks = int(row["total_tracks"] or 0)
        stale_ingestion_flag = int(row["stale_ingestion_flag"] or 0)
        if stale_ingestion_flag not in {0, 1}:
            fail("stale_ingestion_flag must be 0 or 1")
        manifest_source = str(row["manifest_source"])
        if manifest_source != manifest["source"]:
            fail(f"DuckDB profile source {manifest_source!r} does not match manifest source {manifest['source']!r}; rerun make dbt-build")
        adapter = {
            "adapter_name": str(row["adapter_name"]),
            "adapter_version": str(row["adapter_version"]),
            "client_library": str(row["client_library"]),
            "client_library_version": None if row["client_library_version"] is None else str(row["client_library_version"]),
        }
        for field in ["adapter_name", "adapter_version", "client_library"]:
            if not adapter[field]:
                fail(f"DuckDB profile adapter metadata field {field} must not be empty")
        profile_raw_counts = {
            "tracks": int(row["raw_tracks"] or 0),
            "artists": int(row["raw_artists"] or 0),
            "albums": int(row["raw_albums"] or 0),
            "playlists": int(row["raw_playlists"] or 0),
            "playlist_tracks": int(row["raw_playlist_tracks"] or 0),
            "user_library_events": int(row["raw_user_library_events"] or 0),
        }
        if profile_raw_counts != raw_counts:
            fail(f"DuckDB profile raw counts {profile_raw_counts} do not match manifest raw counts {raw_counts}; rerun make dbt-build")
        profile_raw_checksums = {
            "tracks": str(row["raw_tracks_sha256"]),
            "artists": str(row["raw_artists_sha256"]),
            "albums": str(row["raw_albums_sha256"]),
            "playlists": str(row["raw_playlists_sha256"]),
            "playlist_tracks": str(row["raw_playlist_tracks_sha256"]),
            "user_library_events": str(row["raw_user_library_events_sha256"]),
        }
        manifest_checksums = {
            dataset: str(manifest["datasets"][dataset]["jsonl_sha256"])
            for dataset in REQUIRED_RAW_DATASETS
        }
        if profile_raw_checksums != manifest_checksums:
            fail("DuckDB profile raw checksums do not match manifest checksums; rerun make dbt-build")
        diagnostics = {
            "liked_shortcuts_seen": int(row["diagnostic_liked_shortcuts_seen"] or 0),
            "liked_tracks_written": int(row["diagnostic_liked_tracks_written"] or 0),
            "liked_shortcuts_fetch_failed": int(row["diagnostic_liked_shortcuts_fetch_failed"] or 0),
            "liked_shortcuts_missing_track_id": int(row["diagnostic_liked_shortcuts_missing_track_id"] or 0),
            "liked_tracks_duplicate_skipped": int(row["diagnostic_liked_tracks_duplicate_skipped"] or 0),
            "liked_albums_seen": int(row["diagnostic_liked_albums_seen"] or 0),
            "liked_albums_written": int(row["diagnostic_liked_albums_written"] or 0),
            "liked_albums_missing_id": int(row["diagnostic_liked_albums_missing_id"] or 0),
            "liked_albums_duplicate_skipped": int(row["diagnostic_liked_albums_duplicate_skipped"] or 0),
            "liked_artists_seen": int(row["diagnostic_liked_artists_seen"] or 0),
            "liked_artists_written": int(row["diagnostic_liked_artists_written"] or 0),
            "liked_artists_missing_id": int(row["diagnostic_liked_artists_missing_id"] or 0),
            "liked_artists_duplicate_skipped": int(row["diagnostic_liked_artists_duplicate_skipped"] or 0),
            "liked_playlists_seen": int(row["diagnostic_liked_playlists_seen"] or 0),
            "liked_playlists_written": int(row["diagnostic_liked_playlists_written"] or 0),
            "liked_playlists_missing_id": int(row["diagnostic_liked_playlists_missing_id"] or 0),
            "liked_playlists_duplicate_skipped": int(row["diagnostic_liked_playlists_duplicate_skipped"] or 0),
            "playlists_seen": int(row["diagnostic_playlists_seen"] or 0),
            "playlists_written": int(row["diagnostic_playlists_written"] or 0),
            "playlists_missing_id": int(row["diagnostic_playlists_missing_id"] or 0),
            "playlist_fetch_fallbacks": int(row["diagnostic_playlist_fetch_fallbacks"] or 0),
            "playlist_tracks_seen": int(row["diagnostic_playlist_tracks_seen"] or 0),
            "playlist_tracks_written": int(row["diagnostic_playlist_tracks_written"] or 0),
            "playlist_tracks_fetch_failed": int(row["diagnostic_playlist_tracks_fetch_failed"] or 0),
            "playlist_tracks_missing_track_id": int(row["diagnostic_playlist_tracks_missing_track_id"] or 0),
            "playlist_tracks_duplicate_skipped": int(row["diagnostic_playlist_tracks_duplicate_skipped"] or 0),
        }
        return {
            "manifest_source": manifest_source,
            "manifest_generated_at": str(row["manifest_generated_at"]),
            "adapter": adapter,
            "ingestion_diagnostics": diagnostics,
            "raw_counts_from_profile": profile_raw_counts,
            "raw_checksums_from_profile": profile_raw_checksums,
            "total_tracks": total_tracks,
            "liked_tracks": int(row["liked_tracks"] or 0),
            "artists": int(row["artists"] or 0),
            "playlists": int(row["playlists"] or 0),
            "known_genres": int(row["known_genres"] or 0),
            "stale_ingestion_flag": stale_ingestion_flag,
        }


def audit_report() -> None:
    if not REPORT_PATH.exists():
        fail(f"Missing markdown self-analytics report: {REPORT_PATH}")
    text = REPORT_PATH.read_text(encoding="utf-8")
    for marker in [
        "Streamify Yandex Music Self-Analytics Summary",
        "Executive Summary",
        "Recommended Next Steps",
        "Caveats And Assumptions",
    ]:
        if marker not in text:
            fail(f"Report must contain {marker!r}")
    token = os.getenv("YANDEX_MUSIC_TOKEN")
    if token and token in text:
        fail("Report must not contain the configured Yandex Music token value")


def audit_snapshot(manifest: dict[str, Any]) -> None:
    if not SNAPSHOT_PATH.exists():
        fail(f"Missing JSON self-analytics snapshot: {SNAPSHOT_PATH}")
    snapshot_text = SNAPSHOT_PATH.read_text(encoding="utf-8")
    snapshot = json.loads(snapshot_text)
    if snapshot.get("schema_version") != "1.0":
        fail("Snapshot schema_version must be 1.0")
    if snapshot.get("source") != manifest["source"]:
        fail(f"Snapshot source {snapshot.get('source')!r} does not match manifest source {manifest['source']!r}")
    if not isinstance(snapshot.get("answers"), dict):
        fail("Snapshot must contain an answers object")
    for key in ["favorite_artists", "favorite_tracks", "genre_shifts", "repeat_tracks", "playlist_overlap"]:
        if key not in snapshot["answers"]:
            fail(f"Snapshot answers must contain {key!r}")
    quality = snapshot.get("quality")
    if not isinstance(quality, dict):
        fail("Snapshot must contain a quality object")
    for key in ["raw_counts", "raw_checksums", "ingestion_diagnostics", "adapter"]:
        if key not in quality:
            fail(f"Snapshot quality must contain {key!r}")
    for dataset, value in quality["raw_checksums"].items():
        if not isinstance(value, str) or len(value) != 64:
            fail(f"Snapshot raw checksum for {dataset} must be a 64-character sha256 digest")
    token = os.getenv("YANDEX_MUSIC_TOKEN")
    if token and token in snapshot_text:
        fail("Snapshot must not contain the configured Yandex Music token value")


def audit_recommendations() -> None:
    expected_files = [
        "top_artists.csv",
        "rediscovery_tracks.csv",
        "playlist_cleanup.csv",
        "standout_playlists.csv",
        "genre_shifts.csv",
    ]
    if not RECOMMENDATIONS_DIR.exists():
        fail(f"Missing recommendations export directory: {RECOMMENDATIONS_DIR}")
    token = os.getenv("YANDEX_MUSIC_TOKEN")
    for file_name in expected_files:
        path = RECOMMENDATIONS_DIR / file_name
        if not path.exists():
            fail(f"Missing recommendations export: {path}")
        text = path.read_text(encoding="utf-8")
        if token and token in text:
            fail(f"Recommendation export {file_name} must not contain the configured Yandex Music token value")
        with path.open(encoding="utf-8", newline="") as file:
            rows = list(csv.reader(file))
        if not rows or not rows[0]:
            fail(f"Recommendation export {file_name} must contain a header row")


def audit_no_audio() -> None:
    data_dir = ROOT / "data"
    if not data_dir.exists():
        return
    audio_files = [path for path in data_dir.rglob("*") if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS]
    if audio_files:
        fail(f"Audio files must not be stored under data/: {audio_files[0]}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit local Yandex Music product readiness.")
    parser.add_argument(
        "--require-real",
        action="store_true",
        help="Fail unless the latest raw manifest was produced from real Yandex Music metadata.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    manifest = read_manifest()
    raw_counts = audit_raw(manifest)
    profile = audit_duckdb(manifest, raw_counts)
    audit_report()
    audit_snapshot(manifest)
    audit_recommendations()
    audit_no_audio()
    real_account_verified = manifest["source"] == "yandex_music"
    if args.require_real and not real_account_verified:
        fail("Real-account readiness requires _manifest.json source=yandex_music. Run make acceptance-real with a valid YANDEX_MUSIC_TOKEN.")

    summary = {
        "source": manifest["source"],
        "raw_dir": str(RAW_DIR),
        "duckdb_path": str(DUCKDB_PATH),
        "report_path": str(REPORT_PATH),
        "snapshot_path": str(SNAPSHOT_PATH),
        "recommendations_dir": str(RECOMMENDATIONS_DIR),
        "raw_counts": raw_counts,
        "profile": profile,
        "real_account_verified": real_account_verified,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    if manifest["source"] == "sample":
        print("OK: local product readiness is valid for sample metadata. Real-account acceptance still requires make acceptance-real.")
    else:
        print("OK: local product readiness is valid for Yandex Music metadata.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, json.JSONDecodeError, duckdb.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
