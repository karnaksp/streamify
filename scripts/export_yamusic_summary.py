#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
DEFAULT_DUCKDB_PATH = ROOT / "data" / "streamify.duckdb"
DEFAULT_REPORT_PATH = ROOT / "data" / "streamify_summary.md"


def env_path(name: str, default: Path) -> Path:
    value = os.getenv(name)
    if not value:
        return default
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def query_rows(connection: duckdb.DuckDBPyConnection, sql: str, limit: int | None = None) -> list[dict[str, Any]]:
    if limit is not None:
        sql = f"{sql.rstrip().rstrip(';')} limit {int(limit)}"
    cursor = connection.execute(sql)
    columns = [column[0] for column in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


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


def fmt(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        if value.is_integer():
            return f"{int(value):,}"
        return f"{value:,.2f}"
    if isinstance(value, int):
        return f"{value:,}"
    return str(value).replace("|", "\\|").replace("\n", " ")


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value) * 100:.1f}%"
    except (TypeError, ValueError):
        return "n/a"


def markdown_table(rows: list[dict[str, Any]], columns: list[tuple[str, str]], empty: str) -> str:
    if not rows:
        return empty
    headers = [label for _, label in columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(fmt(row.get(key)) for key, _ in columns) + " |")
    return "\n".join(lines)


def profile_summary(profile: dict[str, Any]) -> list[str]:
    manifest_source = str(profile.get("manifest_source") or "unknown")
    manifest_generated_at = profile.get("manifest_generated_at") or "unknown"
    total_tracks = int(profile.get("total_tracks") or 0)
    artists = int(profile.get("artists") or 0)
    playlists = int(profile.get("playlists") or 0)
    library_hours = float(profile.get("library_hours") or 0)
    concentration = pct(profile.get("top_artist_concentration"))
    top_genre_share = pct(profile.get("top_genre_share"))
    stale = bool(profile.get("stale_ingestion_flag"))

    if total_tracks == 0:
        return [
            f"**The latest raw run source is `{manifest_source}` from {manifest_generated_at}.** Use this to distinguish deterministic sample data from real Yandex Music metadata.",
            "**No account metadata is available yet.** The pipeline built successfully, but Yandex Music returned zero tracks or the current run used an empty fixture.",
            "**The product path is still verifiable.** Run `make ingest-sample` for deterministic demo data, or set `YANDEX_MUSIC_TOKEN` in `.env` and run `make acceptance-real` for account metadata.",
            "**Data freshness needs a real library event.** The stale flag remains active until ingestion returns timestamped liked-track or playlist metadata.",
        ]

    freshness = "stale" if stale else "fresh"
    return [
        f"**The latest raw run source is `{manifest_source}` from {manifest_generated_at}.** Use this to distinguish deterministic sample data from real Yandex Music metadata.",
        f"**The library contains {total_tracks:,} tracks across {artists:,} artists and {playlists:,} playlists.** The local warehouse estimates about {library_hours:,.1f} hours of catalogued music metadata.",
        f"**Taste concentration is {concentration} for the top artist and {top_genre_share} for the top genre.** Use those shares to judge whether recommendations are narrow or broad.",
        f"**The latest ingestion health is {freshness}.** The dashboard and report are driven by the same DuckDB marts, so this summary is reproducible from the local data files.",
    ]


