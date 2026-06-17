#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import sys
from datetime import date, datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
DEFAULT_DUCKDB_PATH = ROOT / "data" / "streamify.duckdb"
DEFAULT_SNAPSHOT_PATH = ROOT / "data" / "streamify_snapshot.json"


def env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def json_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Path):
        return str(value)
    return value


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    return {key: json_value(value) for key, value in row.items()}


def query_rows(connection: duckdb.DuckDBPyConnection, sql: str, limit: int | None = None) -> list[dict[str, Any]]:
    if limit is not None:
        sql = f"{sql.rstrip().rstrip(';')} limit {int(limit)}"
    cursor = connection.execute(sql)
    columns = [column[0] for column in cursor.description]
    return [normalize_row(dict(zip(columns, row))) for row in cursor.fetchall()]


def scalar(connection: duckdb.DuckDBPyConnection, sql: str, params: tuple[Any, ...] = (), default: Any = None) -> Any:
    rows = connection.execute(sql, params).fetchall()
    if not rows:
        return default
    return rows[0][0]


def has_table(connection: duckdb.DuckDBPyConnection, table_name: str) -> bool:
    return bool(
        scalar(
            connection,
            """
            select count(*)
            from information_schema.tables
            where table_schema = 'main'
              and table_name = ?
            """,
            (table_name,),
            0,
        )
    )


def required_tables_missing(connection: duckdb.DuckDBPyConnection) -> list[str]:
    required_tables = [
        "yamusic_library_profile",
        "yamusic_artist_affinity",
        "yamusic_dim_tracks",
        "yamusic_genre_profile",
        "yamusic_genre_periods",
        "yamusic_period_activity",
        "yamusic_track_signals",
        "yamusic_playlist_overlap",
        "yamusic_playlist_signals",
    ]
    return [table for table in required_tables if not has_table(connection, table)]


