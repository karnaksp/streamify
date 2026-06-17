#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


ROOT = Path(__file__).resolve().parents[1]
COMPOSE_FILE = ROOT / "docker-compose.local.yml"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def run_compose(args: list[str], env: dict[str, str], check: bool = True) -> subprocess.CompletedProcess[str]:
    command = ["docker", "compose", "-f", str(COMPOSE_FILE), "--profile", "local", *args]
    return subprocess.run(command, cwd=ROOT, env=env, text=True, capture_output=True, check=check)


def wait_for_http(url: str, env: dict[str, str], timeout_seconds: int = 120) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        status = run_compose(["ps", "--format", "json"], env, check=False)
        if status.returncode != 0:
            last_error = RuntimeError(status.stderr.strip() or status.stdout.strip())
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except (URLError, TimeoutError, OSError) as error:
            last_error = error
        time.sleep(1)
    raise RuntimeError(f"compose dashboard did not return HTTP 200 at {url}: {last_error}")


def assert_no_runtime_failures(log_output: str) -> None:
    failure_markers = [
        "Traceback",
        "ModuleNotFoundError",
        "Local DuckDB database is missing",
        "The local marts are not ready yet",
    ]
    for marker in failure_markers:
        if marker in log_output:
            raise RuntimeError(f"compose dashboard emitted failure marker: {marker}")


def run_host_check(args: list[str], env: dict[str, str]) -> None:
    result = subprocess.run(
        [sys.executable, *args],
        cwd=ROOT,
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        output = result.stdout[-4000:] + result.stderr[-4000:]
        raise RuntimeError(f"host validation failed for {' '.join(args)}:\n{output}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Smoke test the local Docker Compose product profile.")
    parser.add_argument(
        "--use-env-token",
        action="store_true",
        help="Use YANDEX_MUSIC_TOKEN from the environment and require real-account readiness.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    port = free_port()
    url = f"http://127.0.0.1:{port}"
    env = os.environ.copy()
    env["STREAMIFY_DASHBOARD_PORT"] = str(port)
    if args.use_env_token:
        if not env.get("YANDEX_MUSIC_TOKEN"):
            print("ERROR: --use-env-token requires YANDEX_MUSIC_TOKEN in the environment or .env.", file=sys.stderr)
            return 2
        readiness_args = ["scripts/audit_yamusic_readiness.py", "--require-real"]
        mode = "Yandex Music metadata"
    else:
        # Default compose smoke must be deterministic and must not call a real account.
        env["YANDEX_MUSIC_TOKEN"] = ""
        readiness_args = ["scripts/audit_yamusic_readiness.py"]
        mode = "sample metadata"

    try:
        run_compose(["up", "--build", "-d", "dashboard"], env)
        wait_for_http(url, env)
        time.sleep(1)
        logs = run_compose(["logs", "--no-color", "--tail", "300"], env, check=False)
        assert_no_runtime_failures(logs.stdout + logs.stderr)
        for check_args in [
            ["scripts/validate_yamusic_raw_contract.py"],
            readiness_args,
            ["scripts/smoke_product_answers.py"],
            ["scripts/smoke_dashboard_content.py"],
        ]:
            run_host_check(check_args, env)
    except (subprocess.CalledProcessError, RuntimeError) as error:
        logs = run_compose(["logs", "--no-color", "--tail", "200"], env, check=False)
        print(f"ERROR: {error}", file=sys.stderr)
        if isinstance(error, subprocess.CalledProcessError):
            print(error.stdout[-4000:], file=sys.stderr)
            print(error.stderr[-4000:], file=sys.stderr)
        print(logs.stdout[-8000:], file=sys.stderr)
        print(logs.stderr[-4000:], file=sys.stderr)
        return 1
    finally:
        run_compose(["down", "--remove-orphans"], env, check=False)

    print(f"OK: docker compose local profile returned HTTP 200 at {url} and produced valid local product artifacts from {mode}.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
