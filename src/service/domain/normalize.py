from __future__ import annotations

from typing import Any

from service.domain.models import PushEvent
from service.providers import codeup, gitlab


def normalize_push(provider: str, payload: dict[str, Any]) -> PushEvent:
    if provider == codeup.PROVIDER:
        return codeup.normalize_push(payload)
    if provider == gitlab.PROVIDER:
        return gitlab.normalize_push(payload)
    raise ValueError(f"unsupported provider: {provider}")

