from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from yamusic_ingest.config import load_dotenv
from yamusic_ingest.__main__ import sample_diagnostics, status_payload
from yamusic_ingest.io import file_sha256, remove_file_if_exists, write_json, write_jsonl, write_parquet_if_available
from yamusic_ingest.sample import sample_payload
import yamusic_ingest.yandex_client as yandex_client
from yamusic_ingest.yandex_client import _sanitize_message, build_ingest_result_from_client, build_payload_from_client, client_metadata, preflight_client


ROOT = Path(__file__).resolve().parents[1]


def test_sample_payload_has_required_datasets() -> None:
    payload = sample_payload()
    assert set(payload) == {
        "tracks",
        "artists",
        "albums",
        "playlists",
        "playlist_tracks",
        "user_library_events",
    }
    assert payload["tracks"]
    assert payload["playlist_tracks"]


def test_write_jsonl_round_trips_unicode(tmp_path) -> None:
    rows = [{"track_id": "1", "title": "Тест"}]
    path = tmp_path / "tracks.jsonl"
    assert write_jsonl(path, rows) == 1
    loaded = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert loaded == rows


def test_file_sha256_is_stable_for_written_jsonl(tmp_path) -> None:
    path = tmp_path / "tracks.jsonl"
    write_jsonl(path, [{"track_id": "1", "title": "Тест"}])

    assert file_sha256(path) == file_sha256(path)
    assert len(file_sha256(path)) == 64


def test_write_json_manifest_keeps_counts_without_token_material(tmp_path) -> None:
    manifest = {
        "source": "sample",
        "datasets": {"tracks": {"row_count": 1}},
    }
    path = tmp_path / "_manifest.json"
    write_json(path, manifest)
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert loaded == manifest
    assert "token" not in path.read_text(encoding="utf-8").lower()


def write_contract_fixture(raw_dir: Path, payload: dict[str, list[dict[str, object]]]) -> None:
    raw_dir.mkdir(parents=True, exist_ok=True)
    datasets = {}
    for name, rows in payload.items():
        path = raw_dir / f"{name}.jsonl"
        write_jsonl(path, rows)
        datasets[name] = {"row_count": len(rows), "jsonl_sha256": file_sha256(path)}
    write_json(
        raw_dir / "_manifest.json",
        {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "source": "sample",
            "adapter": client_metadata(),
            "diagnostics": sample_diagnostics(payload),
            "datasets": datasets,
        },
    )


