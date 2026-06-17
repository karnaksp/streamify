#!/usr/bin/env python3
from __future__ import annotations

import os
import shutil
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
DUCKDB_PATH = ROOT / os.getenv("STREAMIFY_DUCKDB_PATH", "data/streamify.duckdb")


def streamlit_executable() -> Path:
    candidate = Path(sys.executable).parent / "streamlit"
    if candidate.exists():
        return candidate
    resolved = shutil.which("streamlit")
    if resolved:
        return Path(resolved)
    raise RuntimeError("streamlit executable was not found")


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_for_http(url: str, process: subprocess.Popen[str], timeout_seconds: int = 20) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(f"dashboard process exited early with code {process.returncode}")
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError) as error:
            last_error = error
        time.sleep(0.5)
    raise RuntimeError(f"dashboard did not return HTTP 200 at {url}: {last_error}")


def main() -> int:
    if not DUCKDB_PATH.exists():
        print(f"ERROR: local DuckDB database is missing: {DUCKDB_PATH}", file=sys.stderr)
        print("Run `make acceptance-local` before dashboard smoke.", file=sys.stderr)
        return 1

    port = free_port()
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["STREAMIFY_DUCKDB_PATH"] = str(DUCKDB_PATH)
    env.setdefault("STREAMLIT_BROWSER_GATHER_USAGE_STATS", "false")

    command = [
        str(streamlit_executable()),
        "run",
        "dashboard/app.py",
        "--server.address=127.0.0.1",
        f"--server.port={port}",
        "--server.headless=true",
    ]
    process = subprocess.Popen(
        command,
        cwd=ROOT,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_for_http(url, process)
        time.sleep(1)
    finally:
        process.terminate()
        try:
            output, _ = process.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            output, _ = process.communicate(timeout=5)

    if process.returncode not in {0, -15, None}:
        print(output[-4000:], file=sys.stderr)
        return int(process.returncode)

    failure_markers = ["Traceback", "ModuleNotFoundError", "Local DuckDB database is missing"]
    for marker in failure_markers:
        if marker in output:
            print(output[-4000:], file=sys.stderr)
            print(f"ERROR: dashboard emitted failure marker: {marker}", file=sys.stderr)
            return 1

    print(f"OK: dashboard returned HTTP 200 at {url}.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except RuntimeError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
