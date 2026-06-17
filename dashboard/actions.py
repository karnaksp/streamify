from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def safe_int(value: Any) -> int:
    try:
        if value is None:
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


def safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def build_data_next_actions(profile: Mapping[str, Any]) -> list[str]:
    actions: list[str] = []
    source = str(profile.get("manifest_source") or "unknown")
    total_tracks = safe_int(profile.get("total_tracks"))
    known_genres = safe_int(profile.get("known_genres"))
    stale = safe_int(profile.get("stale_ingestion_flag")) == 1
    liked_fetch_failures = safe_int(profile.get("diagnostic_liked_shortcuts_fetch_failed"))
    playlist_track_fetch_failures = safe_int(profile.get("diagnostic_playlist_tracks_fetch_failed"))
    playlist_track_missing_ids = safe_int(profile.get("diagnostic_playlist_tracks_missing_track_id"))
    duplicate_liked_tracks = safe_int(profile.get("diagnostic_liked_tracks_duplicate_skipped"))
    duplicate_playlist_tracks = safe_int(profile.get("diagnostic_playlist_tracks_duplicate_skipped"))
    top_artist_concentration = safe_float(profile.get("top_artist_concentration"))

    if source != "yandex_music":
        actions.append("Replace sample metadata with account metadata: set YANDEX_MUSIC_TOKEN in .env and run make acceptance-real.")
    if total_tracks == 0:
        actions.append("No library rows are available; run make status, then verify account visibility with make preflight.")
    if stale:
        actions.append("Refresh ingestion because stale_ingestion_flag is true; rerun make ingest and make dbt-build.")
    if liked_fetch_failures > 0:
        actions.append(f"Investigate partial liked-track hydration: {liked_fetch_failures} liked shortcuts failed to fetch.")
    if playlist_track_fetch_failures > 0:
        actions.append(f"Investigate partial playlist-track enrichment: {playlist_track_fetch_failures} playlist shortcuts failed to fetch.")
    if playlist_track_missing_ids > 0:
        actions.append(f"Inspect playlist metadata quality: {playlist_track_missing_ids} playlist rows had no stable track id.")
    if duplicate_liked_tracks > 0 or duplicate_playlist_tracks > 0:
        actions.append(
            "Duplicate library rows were skipped during ingestion; review the Data Quality tab before comparing playlist overlap across runs."
        )
    if total_tracks > 0 and known_genres == 0:
        actions.append("Genre coverage is missing; use artist and playlist signals as the primary analytics views.")
    if top_artist_concentration >= 0.5:
        actions.append("Taste is concentrated around the top artist; use underrated tracks and genre views to find variety.")
    if not actions:
        actions.append("Data is ready for exploration; review rediscovery tracks, playlist overlap and genre shifts.")

    return actions