def run_raw_contract(raw_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["STREAMIFY_RAW_DIR"] = str(raw_dir)
    return subprocess.run(
        [sys.executable, "scripts/validate_yamusic_raw_contract.py"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )


def test_raw_contract_accepts_sample_payload(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    write_contract_fixture(raw_dir, sample_payload())

    result = run_raw_contract(raw_dir)

    assert result.returncode == 0, result.stderr
    assert "raw schema contract is valid" in result.stdout


def test_raw_contract_rejects_orphan_playlist_track(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    payload = sample_payload()
    payload["playlist_tracks"][0]["track_id"] = "missing-track"
    write_contract_fixture(raw_dir, payload)

    result = run_raw_contract(raw_dir)

    assert result.returncode == 1
    assert "is not present in tracks.jsonl" in result.stderr


def test_raw_contract_rejects_manifest_diagnostics_mismatch(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    write_contract_fixture(raw_dir, sample_payload())
    manifest_path = raw_dir / "_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["diagnostics"]["playlist_tracks_written"] += 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_raw_contract(raw_dir)

    assert result.returncode == 1
    assert "diagnostics.playlist_tracks_written" in result.stderr


def test_raw_contract_allows_fetch_failure_counters_for_written_fallback_rows(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    write_contract_fixture(raw_dir, sample_payload())
    manifest_path = raw_dir / "_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["diagnostics"]["liked_shortcuts_fetch_failed"] = 1
    manifest["diagnostics"]["playlist_tracks_fetch_failed"] = 1
    manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

    result = run_raw_contract(raw_dir)

    assert result.returncode == 0, result.stderr


def test_raw_contract_rejects_jsonl_checksum_mismatch(tmp_path) -> None:
    raw_dir = tmp_path / "raw"
    write_contract_fixture(raw_dir, sample_payload())
    with (raw_dir / "tracks.jsonl").open("a", encoding="utf-8") as file:
        file.write("\n")

    result = run_raw_contract(raw_dir)

    assert result.returncode == 1
    assert "sha256 mismatch for tracks" in result.stderr


def test_empty_parquet_write_removes_stale_file(tmp_path) -> None:
    path = tmp_path / "tracks.parquet"
    path.write_bytes(b"stale")

    assert write_parquet_if_available(path, []) is False

    assert not path.exists()


def test_remove_file_if_exists_is_idempotent(tmp_path) -> None:
    path = tmp_path / "tracks.parquet"

    remove_file_if_exists(path)
    path.write_bytes(b"stale")
    remove_file_if_exists(path)

    assert not path.exists()


def test_preflight_client_returns_safe_counts() -> None:
    client = FakeClient(liked_tracks=[object(), object()], playlists=[])
    result = preflight_client(client)
    assert result["source"] == "yandex_music"
    assert result["status"] == "ok"
    assert result["liked_shortcut_count"] == 2
    assert result["liked_album_count"] == 0
    assert result["liked_artist_count"] == 0
    assert result["liked_playlist_count"] == 0
    assert result["playlist_count"] == 0
    assert result["adapter_name"] == "yamusic_ingest"
    assert result["adapter_version"]
    assert result["client_library"] == "yandex-music"
    assert "token" not in json.dumps(result).lower()


def test_sanitize_message_redacts_token() -> None:
    assert _sanitize_message("bad token secret-123", "secret-123") == "bad token [redacted-token]"


def test_load_dotenv_reads_export_and_preserves_existing_env(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text(
        "\n".join(
            [
                "# local settings",
                "export YANDEX_MUSIC_TOKEN=from-file",
                "STREAMIFY_RAW_DIR='data/custom/raw'",
                "STREAMIFY_DUCKDB_PATH=\"data/custom.duckdb\"",
            ]
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("YANDEX_MUSIC_TOKEN", "from-shell")
    monkeypatch.delenv("STREAMIFY_RAW_DIR", raising=False)
    monkeypatch.delenv("STREAMIFY_DUCKDB_PATH", raising=False)

    load_dotenv(env_path)

    assert os.environ["YANDEX_MUSIC_TOKEN"] == "from-shell"
    assert os.environ["STREAMIFY_RAW_DIR"] == "data/custom/raw"
    assert os.environ["STREAMIFY_DUCKDB_PATH"] == "data/custom.duckdb"


def test_load_dotenv_preserves_token_special_characters(tmp_path, monkeypatch) -> None:
    env_path = tmp_path / ".env"
    env_path.write_text("YANDEX_MUSIC_TOKEN='ya#token$with=chars'\n", encoding="utf-8")
    monkeypatch.delenv("YANDEX_MUSIC_TOKEN", raising=False)

    load_dotenv(env_path)

    assert os.environ["YANDEX_MUSIC_TOKEN"] == "ya#token$with=chars"


def test_status_payload_does_not_expose_token_material(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    settings = type("SettingsLike", (), {"token": "secret-token", "raw_dir": Path("raw")})()

    payload = status_payload(settings)
    serialized = json.dumps(payload)

    assert payload["token_configured"] is True
    assert "secret-token" not in serialized
    assert payload["next_step"] == "make preflight"
    assert payload["snapshot_path"] == "data/streamify_snapshot.json"
    assert payload["recommendations_dir"] == "data/recommendations"


def test_status_payload_reads_last_manifest_without_api_call(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "_manifest.json").write_text(
        json.dumps({"source": "yandex_music", "generated_at": "2026-06-15T12:00:00+00:00"}),
        encoding="utf-8",
    )
    settings = type("SettingsLike", (), {"token": "secret-token", "raw_dir": raw_dir})()

    payload = status_payload(settings)
    serialized = json.dumps(payload)

    assert payload["last_source"] == "yandex_music"
    assert payload["last_generated_at"] == "2026-06-15T12:00:00+00:00"
    assert payload["manifest_read_error"] is None
    assert payload["next_step"] == "make acceptance-real"
    assert "secret-token" not in serialized


def test_status_payload_reports_broken_manifest_without_failing(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "_manifest.json").write_text("{not-json", encoding="utf-8")
    settings = type("SettingsLike", (), {"token": None, "raw_dir": raw_dir})()

    payload = status_payload(settings)

    assert payload["raw_manifest_exists"] is True
    assert payload["last_source"] is None
    assert payload["manifest_read_error"] == "JSONDecodeError"


def test_token_help_reports_configuration_without_printing_token() -> None:
    env = os.environ.copy()
    env["YANDEX_MUSIC_TOKEN"] = "secret-token-for-test"
    result = subprocess.run(
        [sys.executable, "scripts/yamusic_token_help.py", "--json"],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["token_configured"] is True
    assert payload["supports_token_only_client"] is True
    assert payload["recommended_helper"] == "https://github.com/MarshalX/yandex-music-token"
    assert "secret-token-for-test" not in result.stdout


@dataclass
class FakeLikesResponse:
    tracks: list[object]


@dataclass
class FakeShortcut:
    track: object
    timestamp: str

    def fetch_track(self) -> object:
        return self.track


@dataclass
class FakePlaylistItem:
    track: object
    created_at: str


@dataclass
class FakePlaylist:
    kind: int
    title: str
    track_count: int
    tracks: list[FakePlaylistItem]
    uid: int | None = None
    owner: object | None = None

    def fetch_tracks(self) -> "FakePlaylist":
        return self


@dataclass
class FakeOwner:
    uid: int


class FakeClient:
    def __init__(
        self,
        liked_tracks: list[object],
        playlists: list[FakePlaylist],
        liked_albums: list[object] | None = None,
        liked_artists: list[object] | None = None,
        liked_playlists: list[object] | None = None,
    ) -> None:
        self._liked_tracks = liked_tracks
        self._playlists = playlists
        self._liked_albums = liked_albums or []
        self._liked_artists = liked_artists or []
        self._liked_playlists = liked_playlists or []

    def users_likes_tracks(self) -> FakeLikesResponse:
        return FakeLikesResponse(self._liked_tracks)

    def users_playlists_list(self) -> list[FakePlaylist]:
        return self._playlists

    def users_likes_albums(self) -> list[object]:
        return self._liked_albums

    def users_likes_artists(self) -> list[object]:
        return self._liked_artists

    def users_likes_playlists(self) -> list[object]:
        return self._liked_playlists


class FlakyClient(FakeClient):
    def __init__(self, liked_tracks: list[object], playlists: list[FakePlaylist]) -> None:
        super().__init__(liked_tracks, playlists)
        self.likes_calls = 0
        self.playlist_calls = 0

    def users_likes_tracks(self) -> FakeLikesResponse:
        self.likes_calls += 1
        if self.likes_calls == 1:
            raise RuntimeError("temporary likes failure")
        return super().users_likes_tracks()

    def users_playlists_list(self) -> list[FakePlaylist]:
        self.playlist_calls += 1
        if self.playlist_calls == 1:
            raise RuntimeError("temporary playlists failure")
        return super().users_playlists_list()


class FlakyShortcut(FakeShortcut):
    def __init__(self, track: object, timestamp: str) -> None:
        super().__init__(track, timestamp)
        self.calls = 0

    def fetch_track(self) -> object:
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("temporary track failure")
        return self.track


class AlwaysFailingShortcut(FakeShortcut):
    def fetch_track(self) -> object:
        raise RuntimeError("permanent track failure")


@dataclass
class FakeLikedShortcutOnlyId:
    id: str
    timestamp: str

    def fetch_track(self) -> object:
        raise RuntimeError("liked shortcut hydration failed")


@dataclass
class FakePlaylistReturningTrackList(FakePlaylist):
    fetched_tracks: list[object] | None = None

    def fetch_tracks(self) -> list[object]:
        return self.fetched_tracks or []


@dataclass
class FakePlaylistTrackShortcut:
    id: str
    timestamp: str
    track: object | None = None

    def fetch_track(self) -> object:
        if self.track is None:
            raise RuntimeError("playlist shortcut hydration failed")
        return self.track


def test_build_payload_from_client_normalizes_liked_tracks_playlists_and_timestamps() -> None:
    album = {"id": 101, "title": "Adapter Album", "genre": "indie", "year": 2025}
    artist = {"id": 201, "name": "Adapter Artist"}
    liked_track = {
        "id": "t-1",
        "title": "Liked Track",
        "duration_ms": 123000,
        "albums": [album],
        "artists": [artist],
        "major": {"name": "Adapter Label"},
    }
    playlist_track = {
        "id": "t-2",
        "title": "Playlist Track",
        "durationMs": 234000,
        "albums": [album],
        "artists": [artist],
    }
    client = FakeClient(
        liked_tracks=[FakeShortcut(liked_track, "2026-01-01T10:00:00+00:00")],
        playlists=[
            FakePlaylist(
                kind=77,
                title="Adapter Playlist",
                track_count=1,
                tracks=[FakePlaylistItem(playlist_track, "2026-02-01T11:00:00+00:00")],
            )
        ],
    )

    payload = build_payload_from_client(client)

    assert set(payload) == {
        "tracks",
        "artists",
        "albums",
        "playlists",
        "playlist_tracks",
        "user_library_events",
    }
    assert {track["track_id"] for track in payload["tracks"]} == {"t-1", "t-2"}
    liked = next(track for track in payload["tracks"] if track["track_id"] == "t-1")
    assert liked["liked"] is True
    assert liked["genre"] == "indie"
    assert liked["label"] == "Adapter Label"
    assert payload["albums"] == [
        {
            "album_id": "101",
            "album_title": "Adapter Album",
            "genre": "indie",
            "release_year": 2025,
            "source": "yandex_music",
            "ingested_at": payload["albums"][0]["ingested_at"],
        }
    ]
    assert payload["playlist_tracks"][0]["added_at"] == "2026-02-01T11:00:00+00:00"
    events_by_id = {event["event_id"]: event for event in payload["user_library_events"]}
    assert events_by_id["liked_track:t-1"]["event_ts"] == "2026-01-01T10:00:00+00:00"
    assert events_by_id["playlist_membership:77:t-2"]["event_ts"] == "2026-02-01T11:00:00+00:00"


def test_build_payload_from_client_includes_liked_album_and_artist_metadata() -> None:
    client = FakeClient(
        liked_tracks=[],
        playlists=[],
        liked_albums=[
            {
                "album": {
                    "id": "liked-album-1",
                    "title": "Liked Album",
                    "genre": "ambient",
                    "original_release_year": 2022,
                }
            },
            {"album": {"title": "Missing Id"}},
        ],
        liked_artists=[
            {"artist": {"id": "liked-artist-1", "name": "Liked Artist"}},
            {"artist": {"name": "Missing Id"}},
        ],
    )

    result = build_ingest_result_from_client(client)

    assert result.payload["albums"] == [
        {
            "album_id": "liked-album-1",
            "album_title": "Liked Album",
            "genre": "ambient",
            "release_year": 2022,
            "source": "yandex_music",
            "ingested_at": result.payload["albums"][0]["ingested_at"],
        }
    ]
    assert result.payload["artists"] == [
        {
            "artist_id": "liked-artist-1",
            "artist_name": "Liked Artist",
            "source": "yandex_music",
            "ingested_at": result.payload["artists"][0]["ingested_at"],
        }
    ]
    assert result.diagnostics["liked_albums_seen"] == 2
    assert result.diagnostics["liked_albums_written"] == 1
    assert result.diagnostics["liked_albums_missing_id"] == 1
    assert result.diagnostics["liked_artists_seen"] == 2
    assert result.diagnostics["liked_artists_written"] == 1
    assert result.diagnostics["liked_artists_missing_id"] == 1


def test_build_payload_from_client_includes_liked_playlist_metadata_and_dedupes_owned_playlists() -> None:
    owned_playlist = FakePlaylist(
        uid=100,
        kind=10,
        title="Owned Playlist",
        track_count=0,
        tracks=[],
    )
    liked_playlist = {
        "playlist": FakePlaylist(
            uid=200,
            kind=20,
            title="Liked Playlist",
            track_count=12,
            tracks=[],
        )
    }
    duplicate_liked_playlist = {"playlist": owned_playlist}
    missing_id_liked_playlist = {"playlist": {"title": "Missing Id"}}
    client = FakeClient(
        liked_tracks=[],
        playlists=[owned_playlist],
        liked_playlists=[liked_playlist, duplicate_liked_playlist, missing_id_liked_playlist],
    )

    result = build_ingest_result_from_client(client)

    assert [row["playlist_id"] for row in result.payload["playlists"]] == ["100:10", "200:20"]
    assert result.payload["playlists"][1]["playlist_title"] == "Liked Playlist"
    assert result.payload["playlists"][1]["track_count"] == 12
    assert result.diagnostics["playlists_seen"] == 1
    assert result.diagnostics["playlists_written"] == 1
    assert result.diagnostics["liked_playlists_seen"] == 3
    assert result.diagnostics["liked_playlists_written"] == 1
    assert result.diagnostics["liked_playlists_missing_id"] == 1
    assert result.diagnostics["liked_playlists_duplicate_skipped"] == 1


def test_build_payload_uses_playlist_owner_uid_when_playlist_uid_is_missing() -> None:
    track = {
        "id": "owner-playlist-track",
        "title": "Owner Playlist Track",
        "duration_ms": 123000,
        "albums": [],
        "artists": [],
    }
    playlist = FakePlaylist(
        uid=None,
        owner=FakeOwner(uid=4242),
        kind=55,
        title="Owner Scoped Playlist",
        track_count=1,
        tracks=[FakePlaylistItem(track, "2026-06-04T10:00:00+00:00")],
    )
    client = FakeClient(liked_tracks=[], playlists=[playlist])

    payload = build_payload_from_client(client)

    assert payload["playlists"][0]["playlist_id"] == "4242:55"
    assert payload["playlist_tracks"][0]["playlist_id"] == "4242:55"
    assert payload["user_library_events"][0]["event_id"] == "playlist_membership:4242:55:owner-playlist-track"


def test_preflight_client_retries_transient_top_level_failures(monkeypatch) -> None:
    monkeypatch.setattr(yandex_client, "sleep", lambda _seconds: None)
    client = FlakyClient(liked_tracks=[object()], playlists=[])

    result = preflight_client(client)

    assert result["liked_shortcut_count"] == 1
    assert result["playlist_count"] == 0
    assert client.likes_calls == 2
    assert client.playlist_calls == 2


def test_build_payload_retries_transient_track_fetch(monkeypatch) -> None:
    monkeypatch.setattr(yandex_client, "sleep", lambda _seconds: None)
    track = {
        "id": "flaky-track",
        "title": "Retry Track",
        "duration_ms": 123000,
        "albums": [],
        "artists": [{"id": "retry-artist", "name": "Retry Artist"}],
    }
    shortcut = FlakyShortcut(track, "2026-04-01T10:00:00+00:00")
    client = FakeClient(liked_tracks=[shortcut], playlists=[])

    payload = build_payload_from_client(client)

    assert shortcut.calls == 2
    assert [row["track_id"] for row in payload["tracks"]] == ["flaky-track"]
    assert payload["user_library_events"][0]["event_id"] == "liked_track:flaky-track"


def test_build_ingest_result_reports_safe_skip_diagnostics(monkeypatch) -> None:
    monkeypatch.setattr(yandex_client, "sleep", lambda _seconds: None)
    good_track = {
        "id": "good-track",
        "title": "Good Track",
        "duration_ms": 123000,
        "albums": [],
        "artists": [{"id": "good-artist", "name": "Good Artist"}],
    }
    missing_id_track = {"title": "No Id"}
    failed_shortcut = AlwaysFailingShortcut(good_track, "2026-05-01T10:00:00+00:00")
    playlist = FakePlaylist(
        kind=88,
        title="Diagnostics Playlist",
        track_count=2,
        tracks=[
            FakePlaylistItem(good_track, "2026-05-02T10:00:00+00:00"),
            FakePlaylistItem(missing_id_track, "2026-05-03T10:00:00+00:00"),
        ],
    )
    client = FakeClient(
        liked_tracks=[
            FakeShortcut(good_track, "2026-05-01T10:00:00+00:00"),
            FakeShortcut(missing_id_track, "2026-05-01T11:00:00+00:00"),
            failed_shortcut,
        ],
        playlists=[{"title": "No Stable Id"}, playlist],
    )

    result = build_ingest_result_from_client(client)

    assert result.diagnostics["liked_shortcuts_seen"] == 3
    assert result.diagnostics["liked_tracks_written"] == 1
    assert result.diagnostics["liked_shortcuts_fetch_failed"] == 1
    assert result.diagnostics["liked_shortcuts_missing_track_id"] == 1
    assert result.diagnostics["liked_tracks_duplicate_skipped"] == 1
    assert result.diagnostics["playlists_seen"] == 2
    assert result.diagnostics["playlists_written"] == 1
    assert result.diagnostics["playlists_missing_id"] == 1
    assert result.diagnostics["playlist_tracks_seen"] == 2
    assert result.diagnostics["playlist_tracks_written"] == 1
    assert result.diagnostics["playlist_tracks_missing_track_id"] == 1


def test_build_ingest_result_keeps_liked_shortcut_id_when_hydration_fails(monkeypatch) -> None:
    monkeypatch.setattr(yandex_client, "sleep", lambda _seconds: None)
    shortcut = FakeLikedShortcutOnlyId(id="shortcut-only-track", timestamp="2026-06-03T09:00:00+00:00")
    client = FakeClient(liked_tracks=[shortcut], playlists=[])

    result = build_ingest_result_from_client(client)

    assert result.payload["tracks"] == [
        {
            "track_id": "shortcut-only-track",
            "title": "",
            "duration_ms": None,
            "album_id": None,
            "album_title": None,
            "genre": None,
            "release_year": None,
            "label": None,
            "artist_ids": [],
            "artist_names": [],
            "liked": True,
            "source": "yandex_music",
            "ingested_at": result.payload["tracks"][0]["ingested_at"],
            "liked_at": "2026-06-03T09:00:00+00:00",
        }
    ]
    assert result.payload["user_library_events"][0]["event_id"] == "liked_track:shortcut-only-track"
    assert result.payload["user_library_events"][0]["event_ts"] == "2026-06-03T09:00:00+00:00"
    assert result.diagnostics["liked_shortcuts_seen"] == 1
    assert result.diagnostics["liked_tracks_written"] == 1
    assert result.diagnostics["liked_shortcuts_fetch_failed"] == 1
    assert result.diagnostics["liked_shortcuts_missing_track_id"] == 0


def test_build_ingest_result_deduplicates_repeated_library_rows() -> None:
    track = {
        "id": "dup-track",
        "title": "Duplicate Track",
        "duration_ms": 123000,
        "albums": [],
        "artists": [{"id": "dup-artist", "name": "Duplicate Artist"}],
    }
    playlist = FakePlaylist(
        kind=99,
        title="Duplicate Playlist",
        track_count=2,
        tracks=[
            FakePlaylistItem(track, "2026-06-01T10:00:00+00:00"),
            FakePlaylistItem(track, "2026-06-01T10:01:00+00:00"),
        ],
    )
    client = FakeClient(
        liked_tracks=[
            FakeShortcut(track, "2026-06-01T09:00:00+00:00"),
            FakeShortcut(track, "2026-06-01T09:01:00+00:00"),
        ],
        playlists=[playlist],
    )

    result = build_ingest_result_from_client(client)

    assert [row["track_id"] for row in result.payload["tracks"]] == ["dup-track"]
    assert result.payload["playlist_tracks"] == [
        {
            "playlist_id": "99",
            "track_id": "dup-track",
            "position": 1,
            "added_at": "2026-06-01T10:00:00+00:00",
            "source": "yandex_music",
            "ingested_at": result.payload["playlist_tracks"][0]["ingested_at"],
        }
    ]
    assert {event["event_id"] for event in result.payload["user_library_events"]} == {
        "liked_track:dup-track",
        "playlist_membership:99:dup-track",
    }
    assert result.diagnostics["liked_shortcuts_seen"] == 2
    assert result.diagnostics["liked_tracks_written"] == 1
    assert result.diagnostics["liked_tracks_duplicate_skipped"] == 1
    assert result.diagnostics["playlist_tracks_seen"] == 2
    assert result.diagnostics["playlist_tracks_written"] == 1
    assert result.diagnostics["playlist_tracks_duplicate_skipped"] == 1


def test_build_ingest_result_accepts_playlist_fetch_tracks_list_and_hydrates_shortcuts(monkeypatch) -> None:
    monkeypatch.setattr(yandex_client, "sleep", lambda _seconds: None)
    full_track = {
        "id": "list-track-full",
        "title": "List Track Full",
        "duration_ms": 210000,
        "albums": [{"id": "list-album", "title": "List Album", "genre": "jazz"}],
        "artists": [{"id": "list-artist", "name": "List Artist"}],
    }
    shortcut_only = FakePlaylistTrackShortcut(id="list-track-shortcut", timestamp="2026-06-02T10:00:00+00:00")
    playlist = FakePlaylistReturningTrackList(
        kind=101,
        title="Fetched List Playlist",
        track_count=2,
        tracks=[],
        fetched_tracks=[
            FakePlaylistTrackShortcut(id="list-track-full", timestamp="2026-06-02T09:00:00+00:00", track=full_track),
            shortcut_only,
        ],
    )
    client = FakeClient(liked_tracks=[], playlists=[playlist])

    result = build_ingest_result_from_client(client)

    tracks_by_id = {row["track_id"]: row for row in result.payload["tracks"]}
    assert set(tracks_by_id) == {"list-track-full", "list-track-shortcut"}
    assert tracks_by_id["list-track-full"]["artist_names"] == ["List Artist"]
    assert tracks_by_id["list-track-shortcut"]["title"] == ""
    assert [row["track_id"] for row in result.payload["playlist_tracks"]] == ["list-track-full", "list-track-shortcut"]
    assert result.diagnostics["playlist_tracks_seen"] == 2
    assert result.diagnostics["playlist_tracks_written"] == 2
    assert result.diagnostics["playlist_tracks_fetch_failed"] == 1
    assert result.diagnostics["playlist_tracks_missing_track_id"] == 0


def test_build_payload_from_client_handles_empty_account() -> None:
    payload = build_payload_from_client(FakeClient(liked_tracks=[], playlists=[]))
    assert payload == {
        "tracks": [],
        "artists": [],
        "albums": [],
        "playlists": [],
        "playlist_tracks": [],
        "user_library_events": [],
    }


def test_build_payload_from_yandex_music_model_instances_and_skips_missing_track_ids() -> None:
    from yandex_music import Album, Artist, Playlist, Track

    artist = Artist(id=301, name="Model Artist", genres=["post-rock"])
    album = Album(
        id=401,
        title="Model Album",
        labels=["Model Label"],
        original_release_year=2024,
    )
    liked_track = Track(id="model-1", title="Model Track", artists=[artist], albums=[album], duration_ms=210000)
    playlist_track = Track(id="model-2", title="Duration Seconds", artists=[artist], albums=[album])
    playlist_track.duration = 187
    no_id_track = {"title": "No Id"}

    client = FakeClient(
        liked_tracks=[FakeShortcut(liked_track, "2026-03-01T10:00:00+00:00"), FakeShortcut(no_id_track, "2026-03-02T10:00:00+00:00")],
        playlists=[
            Playlist(
                uid=500,
                kind=600,
                title="Model Playlist",
                track_count=2,
                tracks=[FakePlaylistItem(playlist_track, "2026-03-03T10:00:00+00:00"), FakePlaylistItem(no_id_track, "2026-03-04T10:00:00+00:00")],
                owner=None,
                cover=None,
                made_for=None,
                play_counter=None,
                playlist_absence=None,
            )
        ],
    )

    payload = build_payload_from_client(client)

    assert {track["track_id"] for track in payload["tracks"]} == {"model-1", "model-2"}
    liked = next(track for track in payload["tracks"] if track["track_id"] == "model-1")
    duration_fallback = next(track for track in payload["tracks"] if track["track_id"] == "model-2")
    assert liked["genre"] == "post-rock"
    assert liked["release_year"] == 2024
    assert liked["label"] == "Model Label"
    assert duration_fallback["duration_ms"] == 187000
    assert payload["playlists"][0]["playlist_id"] == "500:600"
    assert len(payload["playlist_tracks"]) == 1
    assert len(payload["user_library_events"]) == 2