def build_snapshot(connection: duckdb.DuckDBPyConnection) -> dict[str, Any]:
    missing = required_tables_missing(connection)
    if missing:
        raise SystemExit(f"Missing required mart tables: {', '.join(missing)}. Run make dbt-build first.")

    profile_rows = query_rows(connection, "select * from yamusic_library_profile limit 1")
    if not profile_rows:
        raise SystemExit("yamusic_library_profile is empty. Run make dbt-build first.")
    profile = profile_rows[0]

    diagnostics = {
        "liked_shortcuts_seen": profile.get("diagnostic_liked_shortcuts_seen"),
        "liked_tracks_written": profile.get("diagnostic_liked_tracks_written"),
        "liked_shortcuts_fetch_failed": profile.get("diagnostic_liked_shortcuts_fetch_failed"),
        "liked_shortcuts_missing_track_id": profile.get("diagnostic_liked_shortcuts_missing_track_id"),
        "liked_tracks_duplicate_skipped": profile.get("diagnostic_liked_tracks_duplicate_skipped"),
        "liked_albums_seen": profile.get("diagnostic_liked_albums_seen"),
        "liked_albums_written": profile.get("diagnostic_liked_albums_written"),
        "liked_albums_missing_id": profile.get("diagnostic_liked_albums_missing_id"),
        "liked_albums_duplicate_skipped": profile.get("diagnostic_liked_albums_duplicate_skipped"),
        "liked_artists_seen": profile.get("diagnostic_liked_artists_seen"),
        "liked_artists_written": profile.get("diagnostic_liked_artists_written"),
        "liked_artists_missing_id": profile.get("diagnostic_liked_artists_missing_id"),
        "liked_artists_duplicate_skipped": profile.get("diagnostic_liked_artists_duplicate_skipped"),
        "liked_playlists_seen": profile.get("diagnostic_liked_playlists_seen"),
        "liked_playlists_written": profile.get("diagnostic_liked_playlists_written"),
        "liked_playlists_missing_id": profile.get("diagnostic_liked_playlists_missing_id"),
        "liked_playlists_duplicate_skipped": profile.get("diagnostic_liked_playlists_duplicate_skipped"),
        "playlists_seen": profile.get("diagnostic_playlists_seen"),
        "playlists_written": profile.get("diagnostic_playlists_written"),
        "playlists_missing_id": profile.get("diagnostic_playlists_missing_id"),
        "playlist_fetch_fallbacks": profile.get("diagnostic_playlist_fetch_fallbacks"),
        "playlist_tracks_seen": profile.get("diagnostic_playlist_tracks_seen"),
        "playlist_tracks_written": profile.get("diagnostic_playlist_tracks_written"),
        "playlist_tracks_fetch_failed": profile.get("diagnostic_playlist_tracks_fetch_failed"),
        "playlist_tracks_missing_track_id": profile.get("diagnostic_playlist_tracks_missing_track_id"),
        "playlist_tracks_duplicate_skipped": profile.get("diagnostic_playlist_tracks_duplicate_skipped"),
    }
    raw_counts = {
        "tracks": profile.get("raw_tracks"),
        "artists": profile.get("raw_artists"),
        "albums": profile.get("raw_albums"),
        "playlists": profile.get("raw_playlists"),
        "playlist_tracks": profile.get("raw_playlist_tracks"),
        "user_library_events": profile.get("raw_user_library_events"),
    }
    raw_checksums = {
        "tracks": profile.get("raw_tracks_sha256"),
        "artists": profile.get("raw_artists_sha256"),
        "albums": profile.get("raw_albums_sha256"),
        "playlists": profile.get("raw_playlists_sha256"),
        "playlist_tracks": profile.get("raw_playlist_tracks_sha256"),
        "user_library_events": profile.get("raw_user_library_events_sha256"),
    }

    answers = {
        "favorite_artists": query_rows(
            connection,
            """
            select artist_name, track_count, liked_track_count, playlist_appearances,
                   avg_playlist_appearances_per_track
            from yamusic_artist_affinity
            order by track_count desc, liked_track_count desc, artist_name
            """,
            20,
        ),
        "favorite_tracks": query_rows(
            connection,
            """
            select title, artist_display, genre, liked, playlist_count
            from yamusic_track_signals
            order by liked desc, playlist_count desc, title
            """,
            20,
        ),
        "genre_profile": query_rows(
            connection,
            """
            select genre, track_count, liked_track_count, library_hours, track_share
            from yamusic_genre_profile
            order by track_count desc, liked_track_count desc, genre
            """,
            20,
        ),
        "genre_shifts": query_rows(
            connection,
            """
            select activity_month, genre, event_count, active_tracks, event_share_in_month
            from yamusic_genre_periods
            order by activity_month desc, event_count desc, genre
            """,
            24,
        ),
        "active_periods": query_rows(
            connection,
            """
            select activity_month, event_count, liked_events, playlist_events,
                   active_tracks, active_artists
            from yamusic_period_activity
            order by activity_month desc
            """,
            24,
        ),
        "repeat_tracks": query_rows(
            connection,
            """
            select title, artist_display, genre, playlist_slots, playlist_count, repeat_signal
            from yamusic_track_signals
            where repeat_signal > 0
            order by repeat_signal desc, playlist_slots desc, title
            """,
            20,
        ),
        "underrated_tracks": query_rows(
            connection,
            """
            select title, artist_display, genre, playlist_slots, playlist_count
            from yamusic_track_signals
            where underrated_flag = true
            order by playlist_slots asc, title
            """,
            20,
        ),
        "playlist_overlap": query_rows(
            connection,
            """
            select playlist_a_title, playlist_b_title, overlap_track_count, jaccard_overlap
            from yamusic_playlist_overlap
            order by jaccard_overlap desc, overlap_track_count desc,
                     playlist_a_title, playlist_b_title
            """,
            20,
        ),
        "underrated_playlists": query_rows(
            connection,
            """
            select playlist_title, actual_track_count, unique_track_count, uniqueness_ratio,
                   max_overlap, overlapped_track_mentions
            from yamusic_playlist_signals
            where underrated_playlist_flag = true
            order by uniqueness_ratio desc, actual_track_count desc, playlist_title
            """,
            20,
        ),
    }

    source = str(profile.get("manifest_source") or "unknown")
    total_tracks = int(profile.get("total_tracks") or 0)
    stale = bool(profile.get("stale_ingestion_flag"))
    next_actions = []
    if source != "yandex_music":
        next_actions.append("Set YANDEX_MUSIC_TOKEN in .env and run make acceptance-real to replace sample metadata.")
    if stale:
        next_actions.append("Rerun ingestion or inspect timestamp availability because stale_ingestion_flag is true.")
    if total_tracks == 0:
        next_actions.append("Run make ingest-sample for deterministic demo data or verify that the Yandex Music account exposes library metadata.")
    if not next_actions:
        next_actions.append("Open make dashboard and use filters to inspect artists, genres, playlists and data quality.")

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "product": "Streamify Yandex Music Self-Analytics",
        "source": source,
        "real_account_verified": source == "yandex_music",
        "profile": profile,
        "quality": {
            "stale_ingestion_flag": profile.get("stale_ingestion_flag"),
            "manifest_generated_at": profile.get("manifest_generated_at"),
            "manifest_json_only": profile.get("manifest_json_only"),
            "adapter": {
                "adapter_name": profile.get("adapter_name"),
                "adapter_version": profile.get("adapter_version"),
                "client_library": profile.get("client_library"),
                "client_library_version": profile.get("client_library_version"),
            },
            "raw_counts": raw_counts,
            "raw_checksums": raw_checksums,
            "ingestion_diagnostics": diagnostics,
        },
        "answers": answers,
        "next_actions": next_actions,
    }


def main() -> int:
    duckdb_path = env_path("STREAMIFY_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
    snapshot_path = env_path("STREAMIFY_SNAPSHOT_PATH", DEFAULT_SNAPSHOT_PATH)
    if not duckdb_path.exists():
        raise SystemExit(f"Local DuckDB database is missing: {duckdb_path}. Run make dbt-build first.")

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        snapshot_path.write_text(
            json.dumps(build_snapshot(connection), ensure_ascii=False, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    print(f"Wrote Yandex Music self-analytics JSON snapshot: {snapshot_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
