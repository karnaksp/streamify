#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
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


def main() -> int:
    if not DATA_DIR.exists():
        print("OK: data directory is absent; no audio artifacts found.")
        return 0

    audio_files = [
        path.relative_to(ROOT)
        for path in DATA_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTENSIONS
    ]
    if audio_files:
        print("ERROR: Streamify local mode must not store audio files.", file=sys.stderr)
        for path in audio_files[:25]:
            print(f"- {path}", file=sys.stderr)
        if len(audio_files) > 25:
            print(f"... and {len(audio_files) - 25} more", file=sys.stderr)
        return 1

    print("OK: no audio artifacts found under data/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
