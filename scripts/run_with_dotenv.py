#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Load Streamify .env once, then exec a command without Make parsing secrets."
    )
    parser.add_argument("--cwd", default=str(ROOT), help="Working directory for the command.")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.command and args.command[0] == "--":
        args.command = args.command[1:]
    return args


def main() -> int:
    args = parse_args()
    if not args.command:
        print("ERROR: command is required after --", file=sys.stderr)
        return 2

    load_dotenv(ROOT / ".env")
    cwd = Path(args.cwd)
    if not cwd.is_absolute():
        cwd = ROOT / cwd
    os.chdir(cwd)
    os.execvpe(args.command[0], args.command, os.environ)
    return 127


if __name__ == "__main__":
    raise SystemExit(main())
