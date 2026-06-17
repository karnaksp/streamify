#!/usr/bin/env python3
from __future__ import annotations

import csv
import os
import sys
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
DEFAULT_DUCKDB_PATH = ROOT / "data" / "streamify.duckdb"
DEFAULT_EXPORT_DIR = ROOT / "data" / "recommendations"


EXPORT_QUERIES: dict[str, str] = {
    "top_artists.csv": """
        select artist_name, track_count, liked_track_count, playlist_appearances,
               avg_playlist_appearances_per_track
        from yamusic_artist_affinity
        order by track_count desc, liked_track_count desc, playlist_appearances desc, artist_name
        limit 100
    """,
    "rediscovery_tracks.csv": """
        select title, artist_display, album_title, genre, playlist_slots, playlist_count,
               event_count, repeat_signal
        from yamusic_track_signals
        where underrated_flag = true
        order by playlist_slots asc, playlist_count asc, repeat_signal desc, title
        limit 250
    """,
    "playlist_cleanup.csv": """
        select playlist_a_title, playlist_b_title, overlap_track_count, jaccard_overlap
        from yamusic_playlist_overlap
        order by jaccard_overlap desc, overlap_track_count desc, playlist_a_title, playlist_b_title
        limit 250
    """,
    "standout_playlists.csv": """
        select playlist_title, actual_track_count, unique_track_count, uniqueness_ratio,
               max_overlap, overlapped_track_mentions
        from yamusic_playlist_signals
        where underrated_playlist_flag = true
        order by uniqueness_ratio desc, actual_track_count desc, playlist_title
        limit 250
    """,
    "genre_shifts.csv": """
        select activity_month, genre, event_count, active_tracks, event_share_in_month
        from yamusic_genre_periods
        order by activity_month desc, event_share_in_month desc, genre
        limit 500
    """,
}


def env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def write_csv(path: Path, columns: list[str], rows: list[tuple[Any, ...]]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)
    return len(rows)


def export_query(connection: duckdb.DuckDBPyConnection, export_dir: Path, file_name: str, sql: str) -> int:
    cursor = connection.execute(sql)
    columns = [column[0] for column in cursor.description]
    rows = cursor.fetchall()
    return write_csv(export_dir / file_name, columns, rows)


def main() -> int:
    duckdb_path = env_path("STREAMIFY_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
    export_dir = env_path("STREAMIFY_RECOMMENDATIONS_DIR", DEFAULT_EXPORT_DIR)
    if not duckdb_path.exists():
        raise SystemExit(f"Local DuckDB database is missing: {duckdb_path}. Run make dbt-build first.")

    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        counts = {
            file_name: export_query(connection, export_dir, file_name, sql)
            for file_name, sql in EXPORT_QUERIES.items()
        }
    for file_name, row_count in counts.items():
        print(f"wrote {row_count:>5} rows to {export_dir / file_name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
