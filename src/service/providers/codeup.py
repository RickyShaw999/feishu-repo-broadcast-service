from __future__ import annotations

from typing import Any

from service.domain.models import Commit, PushEvent, Repository


PROVIDER = "codeup"
PUSH_HEADER = "Push Hook"


def _branch_from_ref(ref: str) -> str:
    return ref.removeprefix("refs/heads/")


def is_test_hook_payload(payload: dict[str, Any]) -> bool:
    # Codeup's "Test Hook" button sends a minimal probe body with only before/after.
    return (
        payload.get("object_kind") is None
        and "before" in payload
        and "after" in payload
        and payload.get("ref") is None
        and payload.get("repository") is None
        and payload.get("commits") is None
    )


def normalize_push(payload: dict[str, Any]) -> PushEvent:
    if payload.get("object_kind") != "push":
        raise ValueError("Codeup payload is not a push event")

    repository_payload = payload.get("repository") or {}
    commits = [
        Commit(
            id=str(commit.get("id", "")),
            message=str(commit.get("message", "")).strip(),
            timestamp=commit.get("timestamp"),
            url=commit.get("url"),
            author_name=(commit.get("author") or {}).get("name"),
            author_email=(commit.get("author") or {}).get("email"),
        )
        for commit in payload.get("commits") or []
    ]

    return PushEvent(
        provider=PROVIDER,
        event_name="push",
        repository=Repository(
            id=str(payload.get("project_id")) if payload.get("project_id") is not None else None,
            name=str(repository_payload.get("name") or payload.get("project", {}).get("name") or "unknown"),
            web_url=repository_payload.get("homepage") or repository_payload.get("web_url"),
            git_http_url=repository_payload.get("git_http_url"),
            git_ssh_url=repository_payload.get("git_ssh_url") or repository_payload.get("url"),
            path_with_namespace=repository_payload.get("path_with_namespace"),
        ),
        actor_name=str(payload.get("user_name") or "unknown"),
        actor_username=payload.get("user_username"),
        actor_email=payload.get("user_email"),
        ref=str(payload.get("ref") or ""),
        branch=_branch_from_ref(str(payload.get("ref") or "")),
        before=str(payload.get("before") or ""),
        after=str(payload.get("after") or ""),
        total_commits_count=int(payload.get("total_commits_count") or len(commits)),
        commits=commits,
        raw=payload,
    )
