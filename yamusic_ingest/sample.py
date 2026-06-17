from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def sample_payload() -> dict[str, list[dict[str, Any]]]:
    ingested_at = datetime.now(timezone.utc).isoformat()
    winter = "2026-01-12T19:30:00+00:00"
    spring = "2026-04-08T08:15:00+00:00"
    summer = "2026-06-10T22:05:00+00:00"
    tracks = [
        {
            "track_id": "sample-track-1",
            "title": "Midnight Local",
            "duration_ms": 213000,
            "album_id": "sample-album-1",
            "album_title": "Local Lake",
            "genre": "electronic",
            "release_year": 2024,
            "label": "Streamify Lab",
            "artist_ids": ["sample-artist-1"],
            "artist_names": ["Nadia Vector"],
            "liked": True,
            "source": "sample",
            "ingested_at": ingested_at,
        },
        {
            "track_id": "sample-track-2",
            "title": "Parquet Morning",
            "duration_ms": 188000,
            "album_id": "sample-album-2",
            "album_title": "Warehouse Sketches",
            "genre": "jazz",
            "release_year": 2023,
            "label": "Local First",
            "artist_ids": ["sample-artist-2"],
            "artist_names": ["Duck DB Trio"],
            "liked": True,
            "source": "sample",
            "ingested_at": ingested_at,
        },
        {
            "track_id": "sample-track-3",
            "title": "Repeat Signal",
            "duration_ms": 241000,
            "album_id": "sample-album-1",
            "album_title": "Local Lake",
            "genre": "electronic",
            "release_year": 2024,
            "label": "Streamify Lab",
            "artist_ids": ["sample-artist-1", "sample-artist-3"],
            "artist_names": ["Nadia Vector", "The Lineage"],
            "liked": False,
            "source": "sample",
            "ingested_at": ingested_at,
        },
    ]
    artists = [
        {"artist_id": "sample-artist-1", "artist_name": "Nadia Vector", "source": "sample", "ingested_at": ingested_at},
        {"artist_id": "sample-artist-2", "artist_name": "Duck DB Trio", "source": "sample", "ingested_at": ingested_at},
        {"artist_id": "sample-artist-3", "artist_name": "The Lineage", "source": "sample", "ingested_at": ingested_at},
    ]
    albums = [
        {"album_id": "sample-album-1", "album_title": "Local Lake", "genre": "electronic", "release_year": 2024, "source": "sample", "ingested_at": ingested_at},
        {"album_id": "sample-album-2", "album_title": "Warehouse Sketches", "genre": "jazz", "release_year": 2023, "source": "sample", "ingested_at": ingested_at},
    ]
    playlists = [
        {"playlist_id": "sample-playlist-1", "playlist_title": "Focus Rotation", "track_count": 2, "source": "sample", "ingested_at": ingested_at},
        {"playlist_id": "sample-playlist-2", "playlist_title": "Late Commits", "track_count": 2, "source": "sample", "ingested_at": ingested_at},
    ]
    playlist_tracks = [
        {"playlist_id": "sample-playlist-1", "track_id": "sample-track-1", "position": 1, "source": "sample", "ingested_at": ingested_at},
        {"playlist_id": "sample-playlist-1", "track_id": "sample-track-2", "position": 2, "source": "sample", "ingested_at": ingested_at},
        {"playlist_id": "sample-playlist-2", "track_id": "sample-track-1", "position": 1, "source": "sample", "ingested_at": ingested_at},
        {"playlist_id": "sample-playlist-2", "track_id": "sample-track-3", "position": 2, "source": "sample", "ingested_at": ingested_at},
    ]
    events = [
        {"event_id": "sample-like-1", "event_type": "liked_track", "track_id": "sample-track-1", "event_ts": winter, "source": "sample", "ingested_at": ingested_at},
        {"event_id": "sample-like-2", "event_type": "liked_track", "track_id": "sample-track-2", "event_ts": spring, "source": "sample", "ingested_at": ingested_at},
        {"event_id": "sample-playlist-1", "event_type": "playlist_membership", "track_id": "sample-track-1", "playlist_id": "sample-playlist-1", "event_ts": spring, "source": "sample", "ingested_at": ingested_at},
        {"event_id": "sample-playlist-2", "event_type": "playlist_membership", "track_id": "sample-track-3", "playlist_id": "sample-playlist-2", "event_ts": summer, "source": "sample", "ingested_at": ingested_at},
    ]
    return {
        "tracks": tracks,
        "artists": artists,
        "albums": albums,
        "playlists": playlists,
        "playlist_tracks": playlist_tracks,
        "user_library_events": events,
    }
