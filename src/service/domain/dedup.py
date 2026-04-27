from __future__ import annotations

import hashlib
import json

from service.domain.models import PushEvent


def dedup_key(event: PushEvent) -> str:
    commit_ids = [commit.id for commit in event.commits]
    parts = {
        "provider": event.provider,
        "repository_id": event.repository.id,
        "repository_name": event.repository.name,
        "ref": event.ref,
        "before": event.before,
        "after": event.after,
        "total_commits_count": event.total_commits_count,
        "commit_ids": commit_ids,
    }
    payload = json.dumps(parts, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

