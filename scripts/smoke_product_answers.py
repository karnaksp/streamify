#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
import json
import csv
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
DUCKDB_PATH = ROOT / os.getenv("STREAMIFY_DUCKDB_PATH", "data/streamify.duckdb")
REPORT_PATH = ROOT / os.getenv("STREAMIFY_REPORT_PATH", "data/streamify_summary.md")
SNAPSHOT_PATH = ROOT / os.getenv("STREAMIFY_SNAPSHOT_PATH", "data/streamify_snapshot.json")
RECOMMENDATIONS_DIR = ROOT / os.getenv("STREAMIFY_RECOMMENDATIONS_DIR", "data/recommendations")


def fail(message: str) -> None:
    raise AssertionError(message)


def scalar(conn: duckdb.DuckDBPyConnection, sql: str) -> Any:
    return conn.execute(sql).fetchone()[0]


def require_count(conn: duckdb.DuckDBPyConnection, label: str, sql: str) -> None:
    count = int(scalar(conn, sql) or 0)
    if count <= 0:
        fail(f"Missing product answer coverage for {label}")


def check_duckdb_answers() -> None:
    if not DUCKDB_PATH.exists():
        fail(f"Missing local DuckDB database: {DUCKDB_PATH}")
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
        total_tracks = int(scalar(conn, "select total_tracks from yamusic_library_profile") or 0)
        if total_tracks <= 0:
            fail("Product-answer smoke requires non-empty sample or account metadata")

        require_count(conn, "favorite artists", "select count(*) from yamusic_artist_affinity where track_count > 0")
        require_count(conn, "favorite tracks", "select count(*) from yamusic_dim_tracks where title is not null")
        require_count(conn, "repeat signals", "select count(*) from yamusic_track_signals where repeat_signal > 1")
        require_count(conn, "genre shifts", "select count(*) from yamusic_genre_periods where event_share_in_month > 0")
        require_count(conn, "diversity profile", "select count(*) from yamusic_genre_profile where track_share > 0")
        require_count(conn, "active periods", "select count(*) from yamusic_period_activity where event_count > 0")
        require_count(conn, "playlist overlap", "select count(*) from yamusic_playlist_overlap where overlap_track_count > 0")
        require_count(conn, "playlist signals", "select count(*) from yamusic_playlist_signals where actual_track_count > 0")
        require_count(conn, "underrated tracks", "select count(*) from yamusic_track_signals where underrated_flag in (0, 1)")

        quality = conn.execute(
            """
            select
                manifest_source,
                adapter_name,
                adapter_version,
                client_library,
                diagnostic_liked_shortcuts_seen,
                diagnostic_liked_tracks_written,
                diagnostic_playlist_tracks_seen,
                diagnostic_playlist_tracks_written,
                raw_tracks,
                stale_ingestion_flag,
                top_artist_concentration,
                known_genres,
                max_repeat_signal
            from yamusic_library_profile
            """
        ).fetchone()
        (
            manifest_source,
            adapter_name,
            adapter_version,
            client_library,
            diagnostic_liked_shortcuts_seen,
            diagnostic_liked_tracks_written,
            diagnostic_playlist_tracks_seen,
            diagnostic_playlist_tracks_written,
            raw_tracks,
            stale_ingestion_flag,
            top_artist_concentration,
            known_genres,
            max_repeat_signal,
        ) = quality
        if manifest_source not in {"sample", "yandex_music"}:
            fail("Data provenance answer must expose manifest_source as sample or yandex_music")
        if not adapter_name or not adapter_version or not client_library:
            fail("Data provenance answer must expose ingestion adapter and client library metadata")
        for value in [
            diagnostic_liked_shortcuts_seen,
            diagnostic_liked_tracks_written,
            diagnostic_playlist_tracks_seen,
            diagnostic_playlist_tracks_written,
        ]:
            if value is None or int(value) < 0:
                fail("Data quality answer must expose non-negative ingestion diagnostics")
        if int(raw_tracks or 0) != total_tracks:
            fail("Data provenance answer must expose raw_tracks aligned to the current profile")
        if stale_ingestion_flag not in {0, 1}:
            fail("Data quality answer must expose a boolean stale_ingestion_flag")
        if top_artist_concentration is None or not (0 <= float(top_artist_concentration) <= 1):
            fail("Diversity answer must expose top_artist_concentration in [0, 1]")
        if int(known_genres or 0) <= 0:
            fail("Diversity answer must expose at least one known genre for sample data")
        if int(max_repeat_signal or 0) <= 0:
            fail("Repeat answer must expose max_repeat_signal")


