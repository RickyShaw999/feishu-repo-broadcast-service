from __future__ import annotations

from dataclasses import dataclass


PENDING = "pending"
IN_PROGRESS = "in_progress"
RETRY_SCHEDULED = "retry_scheduled"
DELIVERED = "delivered"
FAILED_TERMINAL = "failed_terminal"


@dataclass(frozen=True)
class EnqueueResult:
    created: bool
    dedup_key: str
    outbox_id: int
    status: str

