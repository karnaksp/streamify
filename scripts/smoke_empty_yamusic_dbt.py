#!/usr/bin/env python3
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from hashlib import sha256
from pathlib import Path

import duckdb


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw" / "yamusic_empty_smoke"
DUCKDB_PATH = ROOT / "data" / "streamify_empty_smoke.duckdb"
DATASETS = [
    "tracks",
    "artists",
    "albums",
    "playlists",
    "playlist_tracks",
    "user_library_events",
]


def file_sha256(path: Path) -> str:
    digest = sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def cleanup() -> None:
    shutil.rmtree(RAW_DIR, ignore_errors=True)
    for path in [DUCKDB_PATH, DUCKDB_PATH.with_suffix(".duckdb.wal")]:
        path.unlink(missing_ok=True)


def dbt_command() -> list[str]:
    candidate = Path(sys.executable).resolve().parent / "dbt"
    if candidate.exists():
        return [str(candidate)]
    resolved = shutil.which("dbt")
    if resolved:
        return [resolved]
    module_probe = subprocess.run(
        [sys.executable, "-m", "dbt.cli.main", "--version"],
        text=True,
        capture_output=True,
        check=False,
    )
    if module_probe.returncode == 0:
        return [sys.executable, "-m", "dbt.cli.main"]
    raise RuntimeError("dbt executable was not found")


def main() -> int:
    cleanup()
    try:
        RAW_DIR.mkdir(parents=True, exist_ok=True)
        for dataset in DATASETS:
            (RAW_DIR / f"{dataset}.jsonl").write_text("", encoding="utf-8")
        manifest = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "source": "yandex_music",
            "raw_dir": str(RAW_DIR),
            "json_only": True,
            "adapter": {
                "adapter_name": "yamusic_ingest",
                "adapter_version": "0.1.0",
                "client_library": "yandex-music",
                "client_library_version": None,
            },
            "diagnostics": {
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
            },
            "datasets": {
                dataset: {
                    "jsonl_path": str(RAW_DIR / f"{dataset}.jsonl"),
                    "row_count": 0,
                    "jsonl_sha256": file_sha256(RAW_DIR / f"{dataset}.jsonl"),
                    "parquet_written": False,
                }
                for dataset in DATASETS
            },
        }
        (RAW_DIR / "_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        env = os.environ.copy()
        env["STREAMIFY_RAW_DIR"] = "data/raw/yamusic_empty_smoke"
        env["STREAMIFY_DUCKDB_PATH"] = "data/streamify_empty_smoke.duckdb"

        deps_command = [
            *dbt_command(),
            "deps",
        ]
        deps_result = subprocess.run(deps_command, cwd=ROOT / "dbt", env=env, text=True, capture_output=True, check=False)
        if deps_result.returncode != 0:
            print(deps_result.stdout[-4000:], file=sys.stderr)
            print(deps_result.stderr[-4000:], file=sys.stderr)
            return deps_result.returncode

        command = [
            *dbt_command(),
            "build",
            "--profiles-dir",
            ".",
            "--target",
            "local",
            "--select",
            "yamusic",
            "--no-partial-parse",
        ]
        result = subprocess.run(command, cwd=ROOT / "dbt", env=env, text=True, capture_output=True, check=False)

        if result.returncode != 0:
            print(result.stdout[-4000:], file=sys.stderr)
            print(result.stderr[-4000:], file=sys.stderr)
            return result.returncode

        with duckdb.connect(str(DUCKDB_PATH), read_only=True) as conn:
            profile = conn.execute(
                """
                select total_tracks, liked_tracks, playlists, stale_ingestion_flag
                from yamusic_library_profile
                """
            ).fetchone()
    finally:
        cleanup()

    if profile != (0, 0, 0, 1):
        print(f"ERROR: unexpected empty-profile values: {profile!r}", file=sys.stderr)
        return 1

    print("OK: empty Yandex Music raw datasets build with local dbt target.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
