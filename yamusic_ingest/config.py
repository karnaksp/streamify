from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ.setdefault(key, value)


@dataclass(frozen=True)
class Settings:
    token: str | None
    raw_dir: Path
    sample: bool = False

    @classmethod
    def from_env(cls, sample: bool = False) -> "Settings":
        load_dotenv()
        data_dir = Path(os.getenv("STREAMIFY_DATA_DIR", "data"))
        raw_dir = Path(os.getenv("STREAMIFY_RAW_DIR", str(data_dir / "raw" / "yamusic")))
        token = os.getenv("YANDEX_MUSIC_TOKEN") or None
        return cls(token=token, raw_dir=raw_dir, sample=sample)
