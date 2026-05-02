from __future__ import annotations

from datetime import datetime, timezone

from service.domain.models import Commit, PushEvent, ZERO_SHA


MAX_COMMITS_IN_MESSAGE = 10
MAX_COMMIT_MESSAGE_CHARS = 180


def _short_sha(value: str) -> str:
    return value[:8] if value else "unknown"


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _matching_commit(event: PushEvent, sha: str) -> Commit | None:
    normalized_sha = sha.lower()
    if not normalized_sha or normalized_sha == ZERO_SHA:
        return None
    for commit in event.commits:
        commit_id = commit.id.lower()
        if commit_id and (
            commit_id == normalized_sha
            or commit_id.startswith(normalized_sha)
            or normalized_sha.startswith(commit_id)
        ):
            return commit
    return None


def _latest_commit(event: PushEvent) -> Commit | None:
    after_commit = _matching_commit(event, event.after)
    if after_commit:
        return after_commit

    timestamped_commits = [
        (parsed, index, commit)
        for index, commit in enumerate(event.commits)
        if (parsed := _parse_timestamp(commit.timestamp)) is not None
    ]
    if timestamped_commits:
        return max(timestamped_commits, key=lambda item: (item[0], item[1]))[2]

    if event.commits:
        return event.commits[0]
    return None


def _event_time(event: PushEvent) -> str:
    latest_commit = _latest_commit(event)
    if latest_commit and latest_commit.timestamp:
        return _format_timestamp(latest_commit.timestamp)

    timestamped_commits = [
        (parsed, commit.timestamp)
        for commit in event.commits
        if (parsed := _parse_timestamp(commit.timestamp)) is not None and commit.timestamp
    ]
    if timestamped_commits:
        return _format_timestamp(max(timestamped_commits, key=lambda item: item[0])[1])
    return "unknown"


def _format_timestamp(value: str | None) -> str:
    if not value:
        return "unknown"
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return value
    return parsed.strftime("%Y-%m-%d %H:%M")


def _latest_commit_author(event: PushEvent) -> str | None:
    latest_commit = _latest_commit(event)
    if latest_commit and latest_commit.author_name:
        return latest_commit.author_name
    return None


def _display_actor(event: PushEvent) -> str:
    latest_commit_author = _latest_commit_author(event)
    if latest_commit_author:
        return latest_commit_author
    if event.actor_username:
        return event.actor_username
    return event.actor_name


def _repo_label(event: PushEvent) -> str:
    return event.repository.path_with_namespace or event.repository.name


def _branch_label(event: PushEvent) -> str:
    return event.branch or event.ref or "unknown"


def _single_line_message(message: str) -> str:
    compacted = " ".join(message.split()) or "(no message)"
    if len(compacted) <= MAX_COMMIT_MESSAGE_CHARS:
        return compacted
    return f"{compacted[: MAX_COMMIT_MESSAGE_CHARS - 3].rstrip()}..."


def _remaining_commit_count(event: PushEvent, displayed_count: int) -> int:
    total_count = max(event.total_commits_count, len(event.commits))
    return max(total_count - displayed_count, 0)


def _commit_text_line(commit: Commit) -> str:
    author = commit.author_name or "unknown"
    message = _single_line_message(commit.message)
    commit_time = _format_timestamp(commit.timestamp)
    return f"- ({_short_sha(commit.id)}) {author} [{commit_time}]: {message}"


def render_message_text(event: PushEvent) -> str:
    commit_count = event.total_commits_count
    lines = [
        "代码推送通知",
        f"操作人：{_display_actor(event)}",
        f"仓库：{_repo_label(event)}",
        f"分支：{_branch_label(event)}",
        f"推送时间：{_event_time(event)}",
        f"提交数量：{commit_count}",
        f"版本范围：{_short_sha(event.before)} -> {_short_sha(event.after)}",
    ]

    if event.commits:
        lines.append("提交内容：")
        displayed_commits = event.commits[:MAX_COMMITS_IN_MESSAGE]
        for commit in displayed_commits:
            lines.append(_commit_text_line(commit))
            lines.append("")
        remaining = _remaining_commit_count(event, len(displayed_commits))
        if remaining > 0:
            lines.append(f"- 其余 {remaining} 个提交已省略")
        elif lines[-1] == "":
            lines.pop()

    if event.repository.web_url:
        lines.append(f"仓库链接：{event.repository.web_url}")

    return "\n".join(lines)


def _markdown_link(label: str, url: str | None) -> str:
    if not url:
        return label
    return f"[{label}]({url})"


def _commit_markdown_line(commit: Commit) -> str:
    sha = _markdown_link(_short_sha(commit.id), commit.url)
    author = commit.author_name or "unknown"
    commit_time = _format_timestamp(commit.timestamp)
    message = _single_line_message(commit.message)
    return f"- {sha} {author} [{commit_time}]: {message}"


def _header_template(event: PushEvent) -> str:
    if event.after == ZERO_SHA:
        return "red"
    if event.before == ZERO_SHA:
        return "green"
    return "blue"


def _summary_markdown(event: PushEvent) -> str:
    repo = _markdown_link(_repo_label(event), event.repository.web_url)
    return "\n".join(
        [
            f"**操作人：** {_display_actor(event)}",
            f"**仓库：** {repo}",
            f"**分支：** {_branch_label(event)}",
            f"**推送时间：** {_event_time(event)}",
            f"**提交数量：** {event.total_commits_count}",
            f"**版本范围：** {_short_sha(event.before)} -> {_short_sha(event.after)}",
        ]
    )


def _commits_markdown(event: PushEvent) -> str:
    if not event.commits:
        return "**提交内容：**\n无提交明细"

    displayed_commits = event.commits[:MAX_COMMITS_IN_MESSAGE]
    lines = ["**提交内容：**", *[_commit_markdown_line(commit) for commit in displayed_commits]]
    remaining = _remaining_commit_count(event, len(displayed_commits))
    if remaining > 0:
        lines.append(f"- 其余 {remaining} 个提交已省略")
    return "\n".join(lines)


def build_feishu_card(event: PushEvent) -> dict[str, object]:
    elements: list[dict[str, object]] = [
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": _summary_markdown(event),
            },
        },
        {"tag": "hr"},
        {
            "tag": "div",
            "text": {
                "tag": "lark_md",
                "content": _commits_markdown(event),
            },
        },
    ]

    latest_commit = _latest_commit(event)
    actions = []
    if latest_commit and latest_commit.url:
        actions.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "查看最新提交"},
                "url": latest_commit.url,
                "type": "primary",
            }
        )
    if event.repository.web_url:
        actions.append(
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": "打开仓库"},
                "url": event.repository.web_url,
                "type": "default",
            }
        )
    if actions:
        elements.append({"tag": "action", "actions": actions})

    return {
        "config": {
            "wide_screen_mode": True,
        },
        "header": {
            "title": {
                "tag": "plain_text",
                "content": f"代码推送通知：{_repo_label(event)}",
            },
            "template": _header_template(event),
        },
        "elements": elements,
    }


def build_feishu_payload(event: PushEvent) -> dict[str, object]:
    return {
        "msg_type": "interactive",
        "card": build_feishu_card(event),
    }
