#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from streamlit.testing.v1 import AppTest

from yamusic_ingest.config import load_dotenv

load_dotenv(ROOT / ".env")
DUCKDB_PATH = ROOT / os.getenv("STREAMIFY_DUCKDB_PATH", "data/streamify.duckdb")


def fail(message: str) -> None:
    raise AssertionError(message)


def values(elements: object) -> list[str]:
    return [str(getattr(element, "value", "")) for element in elements]


def labels(elements: object) -> list[str]:
    return [str(getattr(element, "label", "")) for element in elements]


def require_contains(actual: list[str], expected: list[str], label: str) -> None:
    missing = [value for value in expected if value not in actual]
    if missing:
        fail(f"dashboard {label} missing expected values: {missing}; actual={actual}")


def main() -> int:
    if not DUCKDB_PATH.exists():
        fail(f"Local DuckDB database is missing: {DUCKDB_PATH}. Run make acceptance-local first.")

    os.environ["STREAMIFY_DUCKDB_PATH"] = str(DUCKDB_PATH)
    app = AppTest.from_file(ROOT / "dashboard" / "app.py", default_timeout=10)
    app.run()

    if app.error:
        fail(f"dashboard emitted st.error elements: {values(app.error)}")
    if app.exception:
        fail(f"dashboard emitted st.exception elements: {values(app.exception)}")

    require_contains(values(app.title), ["Streamify Self-Analytics"], "title")
    require_contains(
        values(app.caption),
        ["Local Yandex Music metadata analytics. Audio is not downloaded or stored."],
        "caption",
    )
    require_contains(
        labels(app.metric),
        [
            "Tracks",
            "Liked",
            "Artists",
            "Playlists",
            "Hours",
            "Source",
            "Raw tracks",
            "Known genres",
            "Active months",
            "Underrated tracks",
            "Underrated playlists",
            "Top artist concentration",
        ],
        "metrics",
    )
    require_contains(
        labels(app.tabs),
        ["Overview", "Periods", "Artists", "Genres", "Playlists", "Tracks", "Actions", "Data Quality"],
        "tabs",
    )
    require_contains(
        values(app.subheader),
        [
            "Library snapshot",
            "Activity periods",
            "Genre shifts",
            "Artist affinity",
            "Genre diversity",
            "Playlist coverage",
            "Playlist overlap",
            "Repeated and underrated tracks",
            "Next actions",
            "Rediscovery queue",
            "Playlist cleanup candidates",
            "Local data quality signals",
        ],
        "sections",
    )
    if len(app.dataframe) < 8:
        fail(f"dashboard should expose multiple analytical dataframes, found {len(app.dataframe)}")
    if not app.json:
        fail("dashboard Data Quality tab should expose a JSON quality block")

    print("OK: dashboard content exposes the expected self-analytics sections.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except AssertionError as error:
        print(f"ERROR: {error}", file=sys.stderr)
        raise SystemExit(1)
