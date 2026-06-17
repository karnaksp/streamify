#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from yamusic_ingest.config import Settings
from yamusic_ingest.yandex_client import client_metadata

TOKEN_HELPER_URL = "https://github.com/MarshalX/yandex-music-token"


def yandex_music_client_capabilities() -> dict[str, Any]:
    try:
        from yandex_music import Client
    except ImportError:
        metadata = client_metadata()
        return {
            **metadata,
            "client_importable": False,
            "supports_device_auth": False,
            "supports_token_only_client": False,
        }

    metadata = client_metadata()
    return {
        **metadata,
        "client_importable": True,
        "supports_device_auth": hasattr(Client, "device_auth"),
        "supports_token_only_client": True,
    }


def token_status() -> dict[str, Any]:
    settings = Settings.from_env()
    capabilities = yandex_music_client_capabilities()
    return {
        "env_file_present": (ROOT / ".env").exists(),
        "token_configured": bool(settings.token),
        "raw_dir": str(settings.raw_dir),
        "recommended_helper": TOKEN_HELPER_URL,
        "next_step": "make preflight" if settings.token else "get a Yandex Music OAuth token and save YANDEX_MUSIC_TOKEN in .env",
        **capabilities,
    }


def print_human_help(status: dict[str, Any]) -> None:
    print("Streamify Yandex Music token setup")
    print()
    print("Current local status:")
    print(f"  .env present: {str(status['env_file_present']).lower()}")
    print(f"  token configured: {str(status['token_configured']).lower()}")
    print(f"  yandex-music importable: {str(status['client_importable']).lower()}")
    print(f"  yandex-music version: {status.get('client_library_version') or 'unknown'}")
    print(f"  built-in device auth helper: {str(status['supports_device_auth']).lower()}")
    print()
    print("This project does not ask for your Yandex password and must not print or store token values outside .env.")
    if status["supports_device_auth"]:
        print("The installed yandex-music client reports a built-in device_auth helper, but Streamify still expects the final OAuth token in .env.")
    else:
        print("The installed yandex-music client accepts an existing OAuth token but does not expose a built-in token acquisition flow.")
    print()
    print("Steps:")
    print("  1. Ensure local config exists: cp .env.example .env")
    print(f"  2. Get a Yandex Music OAuth token with a trusted helper, for example: {TOKEN_HELPER_URL}")
    print("  3. Paste only the token into .env as: YANDEX_MUSIC_TOKEN=...")
    print("  4. Validate without writing raw data: make preflight")
    print("  5. Build real-account analytics: make acceptance-real")
    print()
    print(f"Next step: {status['next_step']}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Print safe Yandex Music token setup guidance for Streamify.")
    parser.add_argument("--json", action="store_true", help="Print machine-readable status without token values.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    status = token_status()
    if args.json:
        print(json.dumps(status, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print_human_help(status)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