def build_report(connection: duckdb.DuckDBPyConnection) -> str:
    required_tables = [
        "yamusic_library_profile",
        "yamusic_artist_affinity",
        "yamusic_genre_periods",
        "yamusic_track_signals",
        "yamusic_playlist_signals",
    ]
    missing = [table for table in required_tables if not has_table(connection, table)]
    if missing:
        raise SystemExit(f"Missing required mart tables: {', '.join(missing)}. Run make dbt-build first.")

    profile_rows = query_rows(connection, "select * from yamusic_library_profile limit 1")
    if not profile_rows:
        raise SystemExit("yamusic_library_profile is empty. Run make dbt-build first.")
    profile = profile_rows[0]

    top_artists = query_rows(
        connection,
        """
        select artist_name, track_count, liked_track_count, playlist_appearances,
               avg_playlist_appearances_per_track
        from yamusic_artist_affinity
        order by track_count desc, liked_track_count desc, artist_name
        """,
        10,
    )
    genre_shifts = query_rows(
        connection,
        """
        select activity_month, genre, event_count, active_tracks, event_share_in_month
        from yamusic_genre_periods
        order by activity_month desc, event_count desc, genre
        """,
        12,
    )
    repeated_tracks = query_rows(
        connection,
        """
        select title, artist_display, genre, playlist_slots, playlist_count, repeat_signal
        from yamusic_track_signals
        where repeat_signal > 0
        order by repeat_signal desc, playlist_slots desc, title
        """,
        10,
    )
    underrated_tracks = query_rows(
        connection,
        """
        select title, artist_display, genre, playlist_slots, playlist_count
        from yamusic_track_signals
        where underrated_flag = true
        order by playlist_slots asc, title
        """,
        10,
    )
    underrated_playlists = query_rows(
        connection,
        """
        select playlist_title, actual_track_count, unique_track_count, uniqueness_ratio,
               max_overlap, overlapped_track_mentions
        from yamusic_playlist_signals
        where underrated_playlist_flag = true
        order by uniqueness_ratio desc, actual_track_count desc, playlist_title
        """,
        10,
    )

    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total_tracks = int(profile.get("total_tracks") or 0)
    stale = bool(profile.get("stale_ingestion_flag"))
    profile_display = dict(profile)
    profile_display["stale_ingestion_flag"] = "yes" if stale else "no"
    profile_display["manifest_json_only"] = "yes" if profile.get("manifest_json_only") else "no"
    for row in genre_shifts:
        row["event_share_in_month"] = pct(row.get("event_share_in_month"))
    for row in underrated_playlists:
        row["uniqueness_ratio"] = pct(row.get("uniqueness_ratio"))
        row["max_overlap"] = pct(row.get("max_overlap"))

    lines = [
        "# Streamify Yandex Music Self-Analytics Summary",
        "",
        f"Generated: {generated_at}",
        "",
        "## Executive Summary",
        "",
        *[f"- {item}" for item in profile_summary(profile)],
        "",
        "## What The Local Library Looks Like",
        "",
        "These headline metrics come from `yamusic_library_profile`, the one-row mart that combines raw ingestion freshness, artist concentration, playlist coverage, genre availability and signal counts.",
        "",
        markdown_table(
            [profile_display],
            [
                ("total_tracks", "Tracks"),
                ("liked_tracks", "Liked"),
                ("artists", "Artists"),
                ("playlists", "Playlists"),
                ("library_hours", "Library hours"),
                ("known_genres", "Known genres"),
                ("active_months", "Active months"),
                ("stale_ingestion_flag", "Stale"),
                ("manifest_source", "Source"),
            ],
            "No profile row is available.",
        ),
        "",
        "## Raw Ingestion Counts",
        "",
        "These counts come from `_manifest.json` through `stg_yamusic_manifest` and are copied into `yamusic_library_profile` to make stale dbt builds visible.",
        "",
        markdown_table(
            [profile_display],
            [
                ("manifest_generated_at", "Manifest generated"),
                ("manifest_json_only", "JSON only"),
                ("adapter_name", "Adapter"),
                ("adapter_version", "Adapter version"),
                ("client_library", "Client library"),
                ("client_library_version", "Client version"),
                ("raw_tracks", "Raw tracks"),
                ("raw_artists", "Raw artists"),
                ("raw_albums", "Raw albums"),
                ("raw_playlists", "Raw playlists"),
                ("raw_playlist_tracks", "Raw playlist tracks"),
                ("raw_user_library_events", "Raw events"),
            ],
            "No raw manifest profile is available.",
        ),
        "",
        "### Raw File Checksums",
        "",
        "These SHA256 checksums identify the exact JSONL files used for the local DuckDB build.",
        "",
        markdown_table(
            [profile_display],
            [
                ("raw_tracks_sha256", "Tracks"),
                ("raw_artists_sha256", "Artists"),
                ("raw_albums_sha256", "Albums"),
                ("raw_playlists_sha256", "Playlists"),
                ("raw_playlist_tracks_sha256", "Playlist tracks"),
                ("raw_user_library_events_sha256", "Events"),
            ],
            "No raw checksums are available.",
        ),
        "",
        "### Ingestion Diagnostics",
        "",
        "Diagnostics are aggregate counters only. They help identify partial Yandex Music API responses without storing skipped track, playlist or account identifiers.",
        "",
        markdown_table(
            [profile_display],
            [
                ("diagnostic_liked_shortcuts_seen", "Liked shortcuts seen"),
                ("diagnostic_liked_tracks_written", "Liked tracks written"),
                ("diagnostic_liked_shortcuts_fetch_failed", "Liked fetch failures"),
                ("diagnostic_liked_shortcuts_missing_track_id", "Liked missing IDs"),
                ("diagnostic_liked_tracks_duplicate_skipped", "Liked duplicates skipped"),
                ("diagnostic_liked_albums_seen", "Liked albums seen"),
                ("diagnostic_liked_albums_written", "Liked albums written"),
                ("diagnostic_liked_albums_missing_id", "Liked albums missing IDs"),
                ("diagnostic_liked_albums_duplicate_skipped", "Liked album duplicates skipped"),
                ("diagnostic_liked_artists_seen", "Liked artists seen"),
                ("diagnostic_liked_artists_written", "Liked artists written"),
                ("diagnostic_liked_artists_missing_id", "Liked artists missing IDs"),
                ("diagnostic_liked_artists_duplicate_skipped", "Liked artist duplicates skipped"),
                ("diagnostic_liked_playlists_seen", "Liked playlists seen"),
                ("diagnostic_liked_playlists_written", "Liked playlists written"),
                ("diagnostic_liked_playlists_missing_id", "Liked playlists missing IDs"),
                ("diagnostic_liked_playlists_duplicate_skipped", "Liked playlist duplicates skipped"),
                ("diagnostic_playlists_seen", "Playlists seen"),
                ("diagnostic_playlists_written", "Playlists written"),
                ("diagnostic_playlists_missing_id", "Playlists missing IDs"),
                ("diagnostic_playlist_fetch_fallbacks", "Playlist fetch fallbacks"),
                ("diagnostic_playlist_tracks_seen", "Playlist tracks seen"),
                ("diagnostic_playlist_tracks_written", "Playlist tracks written"),
                ("diagnostic_playlist_tracks_fetch_failed", "Playlist track fetch failures"),
                ("diagnostic_playlist_tracks_missing_track_id", "Playlist tracks missing IDs"),
                ("diagnostic_playlist_tracks_duplicate_skipped", "Playlist duplicates skipped"),
            ],
            "No ingestion diagnostics are available.",
        ),
        "",
        "## Artist Affinity Is The Main Taste Signal",
        "",
        "Top artists are ranked by catalog presence first, then liked-track count. This makes the table useful for deciding whether the library is concentrated around a few artists or spread across many smaller preferences.",
        "",
        markdown_table(
            top_artists,
            [
                ("artist_name", "Artist"),
                ("track_count", "Tracks"),
                ("liked_track_count", "Liked tracks"),
                ("playlist_appearances", "Playlist slots"),
                ("avg_playlist_appearances_per_track", "Slots per track"),
            ],
            "No artist rows are available.",
        ),
        "",
        "## Genre Shifts Depend On Metadata Coverage",
        "",
        "Genre-period rows use only tracks where Yandex Music exposes genre metadata. When genre coverage is sparse, treat this as a directional view rather than a complete listening history.",
        "",
        markdown_table(
            genre_shifts,
            [
                ("activity_month", "Month"),
                ("genre", "Genre"),
                ("event_count", "Events"),
                ("active_tracks", "Tracks"),
                ("event_share_in_month", "Share"),
            ],
            "No genre-period rows are available.",
        ),
        "",
        "## Repeats And Underrated Tracks Show Actionable Library Work",
        "",
        "Repeated tracks are useful for playlist cleanup and taste concentration checks. Underrated tracks are liked tracks with low playlist coverage, which makes them candidates for rediscovery playlists.",
        "",
        markdown_table(
            repeated_tracks,
            [
                ("title", "Track"),
                ("artist_display", "Artist"),
                ("genre", "Genre"),
                ("playlist_slots", "Playlist slots"),
                ("playlist_count", "Playlists"),
                ("repeat_signal", "Repeat signal"),
            ],
            "No repeated-track signals are available.",
        ),
        "",
        markdown_table(
            underrated_tracks,
            [
                ("title", "Track"),
                ("artist_display", "Artist"),
                ("genre", "Genre"),
                ("playlist_slots", "Playlist slots"),
                ("playlist_count", "Playlists"),
            ],
            "No underrated-track candidates are available.",
        ),
        "",
        "## Playlist Overlap Highlights Where Curation Can Improve",
        "",
        "Underrated playlists have high uniqueness and low overlap. They are good candidates for highlighting because they add variety rather than duplicating the same tracks across the library.",
        "",
        markdown_table(
            underrated_playlists,
            [
                ("playlist_title", "Playlist"),
                ("actual_track_count", "Tracks"),
                ("unique_track_count", "Unique tracks"),
                ("uniqueness_ratio", "Uniqueness"),
                ("max_overlap", "Max overlap"),
                ("overlapped_track_mentions", "Overlap mentions"),
            ],
            "No underrated-playlist candidates are available.",
        ),
        "",
        "## Recommended Next Steps",
        "",
        "- Use `make dashboard` for interactive filtering after reading this static summary.",
        "- Run `make acceptance-real` after adding a real `YANDEX_MUSIC_TOKEN` to refresh the report from account metadata.",
        "- Watch `stale_ingestion_flag`; if it is true on a real account, rerun ingestion or inspect whether the API returned timestamped events.",
        "",
        "## Further Questions",
        "",
        "- Which genres or languages are underrepresented because the Yandex Music API did not expose metadata?",
        "- Which playlist overlaps should be merged, split or archived?",
        "- Which underrated tracks should be promoted into a rediscovery playlist?",
        "",
        "## Caveats And Assumptions",
        "",
        "- The project stores metadata, events and aggregates only; it does not download or store audio.",
        "- Yandex Music integration uses an unofficial Python client, so available fields can vary by account, region and library visibility.",
        "- This summary is not a full listening-history analysis unless the account/API returns timestamped history-like metadata.",
    ]

    if total_tracks == 0:
        lines.extend(
            [
                "",
                "## No-Data Runbook",
                "",
                "A zero-track report is still a valid local build check. For real analytics, set `YANDEX_MUSIC_TOKEN` in `.env`, run `make preflight`, then run `make acceptance-real`.",
            ]
        )
    if stale:
        lines.extend(
            [
                "",
                "## Freshness Warning",
                "",
                "`stale_ingestion_flag` is true. The latest local event is missing or older than the configured freshness threshold, so use the report for structure validation until ingestion is refreshed.",
            ]
        )

    return "\n".join(lines) + "\n"


def main() -> int:
    duckdb_path = env_path("STREAMIFY_DUCKDB_PATH", DEFAULT_DUCKDB_PATH)
    report_path = env_path("STREAMIFY_REPORT_PATH", DEFAULT_REPORT_PATH)
    if not duckdb_path.exists():
        raise SystemExit(f"Local DuckDB database is missing: {duckdb_path}. Run make dbt-build first.")

    report_path.parent.mkdir(parents=True, exist_ok=True)
    with duckdb.connect(str(duckdb_path), read_only=True) as connection:
        report_path.write_text(build_report(connection), encoding="utf-8")
    print(f"Wrote Yandex Music self-analytics summary: {report_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
