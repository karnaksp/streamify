#!/usr/bin/env python3
from __future__ import annotations

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

REQUIRED_DATASETS = [
    "tracks",
    "artists",
    "albums",
    "playlists",
    "playlist_tracks",
    "user_library_events",
]
REQUIRED_TABLES = [
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


def fail(message: str) -> None:
    raise AssertionError(message)


def read_manifest() -> dict[str, Any]:
    manifest_path = RAW_DIR / "_manifest.json"
    if not manifest_path.exists():
        fail(f"Missing ingestion manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("source") not in {"sample", "yandex_music"}:
        fail("_manifest.json must declare source as sample or yandex_music")
    if "token" in json.dumps(manifest).lower():
        fail("_manifest.json must not contain token material")
    return manifest


def check_raw_files(manifest: dict[str, Any]) -> dict[str, int]:
    datasets = manifest.get("datasets")
    if not isinstance(datasets, dict):
        fail("_manifest.json must contain datasets object")
    counts: dict[str, int] = {}
    for dataset in REQUIRED_DATASETS:
        jsonl_path = RAW_DIR / f"{dataset}.jsonl"
        if not jsonl_path.exists():
            fail(f"Missing raw dataset: {jsonl_path}")
        rows = 0
        with jsonl_path.open(encoding="utf-8") as file:
            for line_number, line in enumerate(file, start=1):
                if not line.strip():
                    continue
                json.loads(line)
                rows += 1
        manifest_count = datasets.get(dataset, {}).get("row_count")
        if manifest_count != rows:
            fail(f"Manifest row count mismatch for {dataset}: manifest={manifest_count}, actual={rows}")
        counts[dataset] = rows
    return counts


def scalar(conn: duckdb.DuckDBPyConnection, sql: str) -> Any:
    return conn.execute(sql).fetchone()[0]


def check_duckdb(manifest: dict[str, Any], raw_counts: dict[str, int]) -> None:
    if not DUCKDB_PATH.exists():
        fail(f"Missing local DuckDB database: {DUCKDB_PATH}")
    with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "select table_name from information_schema.tables where table_schema = 'main'"
            ).fetchall()
        }
        missing = sorted(set(REQUIRED_TABLES) - tables)
        if missing:
            fail(f"Missing local mart tables: {', '.join(missing)}")

        profile_rows = scalar(conn, "select count(*) from yamusic_library_profile")
        if profile_rows != 1:
            fail(f"yamusic_library_profile must contain exactly one row, found {profile_rows}")

        profile = conn.execute(
            """
            select
                total_tracks,
                manifest_source,
                adapter_name,
                adapter_version,
                client_library,
                raw_tracks,
                raw_artists,
                raw_albums,
                raw_playlists,
                raw_playlist_tracks,
                raw_user_library_events,
                playlists,
                stale_ingestion_flag,
                underrated_tracks,
                underrated_playlists,
                active_months
            from yamusic_library_profile
            """
        ).fetchone()
        (
            total_tracks,
            manifest_source,
            adapter_name,
            adapter_version,
            client_library,
            raw_tracks,
            raw_artists,
            raw_albums,
            raw_playlists,
            raw_playlist_tracks,
            raw_user_library_events,
            playlists,
            stale_ingestion_flag,
            _,
            _,
            active_months,
        ) = profile
        if manifest_source != manifest["source"]:
            fail(f"DuckDB profile source {manifest_source!r} does not match manifest source {manifest['source']!r}; rerun make dbt-build")
        for field_name, field_value in {
            "adapter_name": adapter_name,
            "adapter_version": adapter_version,
            "client_library": client_library,
        }.items():
            if not field_value:
                fail(f"DuckDB profile adapter metadata field {field_name} must not be empty")
        profile_raw_counts = {
            "tracks": int(raw_tracks or 0),
            "artists": int(raw_artists or 0),
            "albums": int(raw_albums or 0),
            "playlists": int(raw_playlists or 0),
            "playlist_tracks": int(raw_playlist_tracks or 0),
            "user_library_events": int(raw_user_library_events or 0),
        }
        if profile_raw_counts != raw_counts:
            fail(f"DuckDB profile raw counts {profile_raw_counts} do not match manifest raw counts {raw_counts}; rerun make dbt-build")
        if stale_ingestion_flag not in {0, 1}:
            fail("stale_ingestion_flag must be 0 or 1")
        if total_tracks > 0:
            if scalar(conn, "select count(*) from yamusic_track_signals") == 0:
                fail("yamusic_track_signals must be non-empty when tracks exist")
            if active_months > 0 and scalar(conn, "select count(*) from yamusic_period_activity") == 0:
                fail("yamusic_period_activity must be non-empty when activity months exist")
            if active_months > 0 and scalar(conn, "select count(*) from yamusic_genre_periods") == 0:
                fail("yamusic_genre_periods must be non-empty when activity months exist")
        if playlists > 0 and scalar(conn, "select count(*) from yamusic_playlist_signals") == 0:
            fail("yamusic_playlist_signals must be non-empty when playlists exist")


def main() -> int:
    manifest = read_manifest()
    raw_counts = check_raw_files(manifest)
    check_duckdb(manifest, raw_counts)
    print("OK: local Yandex Music acceptance checks passed.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (AssertionError, json.JSONDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
