#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
AUDIO_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".alac",
    ".flac",
    ".m4a",
    ".mp3",
    ".ogg",
    ".opus",
    ".wav",
    ".wma",
}
FORBIDDEN_TRACKED_PATHS = {
    ".env",
    "data/raw/yamusic",
    "data/streamify.duckdb",
    "data/streamify.duckdb.wal",
}
REQUIRED_GITIGNORE_MARKERS = [
    ".env",
    "data/",
    "*.duckdb",
    "*.duckdb.wal",
]


def git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def main() -> int:
    tracked_files = git_ls_files()
    errors: list[str] = []

    for path in tracked_files:
        normalized = path.strip("/")
        if normalized in FORBIDDEN_TRACKED_PATHS or any(
            normalized.startswith(f"{forbidden}/") for forbidden in FORBIDDEN_TRACKED_PATHS
        ):
            errors.append(f"local sensitive artifact is tracked: {path}")
        if normalized.startswith("data/") and Path(normalized).suffix.lower() in AUDIO_EXTENSIONS:
            errors.append(f"audio file is tracked under data/: {path}")

    gitignore = (ROOT / ".gitignore").read_text(encoding="utf-8")
    for marker in REQUIRED_GITIGNORE_MARKERS:
        if marker not in gitignore:
            errors.append(f".gitignore must contain {marker!r}")

    if errors:
        print("ERROR: local product sensitive-artifact guard failed.", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1

    print("OK: no local Yandex Music secrets, raw data, DuckDB files, or audio artifacts are tracked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
