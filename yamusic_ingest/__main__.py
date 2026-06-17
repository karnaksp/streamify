from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from datetime import UTC, datetime

from yamusic_ingest.config import Settings
from yamusic_ingest.io import file_sha256, remove_file_if_exists, write_json, write_jsonl, write_parquet_if_available
from yamusic_ingest.sample import sample_payload
from yamusic_ingest.yandex_client import YandexMusicIngestError, client_metadata, fetch_ingest_result, preflight_token


DIAGNOSTIC_FIELDS = [
    "liked_shortcuts_seen",
    "liked_tracks_written",
    "liked_shortcuts_fetch_failed",
    "liked_shortcuts_missing_track_id",
    "liked_tracks_duplicate_skipped",
    "liked_albums_seen",
    "liked_albums_written",
    "liked_albums_missing_id",
    "liked_albums_duplicate_skipped",
    "liked_artists_seen",
    "liked_artists_written",
    "liked_artists_missing_id",
    "liked_artists_duplicate_skipped",
    "liked_playlists_seen",
    "liked_playlists_written",
    "liked_playlists_missing_id",
    "liked_playlists_duplicate_skipped",
    "playlists_seen",
    "playlists_written",
    "playlists_missing_id",
    "playlist_fetch_fallbacks",
    "playlist_tracks_seen",
    "playlist_tracks_written",
    "playlist_tracks_fetch_failed",
    "playlist_tracks_missing_track_id",
    "playlist_tracks_duplicate_skipped",
]


def sample_diagnostics(payload: dict[str, list[dict[str, object]]]) -> dict[str, int]:
    return {
        "liked_shortcuts_seen": sum(1 for row in payload["tracks"] if row.get("liked")),
        "liked_tracks_written": sum(1 for row in payload["tracks"] if row.get("liked")),
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
        "playlists_seen": len(payload["playlists"]),
        "playlists_written": len(payload["playlists"]),
        "playlists_missing_id": 0,
        "playlist_fetch_fallbacks": 0,
        "playlist_tracks_seen": len(payload["playlist_tracks"]),
        "playlist_tracks_written": len(payload["playlist_tracks"]),
        "playlist_tracks_fetch_failed": 0,
        "playlist_tracks_missing_track_id": 0,
        "playlist_tracks_duplicate_skipped": 0,
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ingest Yandex Music metadata for local Streamify analytics.")
    parser.add_argument("--sample", action="store_true", help="Write deterministic sample data instead of calling Yandex Music.")
    parser.add_argument("--json-only", action="store_true", help="Skip optional Parquet output.")
    parser.add_argument("--preflight", action="store_true", help="Check real Yandex Music token access without writing raw data.")
    parser.add_argument("--status", action="store_true", help="Print local configuration status without calling Yandex Music or writing data.")
    return parser.parse_args()


def status_payload(settings: Settings) -> dict[str, object]:
    duckdb_path = Path(os.getenv("STREAMIFY_DUCKDB_PATH", "data/streamify.duckdb"))
    report_path = Path(os.getenv("STREAMIFY_REPORT_PATH", "data/streamify_summary.md"))
    snapshot_path = Path(os.getenv("STREAMIFY_SNAPSHOT_PATH", "data/streamify_snapshot.json"))
    recommendations_dir = Path(os.getenv("STREAMIFY_RECOMMENDATIONS_DIR", "data/recommendations"))
    raw_manifest = settings.raw_dir / "_manifest.json"
    manifest_source = None
    manifest_generated_at = None
    manifest_read_error = None
    if raw_manifest.exists():
        try:
            manifest = json.loads(raw_manifest.read_text(encoding="utf-8"))
            manifest_source = manifest.get("source")
            manifest_generated_at = manifest.get("generated_at")
        except (OSError, json.JSONDecodeError) as exc:
            manifest_read_error = exc.__class__.__name__
    if settings.token:
        next_step = "make acceptance-real" if manifest_source == "yandex_music" else "make preflight"
    else:
        next_step = "set YANDEX_MUSIC_TOKEN in .env or run make ingest-sample"
    return {
        "env_file_present": Path(".env").exists(),
        "token_configured": bool(settings.token),
        "raw_dir": str(settings.raw_dir),
        "raw_manifest_exists": raw_manifest.exists(),
        "last_source": manifest_source,
        "last_generated_at": manifest_generated_at,
        "manifest_read_error": manifest_read_error,
        "duckdb_path": str(duckdb_path),
        "duckdb_exists": duckdb_path.exists(),
        "report_path": str(report_path),
        "report_exists": report_path.exists(),
        "snapshot_path": str(snapshot_path),
        "snapshot_exists": snapshot_path.exists(),
        "recommendations_dir": str(recommendations_dir),
        "recommendations_exists": recommendations_dir.exists(),
        "next_step": next_step,
    }


def main() -> int:
    args = parse_args()
    settings = Settings.from_env(sample=args.sample)

    if args.status:
        if args.sample:
            print("--status reports local configuration; do not combine it with --sample.", file=sys.stderr)
            return 2
        print(json.dumps(status_payload(settings), ensure_ascii=False, indent=2, sort_keys=True))
        return 0

    settings.raw_dir.mkdir(parents=True, exist_ok=True)

    if args.preflight:
        if args.sample:
            print("--preflight checks a real Yandex Music token; do not combine it with --sample.", file=sys.stderr)
            return 2
        if not settings.token:
            print("YANDEX_MUSIC_TOKEN is not set. Add it to .env before running --preflight.", file=sys.stderr)
            return 2
        try:
            print(json.dumps(preflight_token(settings.token), ensure_ascii=False, indent=2, sort_keys=True))
        except YandexMusicIngestError as exc:
            print(f"Yandex Music preflight failed: {exc}", file=sys.stderr)
            return 1
        return 0

    source = "sample" if args.sample else "yandex_music"
    if args.sample:
        payload = sample_payload()
        diagnostics = sample_diagnostics(payload)
    else:
        if not settings.token:
            print("YANDEX_MUSIC_TOKEN is not set. Use --sample for a local demo or add the token to .env.", file=sys.stderr)
            return 2
        try:
            result = fetch_ingest_result(settings.token)
            payload = result.payload
            diagnostics = result.diagnostics
        except YandexMusicIngestError as exc:
            print(f"Yandex Music ingestion failed: {exc}", file=sys.stderr)
            return 1

    diagnostics = {field: int(diagnostics.get(field, 0)) for field in DIAGNOSTIC_FIELDS}

    manifest = {
        "generated_at": datetime.now(UTC).isoformat(),
        "source": source,
        "raw_dir": str(settings.raw_dir),
        "json_only": args.json_only,
        "adapter": client_metadata(),
        "diagnostics": diagnostics,
        "datasets": {},
    }
    for name, rows in payload.items():
        jsonl_path = settings.raw_dir / f"{name}.jsonl"
        parquet_path = settings.raw_dir / f"{name}.parquet"
        count = write_jsonl(jsonl_path, rows)
        parquet_written = False
        if not args.json_only:
            parquet_written = write_parquet_if_available(parquet_path, rows)
        else:
            remove_file_if_exists(parquet_path)
        manifest["datasets"][name] = {
            "jsonl_path": str(jsonl_path),
            "row_count": count,
            "jsonl_sha256": file_sha256(jsonl_path),
            "parquet_written": parquet_written,
        }
        suffix = " + parquet" if parquet_written else ""
        print(f"wrote {count:>5} rows to {jsonl_path}{suffix}")

    write_json(settings.raw_dir / "_manifest.json", manifest)
    print(f"wrote manifest to {settings.raw_dir / '_manifest.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
