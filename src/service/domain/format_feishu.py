from __future__ import annotations

from service.domain.models import PushEvent


MAX_COMMITS_IN_MESSAGE = 10


def _short_sha(value: str) -> str:
    return value[:8] if value else "unknown"


def _event_time(event: PushEvent) -> str:
    timestamps = [commit.timestamp for commit in event.commits if commit.timestamp]
    if timestamps:
        return max(timestamps)
    return "unknown"


def _display_actor(event: PushEvent) -> str:
    commit_authors = {commit.author_name for commit in event.commits if commit.author_name}
    if len(commit_authors) == 1:
        return next(iter(commit_authors))
    return event.actor_name


def render_message_text(event: PushEvent) -> str:
    repo_label = event.repository.path_with_namespace or event.repository.name
    branch_label = event.branch or event.ref or "unknown"
    commit_count = event.total_commits_count
    lines = [
        "代码推送通知",
        f"操作人：{_display_actor(event)}",
        f"仓库：{repo_label}",
        f"分支：{branch_label}",
        f"推送时间：{_event_time(event)}",
        f"提交数量：{commit_count}",
        f"版本范围：{_short_sha(event.before)} -> {_short_sha(event.after)}",
    ]

    if event.commits:
        lines.append("提交内容：")
        for commit in event.commits[:MAX_COMMITS_IN_MESSAGE]:
            author = commit.author_name or "unknown"
            message = " ".join(commit.message.split()) or "(no message)"
            lines.append(f"- ({_short_sha(commit.id)}) {author}: {message}")
            lines.append("")
        remaining = len(event.commits) - MAX_COMMITS_IN_MESSAGE
        if remaining > 0:
            lines.append(f"- 其余 {remaining} 个提交已省略")
        elif lines[-1] == "":
            lines.pop()

    if event.repository.web_url:
        lines.append(f"仓库链接：{event.repository.web_url}")

    return "\n".join(lines)


def build_feishu_payload(event: PushEvent) -> dict[str, object]:
    return {
        "msg_type": "text",
        "content": {
            "text": render_message_text(event),
        },
    }