def check_report_answers() -> None:
    if not REPORT_PATH.exists():
        fail(f"Missing static self-analytics report: {REPORT_PATH}")
    text = REPORT_PATH.read_text(encoding="utf-8")
    for marker in [
        "Artist Affinity Is The Main Taste Signal",
        "Genre Shifts Depend On Metadata Coverage",
        "Repeats And Underrated Tracks Show Actionable Library Work",
        "Playlist Overlap Highlights Where Curation Can Improve",
        "Raw Ingestion Counts",
        "Raw File Checksums",
        "Stale",
    ]:
        if marker not in text:
            fail(f"Static report must contain product answer section {marker!r}")


def check_snapshot_answers() -> None:
    if not SNAPSHOT_PATH.exists():
        fail(f"Missing JSON self-analytics snapshot: {SNAPSHOT_PATH}")
    snapshot = json.loads(SNAPSHOT_PATH.read_text(encoding="utf-8"))
    if snapshot.get("schema_version") != "1.0":
        fail("JSON snapshot must expose schema_version=1.0")
    if snapshot.get("product") != "Streamify Yandex Music Self-Analytics":
        fail("JSON snapshot must expose the product name")
    if snapshot.get("source") not in {"sample", "yandex_music"}:
        fail("JSON snapshot must expose source as sample or yandex_music")
    if not isinstance(snapshot.get("profile"), dict):
        fail("JSON snapshot must expose a profile object")
    quality = snapshot.get("quality")
    if not isinstance(quality, dict):
        fail("JSON snapshot must expose a quality object")
    for key in ["adapter", "raw_counts", "raw_checksums", "ingestion_diagnostics"]:
        if key not in quality:
            fail(f"JSON snapshot quality must expose {key}")
    for key, value in quality["raw_checksums"].items():
        if not isinstance(value, str) or len(value) != 64:
            fail(f"JSON snapshot raw checksum {key} must be a 64-character sha256 digest")
    answers = snapshot.get("answers")
    if not isinstance(answers, dict):
        fail("JSON snapshot must expose an answers object")
    for key in [
        "favorite_artists",
        "favorite_tracks",
        "genre_profile",
        "genre_shifts",
        "active_periods",
        "repeat_tracks",
        "underrated_tracks",
        "playlist_overlap",
        "underrated_playlists",
    ]:
        if key not in answers:
            fail(f"JSON snapshot answers must expose {key}")
        if not isinstance(answers[key], list):
            fail(f"JSON snapshot answer {key} must be a list")
    if not answers["favorite_artists"] or not answers["favorite_tracks"]:
        fail("JSON snapshot must include favorite artist and track rows for sample/account metadata")
    diagnostics = quality["ingestion_diagnostics"]
    for key in [
        "liked_shortcuts_seen",
        "liked_tracks_duplicate_skipped",
        "liked_albums_seen",
        "liked_albums_written",
        "liked_artists_seen",
        "liked_artists_written",
        "liked_playlists_seen",
        "liked_playlists_written",
        "playlist_tracks_seen",
        "playlist_tracks_fetch_failed",
        "playlist_tracks_duplicate_skipped",
    ]:
        value = diagnostics.get(key)
        if value is None or int(value) < 0:
            fail(f"JSON snapshot diagnostics must expose non-negative {key}")


def check_recommendation_exports() -> None:
    expected_files = {
        "top_artists.csv",
        "rediscovery_tracks.csv",
        "playlist_cleanup.csv",
        "standout_playlists.csv",
        "genre_shifts.csv",
    }
    if not RECOMMENDATIONS_DIR.exists():
        fail(f"Missing recommendations export directory: {RECOMMENDATIONS_DIR}")
    for file_name in sorted(expected_files):
        path = RECOMMENDATIONS_DIR / file_name
        if not path.exists():
            fail(f"Missing recommendation export: {path}")
        with path.open(encoding="utf-8", newline="") as file:
            rows = list(csv.reader(file))
        if not rows or not rows[0]:
            fail(f"Recommendation export {file_name} must contain a header row")
        if file_name in {"top_artists.csv", "rediscovery_tracks.csv", "playlist_cleanup.csv", "genre_shifts.csv"} and len(rows) <= 1:
            fail(f"Recommendation export {file_name} must contain sample/account rows")


def main() -> int:
    check_duckdb_answers()
    check_report_answers()
    check_snapshot_answers()
    check_recommendation_exports()
    print("OK: practical self-analytics product answers and Data Quality signals are available.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, duckdb.Error) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
