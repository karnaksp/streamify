from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from time import sleep
from typing import Any

from yamusic_ingest import __version__


class YandexMusicIngestError(RuntimeError):
    """Raised for sanitized, user-facing Yandex Music ingestion failures."""


@dataclass(frozen=True)
class IngestResult:
    payload: dict[str, list[dict[str, Any]]]
    diagnostics: dict[str, int]


def _sanitize_message(message: str, token: str | None = None) -> str:
    sanitized = message
    if token:
        sanitized = sanitized.replace(token, "[redacted-token]")
    return sanitized


def _call_with_retries(label: str, func: Callable[[], Any], *, attempts: int = 3, delay_seconds: float = 0.25) -> Any:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return func()
        except Exception as exc:  # noqa: BLE001 - external client exceptions vary by version.
            last_error = exc
            if attempt == attempts:
                break
            sleep(delay_seconds * attempt)
    message = str(last_error) or last_error.__class__.__name__ if last_error else "unknown error"
    raise YandexMusicIngestError(f"{label} failed after {attempts} attempts: {message}") from last_error


def _value(obj: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(obj, dict) and name in obj:
            return obj[name]
        if hasattr(obj, name):
            return getattr(obj, name)
    return default


def _track_id(track: Any) -> str:
    value = _value(track, "id", "track_id")
    return str(value)


def _has_track_id(track: Any) -> bool:
    value = _value(track, "id", "track_id", default=None)
    return value is not None and str(value) != ""


def _album_id(album: Any) -> str:
    value = _value(album, "id", "album_id")
    return str(value)


def _has_album_id(album: Any) -> bool:
    value = _value(album, "id", "album_id", default=None)
    return value is not None and str(value) != ""


def _artist_id(artist: Any) -> str:
    value = _value(artist, "id", "artist_id")
    return str(value)


def _has_artist_id(artist: Any) -> bool:
    value = _value(artist, "id", "artist_id", default=None)
    return value is not None and str(value) != ""


def _album(track: Any) -> Any | None:
    albums = _value(track, "albums", default=[]) or []
    return albums[0] if albums else None


def _artists(track: Any) -> list[Any]:
    return list(_value(track, "artists", default=[]) or [])


def _duration_ms(track: Any) -> Any:
    value = _value(track, "duration_ms", "durationMs", default=None)
    if value is not None:
        return value
    duration = _value(track, "duration", default=None)
    if isinstance(duration, (int, float)) and duration < 10_000:
        return int(duration * 1000)
    return duration


def _first_non_empty(values: list[Any]) -> Any:
    for value in values:
        if value not in {None, ""}:
            return value
    return None


def _first_artist_genre(artists: list[Any]) -> Any:
    for artist in artists:
        genres = _value(artist, "genres", default=None) or []
        if genres:
            return genres[0]
    return None


def _label(track: Any, album: Any | None, major: Any | None) -> Any:
    if isinstance(major, str):
        return major
    if major:
        value = _value(major, "name", default=None)
        if value:
            return value
    labels = _value(album, "labels", default=[]) if album else []
    for label in labels or []:
        if isinstance(label, str):
            return label
        value = _value(label, "name", default=None)
        if value:
            return value
    return None


def _playlist_id(playlist: Any) -> str:
    owner = _value(playlist, "owner", default=None)
    uid = _first_non_empty([_value(playlist, "uid", default=None), _value(owner, "uid", "id", default=None)])
    kind = _value(playlist, "kind", default=None)
    if uid not in {None, ""} and kind not in {None, ""}:
        return f"{uid}:{kind}"
    value = _first_non_empty([kind, uid, _value(playlist, "id", default=None), _value(playlist, "playlist_uuid", default=None)])
    return str(value or "")


def _normalize_playlist(playlist: Any, source: str, ingested_at: str) -> dict[str, Any]:
    return {
        "playlist_id": _playlist_id(playlist),
        "playlist_title": _value(playlist, "title", default=""),
        "track_count": _value(playlist, "track_count", "trackCount", default=None),
        "source": source,
        "ingested_at": ingested_at,
    }


def _playlist_with_tracks(playlist: Any) -> tuple[Any, bool]:
    if not hasattr(playlist, "fetch_tracks"):
        return playlist, False
    try:
        return _call_with_retries("playlist.fetch_tracks", playlist.fetch_tracks), False
    except YandexMusicIngestError:
        return playlist, True


def _playlist_items(playlist_or_tracks: Any) -> list[Any]:
    if isinstance(playlist_or_tracks, list):
        return playlist_or_tracks
    return list(_value(playlist_or_tracks, "tracks", default=[]) or [])


def _track_from_playlist_item(item: Any) -> tuple[Any, bool]:
    embedded_track = _value(item, "track", default=None)
    if embedded_track is not None:
        return embedded_track, False
    if hasattr(item, "fetch_track"):
        try:
            return _call_with_retries("playlist track fetch_track", item.fetch_track), False
        except YandexMusicIngestError:
            return item, True
    return item, False


def _track_from_liked_shortcut(shortcut: Any) -> tuple[Any, bool]:
    if hasattr(shortcut, "fetch_track"):
        try:
            return _call_with_retries("shortcut.fetch_track", shortcut.fetch_track), False
        except YandexMusicIngestError:
            embedded_track = _value(shortcut, "track", default=None)
            return embedded_track if embedded_track is not None else shortcut, True
    return shortcut, False


def _iso_timestamp(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.isoformat()
    if isinstance(value, (int, float)):
        seconds = value / 1000 if value > 10_000_000_000 else value
        return datetime.fromtimestamp(seconds, tz=timezone.utc).isoformat()
    return str(value)


def _available_timestamp(obj: Any) -> str | None:
    value = _value(
        obj,
        "timestamp",
        "created",
        "created_at",
        "createdAt",
        "modified",
        "modified_at",
        "modifiedAt",
        "recent",
        "recent_timestamp",
        default=None,
    )
    return _iso_timestamp(value)


def _normalize_track(track: Any, source: str, ingested_at: str, liked: bool) -> dict[str, Any]:
    album = _album(track)
    artists = _artists(track)
    major = _value(track, "major", default=None)
    genre = _first_non_empty([
        _value(track, "genre", default=None),
        _value(album, "genre", default=None),
        _first_artist_genre(artists),
    ])
    release_year = _first_non_empty([
        _value(track, "year", default=None),
        _value(album, "year", default=None),
        _value(album, "original_release_year", default=None),
    ])
    return {
        "track_id": _track_id(track),
        "title": _value(track, "title", default=""),
        "duration_ms": _duration_ms(track),
        "album_id": str(_value(album, "id", default="")) if album else None,
        "album_title": _value(album, "title", default=None) if album else None,
        "genre": genre,
        "release_year": release_year,
        "label": _label(track, album, major),
        "artist_ids": [str(_value(artist, "id", default="")) for artist in artists],
        "artist_names": [_value(artist, "name", default="") for artist in artists],
        "liked": liked,
        "source": source,
        "ingested_at": ingested_at,
    }


def _normalize_album(album: Any, source: str, ingested_at: str) -> dict[str, Any]:
    return {
        "album_id": _album_id(album),
        "album_title": _value(album, "title", default=None),
        "genre": _value(album, "genre", default=None),
        "release_year": _first_non_empty([
            _value(album, "year", default=None),
            _value(album, "original_release_year", default=None),
        ]),
        "source": source,
        "ingested_at": ingested_at,
    }


def _normalize_artist(artist: Any, source: str, ingested_at: str) -> dict[str, Any]:
    return {
        "artist_id": _artist_id(artist),
        "artist_name": _value(artist, "name", default=""),
        "source": source,
        "ingested_at": ingested_at,
    }


def build_ingest_result_from_client(client: Any) -> IngestResult:
    ingested_at = datetime.now(timezone.utc).isoformat()
    diagnostics = {
        "liked_shortcuts_seen": 0,
        "liked_tracks_written": 0,
        "liked_shortcuts_fetch_failed": 0,
        "liked_shortcuts_missing_track_id": 0,
        "liked_tracks_duplicate_skipped": 0,
        "liked_albums_seen": 0,
        "liked_albums_written": 0,
        "liked_albums_missing_id": 0,
        "liked_albums_duplicate_skipped": 0,
        "liked_artists_seen": 0,
        "liked_artists_written": 0,
        "liked_artists_missing_id": 0,
        "liked_artists_duplicate_skipped": 0,
        "liked_playlists_seen": 0,
        "liked_playlists_written": 0,
        "liked_playlists_missing_id": 0,
        "liked_playlists_duplicate_skipped": 0,
        "playlists_seen": 0,
        "playlists_written": 0,
        "playlists_missing_id": 0,
        "playlist_fetch_fallbacks": 0,
        "playlist_tracks_seen": 0,
        "playlist_tracks_written": 0,
        "playlist_tracks_fetch_failed": 0,
        "playlist_tracks_missing_track_id": 0,
        "playlist_tracks_duplicate_skipped": 0,
    }

    liked_tracks = []
    liked_track_ids: set[str] = set()
    liked_tracks_response = _call_with_retries("client.users_likes_tracks", client.users_likes_tracks)
    for shortcut in getattr(liked_tracks_response, "tracks", []) or []:
        diagnostics["liked_shortcuts_seen"] += 1
        track, track_fetch_failed = _track_from_liked_shortcut(shortcut)
        if track_fetch_failed:
            diagnostics["liked_shortcuts_fetch_failed"] += 1
        if not _has_track_id(track):
            diagnostics["liked_shortcuts_missing_track_id"] += 1
            continue
        track_id = _track_id(track)
        if track_id in liked_track_ids:
            diagnostics["liked_tracks_duplicate_skipped"] += 1
            continue
        liked_track_ids.add(track_id)
        normalized = _normalize_track(track, "yandex_music", ingested_at, liked=True)
        normalized["liked_at"] = _available_timestamp(shortcut) or ingested_at
        liked_tracks.append(normalized)
        diagnostics["liked_tracks_written"] += 1

    playlists_by_id: dict[str, dict[str, Any]] = {}
    playlist_tracks: list[dict[str, Any]] = []
    playlist_track_rows: dict[str, dict[str, Any]] = {}
    playlist_track_memberships: set[tuple[str, str]] = set()
    for playlist in _call_with_retries("client.users_playlists_list", client.users_playlists_list) or []:
        diagnostics["playlists_seen"] += 1
        playlist_id = _playlist_id(playlist)
        if not playlist_id:
            diagnostics["playlists_missing_id"] += 1
            continue
        playlists_by_id[playlist_id] = _normalize_playlist(playlist, "yandex_music", ingested_at)
        diagnostics["playlists_written"] += 1
        full_playlist, used_fallback = _playlist_with_tracks(playlist)
        if used_fallback:
            diagnostics["playlist_fetch_fallbacks"] += 1
        for position, item in enumerate(_playlist_items(full_playlist), start=1):
            diagnostics["playlist_tracks_seen"] += 1
            track, track_fetch_failed = _track_from_playlist_item(item)
            if track_fetch_failed:
                diagnostics["playlist_tracks_fetch_failed"] += 1
            if not _has_track_id(track):
                diagnostics["playlist_tracks_missing_track_id"] += 1
                continue
            normalized = _normalize_track(track, "yandex_music", ingested_at, liked=False)
            membership_key = (playlist_id, normalized["track_id"])
            if membership_key in playlist_track_memberships:
                diagnostics["playlist_tracks_duplicate_skipped"] += 1
                continue
            playlist_track_memberships.add(membership_key)
            playlist_track_rows[normalized["track_id"]] = normalized
            playlist_tracks.append(
                {
                    "playlist_id": playlist_id,
                    "track_id": normalized["track_id"],
                    "position": position,
                    "added_at": _available_timestamp(item),
                    "source": "yandex_music",
                    "ingested_at": ingested_at,
                }
            )
            diagnostics["playlist_tracks_written"] += 1

    tracks_by_id = {row["track_id"]: row for row in playlist_track_rows.values()}
    for row in liked_tracks:
        tracks_by_id[row["track_id"]] = row

    artists: dict[str, dict[str, Any]] = {}
    albums: dict[str, dict[str, Any]] = {}
    for row in tracks_by_id.values():
        if row.get("album_id"):
            albums[row["album_id"]] = {
                "album_id": row["album_id"],
                "album_title": row.get("album_title"),
                "genre": row.get("genre"),
                "release_year": row.get("release_year"),
                "source": "yandex_music",
                "ingested_at": ingested_at,
            }
        for artist_id, artist_name in zip(row.get("artist_ids") or [], row.get("artist_names") or []):
            if artist_id:
                artists[artist_id] = {
                    "artist_id": artist_id,
                    "artist_name": artist_name,
                    "source": "yandex_music",
                    "ingested_at": ingested_at,
                }

    liked_albums_response = _call_with_retries("client.users_likes_albums", client.users_likes_albums) if hasattr(client, "users_likes_albums") else []
    for like in liked_albums_response or []:
        diagnostics["liked_albums_seen"] += 1
        album = _value(like, "album", default=like)
        if not _has_album_id(album):
            diagnostics["liked_albums_missing_id"] += 1
            continue
        album_id = _album_id(album)
        if album_id in albums:
            diagnostics["liked_albums_duplicate_skipped"] += 1
            continue
        albums[album_id] = _normalize_album(album, "yandex_music", ingested_at)
        diagnostics["liked_albums_written"] += 1

    liked_artists_response = _call_with_retries("client.users_likes_artists", client.users_likes_artists) if hasattr(client, "users_likes_artists") else []
    for like in liked_artists_response or []:
        diagnostics["liked_artists_seen"] += 1
        artist = _value(like, "artist", default=like)
        if not _has_artist_id(artist):
            diagnostics["liked_artists_missing_id"] += 1
            continue
        artist_id = _artist_id(artist)
        if artist_id in artists:
            diagnostics["liked_artists_duplicate_skipped"] += 1
            continue
        artists[artist_id] = _normalize_artist(artist, "yandex_music", ingested_at)
        diagnostics["liked_artists_written"] += 1

    liked_playlists_response = _call_with_retries("client.users_likes_playlists", client.users_likes_playlists) if hasattr(client, "users_likes_playlists") else []
    for like in liked_playlists_response or []:
        diagnostics["liked_playlists_seen"] += 1
        playlist = _value(like, "playlist", default=like)
        playlist_id = _playlist_id(playlist)
        if not playlist_id:
            diagnostics["liked_playlists_missing_id"] += 1
            continue
        if playlist_id in playlists_by_id:
            diagnostics["liked_playlists_duplicate_skipped"] += 1
            continue
        playlists_by_id[playlist_id] = _normalize_playlist(playlist, "yandex_music", ingested_at)
        diagnostics["liked_playlists_written"] += 1

    events = [
        {
            "event_id": f"liked_track:{row['track_id']}",
            "event_type": "liked_track",
            "track_id": row["track_id"],
            "event_ts": row.get("liked_at") or ingested_at,
            "source": "yandex_music",
            "ingested_at": ingested_at,
        }
        for row in liked_tracks
    ]
    events.extend(
        {
            "event_id": f"playlist_membership:{row['playlist_id']}:{row['track_id']}",
            "event_type": "playlist_membership",
            "track_id": row["track_id"],
            "playlist_id": row["playlist_id"],
            "event_ts": row.get("added_at") or ingested_at,
            "source": "yandex_music",
            "ingested_at": ingested_at,
        }
        for row in playlist_tracks
    )

    return IngestResult(
        payload={
            "tracks": list(tracks_by_id.values()),
            "artists": list(artists.values()),
            "albums": list(albums.values()),
            "playlists": list(playlists_by_id.values()),
            "playlist_tracks": playlist_tracks,
            "user_library_events": events,
        },
        diagnostics=diagnostics,
    )


def build_payload_from_client(client: Any) -> dict[str, list[dict[str, Any]]]:
    return build_ingest_result_from_client(client).payload


def _client_class() -> Any:
    try:
        from yandex_music import Client
    except ImportError as exc:
        raise YandexMusicIngestError("Install yandex-music to ingest a real account: pip install yandex-music") from exc

    return Client


def _client_version() -> str | None:
    try:
        import yandex_music
    except ImportError:
        return None
    return getattr(yandex_music, "__version__", None)


def client_metadata() -> dict[str, str | None]:
    return {
        "adapter_name": "yamusic_ingest",
        "adapter_version": __version__,
        "client_library": "yandex-music",
        "client_library_version": _client_version(),
    }


def client_from_token(token: str) -> Any:
    try:
        return _call_with_retries("Yandex Music client init", lambda: _client_class()(token).init())
    except Exception as exc:
        raise YandexMusicIngestError(_sanitize_message(str(exc) or exc.__class__.__name__, token)) from exc


def preflight_client(client: Any) -> dict[str, Any]:
    liked_tracks_response = _call_with_retries("client.users_likes_tracks", client.users_likes_tracks)
    liked_shortcuts = getattr(liked_tracks_response, "tracks", []) or []
    liked_albums = _call_with_retries("client.users_likes_albums", client.users_likes_albums) if hasattr(client, "users_likes_albums") else []
    liked_artists = _call_with_retries("client.users_likes_artists", client.users_likes_artists) if hasattr(client, "users_likes_artists") else []
    liked_playlists = _call_with_retries("client.users_likes_playlists", client.users_likes_playlists) if hasattr(client, "users_likes_playlists") else []
    playlists = _call_with_retries("client.users_playlists_list", client.users_playlists_list) or []
    return {
        "source": "yandex_music",
        "status": "ok",
        "liked_shortcut_count": len(liked_shortcuts),
        "liked_album_count": len(liked_albums or []),
        "liked_artist_count": len(liked_artists or []),
        "liked_playlist_count": len(liked_playlists or []),
        "playlist_count": len(playlists),
        **client_metadata(),
    }


def preflight_token(token: str) -> dict[str, Any]:
    client = client_from_token(token)
    try:
        return preflight_client(client)
    except Exception as exc:  # noqa: BLE001 - external client exceptions vary by version.
        raise YandexMusicIngestError(_sanitize_message(str(exc) or exc.__class__.__name__, token)) from exc


def fetch_payload(token: str) -> dict[str, list[dict[str, Any]]]:
    return fetch_ingest_result(token).payload


def fetch_ingest_result(token: str) -> IngestResult:
    client = client_from_token(token)
    try:
        return build_ingest_result_from_client(client)
    except Exception as exc:  # noqa: BLE001 - external client exceptions vary by version.
        raise YandexMusicIngestError(_sanitize_message(str(exc) or exc.__class__.__name__, token)) from exc
