from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


ZERO_SHA = "0" * 40


@dataclass(frozen=True)
class Commit:
    id: str
    message: str
    timestamp: str | None = None
    url: str | None = None
    author_name: str | None = None
    author_email: str | None = None


@dataclass(frozen=True)
class Repository:
    id: str | None
    name: str
    web_url: str | None = None
    git_http_url: str | None = None
    git_ssh_url: str | None = None
    path_with_namespace: str | None = None


@dataclass(frozen=True)
class PushEvent:
    provider: str
    event_name: str
    repository: Repository
    actor_name: str
    actor_username: str | None
    actor_email: str | None
    ref: str
    branch: str
    before: str
    after: str
    total_commits_count: int
    commits: list[Commit] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def action(self) -> str:
        if self.before == ZERO_SHA:
            return "created branch"
        if self.after == ZERO_SHA:
            return "deleted branch"
        return "pushed commits"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

