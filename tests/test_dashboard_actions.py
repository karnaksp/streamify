from __future__ import annotations

from dashboard.actions import build_data_next_actions


def test_build_data_next_actions_guides_sample_to_real_acceptance() -> None:
    actions = build_data_next_actions(
        {
            "manifest_source": "sample",
            "total_tracks": 3,
            "known_genres": 2,
            "stale_ingestion_flag": 0,
            "top_artist_concentration": 0.2,
        }
    )

    assert any("YANDEX_MUSIC_TOKEN" in action for action in actions)
    assert any("make acceptance-real" in action for action in actions)


def test_build_data_next_actions_surfaces_quality_failures() -> None:
    actions = build_data_next_actions(
        {
            "manifest_source": "yandex_music",
            "total_tracks": 100,
            "known_genres": 0,
            "stale_ingestion_flag": 1,
            "diagnostic_liked_shortcuts_fetch_failed": 4,
            "diagnostic_playlist_tracks_fetch_failed": 5,
            "diagnostic_playlist_tracks_missing_track_id": 2,
            "diagnostic_liked_tracks_duplicate_skipped": 1,
            "diagnostic_playlist_tracks_duplicate_skipped": 3,
            "top_artist_concentration": 0.65,
        }
    )

    assert any("stale_ingestion_flag" in action for action in actions)
    assert any("liked shortcuts failed" in action for action in actions)
    assert any("playlist shortcuts failed" in action for action in actions)
    assert any("no stable track id" in action for action in actions)
    assert any("Duplicate library rows" in action for action in actions)
    assert any("Genre coverage is missing" in action for action in actions)
    assert any("concentrated" in action for action in actions)


def test_build_data_next_actions_has_ready_state() -> None:
    actions = build_data_next_actions(
        {
            "manifest_source": "yandex_music",
            "total_tracks": 100,
            "known_genres": 12,
            "stale_ingestion_flag": 0,
            "diagnostic_liked_shortcuts_fetch_failed": 0,
            "diagnostic_playlist_tracks_missing_track_id": 0,
            "top_artist_concentration": 0.2,
        }
    )

    assert actions == ["Data is ready for exploration; review rediscovery tracks, playlist overlap and genre shifts."]
