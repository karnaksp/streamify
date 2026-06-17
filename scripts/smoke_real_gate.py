#!/usr/bin/env python3
from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    command = [
        sys.executable,
        "scripts/audit_yamusic_readiness.py",
        "--require-real",
    ]
    result = subprocess.run(command, cwd=ROOT, text=True, capture_output=True, check=False)
    output = result.stdout + result.stderr
    if result.returncode == 0:
        print("ERROR: sample metadata unexpectedly passed real-account readiness.", file=sys.stderr)
        print(output[-4000:], file=sys.stderr)
        return 1
    required = [
        "Real-account readiness requires",
        "source=yandex_music",
        "YANDEX_MUSIC_TOKEN",
    ]
    missing = [marker for marker in required if marker not in output]
    if missing:
        print(f"ERROR: real-account gate failure message is missing markers: {missing}", file=sys.stderr)
        print(output[-4000:], file=sys.stderr)
        return 1
    print("OK: sample metadata is rejected by the real-account readiness gate.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
