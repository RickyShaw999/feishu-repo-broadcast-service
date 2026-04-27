from __future__ import annotations

import json

from service.domain.models import PushEvent


MAX_COMMITS_IN_MESSAGE = 10
MAX_RAW_CHARS = 3000


def _short_sha(value: str) -> str:
    return value[:8] if value else "unknown"


def render_message_text(event: PushEvent) -> str:
    commit_count = event.total_commits_count
    commit_word = "commit" if commit_count == 1 else "commits"
    repo_label = event.repository.path_with_namespace or event.repository.name
    lines = [
        "Technical Explanation Protocol",
        f"- Actor: {event.actor_name}",
        f"- Time: provider payload commit timestamps; newest commit shown below when present",
        f"- Action: {event.action} on {event.provider}",
        f"- Repository: {repo_label}",
        f"- Branch: {event.branch or event.ref}",
        f"- Revision: {_short_sha(event.before)} -> {_short_sha(event.after)}",
        f"- Change size: {commit_count} {commit_word}",
    ]

    if event.commits:
        lines.append("- Commit details:")
        for commit in event.commits[:MAX_COMMITS_IN_MESSAGE]:
            author = commit.author_name or "unknown"
            message = " ".join(commit.message.split()) or "(no message)"
            lines.append(f"  - {_short_sha(commit.id)} {author}: {message}")
        remaining = len(event.commits) - MAX_COMMITS_IN_MESSAGE
        if remaining > 0:
            lines.append(f"  - ... {remaining} more commit(s) omitted")

    raw = json.dumps(event.raw, ensure_ascii=False, sort_keys=True, indent=2)
    if len(raw) > MAX_RAW_CHARS:
        raw = raw[:MAX_RAW_CHARS] + "\n...<truncated>"

    lines.extend(
        [
            "",
            "Original Event",
            f"- Provider: {event.provider}",
            f"- Ref: {event.ref}",
            f"- Before: {event.before}",
            f"- After: {event.after}",
            "- Raw payload:",
            raw,
        ]
    )
    return "\n".join(lines)


def build_feishu_payload(event: PushEvent) -> dict[str, object]:
    return {
        "msg_type": "text",
        "content": {
            "text": render_message_text(event),
        },
    }

