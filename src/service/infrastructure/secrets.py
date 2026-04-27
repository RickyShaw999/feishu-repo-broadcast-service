from __future__ import annotations

import os
from pathlib import Path


def read_secret(env_name: str, *, default: str | None = None) -> str | None:
    file_path = os.getenv(f"{env_name}_FILE")
    if file_path:
        path = Path(file_path)
        if path.exists():
            value = path.read_text(encoding="utf-8").strip()
            if value:
                return value

    direct = os.getenv(env_name)
    if direct:
        return direct
    return default
