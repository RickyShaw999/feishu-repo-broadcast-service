from __future__ import annotations

from typing import Any

from service.domain.models import Commit, PushEvent, Repository


PROVIDER = "gitlab"
PUSH_HEADER = "Push Hook"


def _branch_from_ref(ref: str) -> str:
    return ref.removeprefix("refs/heads/")


def normalize_push(payload: dict[str, Any]) -> PushEvent:
    if payload.get("object_kind") != "push" and payload.get("event_name") != "push":
        raise ValueError("GitLab payload is not a push event")

    project_payload = payload.get("project") or {}
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
            id=str(payload.get("project_id") or project_payload.get("id")) if (payload.get("project_id") or project_payload.get("id")) is not None else None,
            name=str(project_payload.get("name") or repository_payload.get("name") or "unknown"),
            web_url=project_payload.get("web_url") or repository_payload.get("homepage"),
            git_http_url=project_payload.get("git_http_url") or repository_payload.get("git_http_url"),
            git_ssh_url=project_payload.get("git_ssh_url") or repository_payload.get("git_ssh_url") or repository_payload.get("url"),
            path_with_namespace=project_payload.get("path_with_namespace"),
        ),
        actor_name=str(payload.get("user_name") or payload.get("user_username") or "unknown"),
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

