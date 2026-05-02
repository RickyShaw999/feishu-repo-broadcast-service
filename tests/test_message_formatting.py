from service.domain.format_feishu import build_feishu_payload, render_message_text
from service.providers import codeup

from tests.conftest import load_fixture


def test_message_contains_human_friendly_summary() -> None:
    event = codeup.normalize_push(load_fixture("codeup_push.json"))

    text = render_message_text(event)

    assert "代码推送通知" in text
    assert "操作人：Codeup User" in text
    assert "仓库：pengleni" in text
    assert "分支：develop" in text
    assert "推送时间：2019-01-03 23:36" in text
    assert "提交内容：" in text
    assert "Fix webhook docs." in text
    assert "- (f2e2d577) Codeup User [2019-01-01 00:08]: Update readme." in text
    assert "\n\n- (eb63d027) Codeup User [2019-01-03 23:36]: Fix webhook docs." in text
    assert "仓库链接：https://codeup.aliyun.com/demo/pengleni" in text
    assert "Original Event" not in text
    assert '"object_kind"' not in text
    assert "Codeup User" in text
    assert "f2e2d57" in text


def test_feishu_payload_uses_interactive_card() -> None:
    event = codeup.normalize_push(load_fixture("codeup_push.json"))

    payload = build_feishu_payload(event)

    assert payload["msg_type"] == "interactive"
    card = payload["card"]
    assert card["config"]["wide_screen_mode"] is True
    assert card["header"]["title"]["content"] == "代码推送通知：pengleni"
    summary = card["elements"][0]["text"]["content"]
    commits = card["elements"][2]["text"]["content"]
    assert "**操作人：** Codeup User" in summary
    assert "**仓库：** [pengleni](https://codeup.aliyun.com/demo/pengleni)" in summary
    assert "**提交内容：**" in commits
    assert "[eb63d027](https://codeup.aliyun.com/demo/pengleni/commits/eb63d0277e64684236ebf8394b919230c4b8a286)" in commits


def test_single_commit_author_overrides_org_style_actor_name() -> None:
    payload = load_fixture("codeup_push.json")
    payload["user_name"] = "北京指边科技有限公司"
    payload["commits"] = [
        {
            "id": "f2514848563238ee329fe4820cfc19a65c432f28",
            "message": "测试飞书机器人\n",
            "timestamp": "2026-04-28T21:41:13.000+08:00",
            "url": "https://codeup.aliyun.com/demo/pengleni/commits/f2514848563238ee329fe4820cfc19a65c432f28",
            "author": {
                "name": "hyk",
                "email": "hyk@example.com",
            },
        }
    ]
    payload["total_commits_count"] = 1
    payload["before"] = "cd2be4fb0c000000000000000000000000000000"
    payload["after"] = "93a189d40c000000000000000000000000000000"

    event = codeup.normalize_push(payload)
    text = render_message_text(event)

    assert "操作人：hyk" in text
    assert "操作人：北京指边科技有限公司" not in text


def test_latest_commit_author_is_used_when_actor_name_is_org_and_authors_are_mixed() -> None:
    payload = load_fixture("codeup_push.json")
    payload["user_name"] = "北京指边科技有限公司"
    payload["commits"] = [
        {
            "id": "d4f76e4700000000000000000000000000000000",
            "message": "fix: 恢复 LightRAG 知识库过滤\n",
            "timestamp": "2026-04-30T02:01:00.000+08:00",
            "url": "https://example.com/commit/d4f76e47",
            "author": {
                "name": "RickyShaw",
                "email": "ricky@example.com",
            },
        },
        {
            "id": "6391c24500000000000000000000000000000000",
            "message": "Split repo test foundation into apply-ready L2 changes\n",
            "timestamp": "2026-04-30T02:30:00.000+08:00",
            "url": "https://example.com/commit/6391c245",
            "author": {
                "name": "hyk",
                "email": "hyk@example.com",
            },
        },
        {
            "id": "93a189d400000000000000000000000000000000",
            "message": "Merge remote-tracking branch 'origin/develop' into develop\n",
            "timestamp": "2026-04-30T02:50:00.000+08:00",
            "url": "https://example.com/commit/93a189d4",
            "author": {
                "name": "hyk",
                "email": "hyk@example.com",
            },
        },
        {
            "id": "36c1536900000000000000000000000000000000",
            "message": "Merge branch 'develop' into feature/observability\n",
            "timestamp": "2026-04-30T03:03:26.000+08:00",
            "url": "https://example.com/commit/36c15369",
            "author": {
                "name": "RayLeeTHU",
                "email": "ray@example.com",
            },
        },
    ]
    payload["total_commits_count"] = 4
    payload["before"] = "63f83a2400000000000000000000000000000000"
    payload["after"] = "36c1536900000000000000000000000000000000"
    payload["ref"] = "refs/heads/feature/observability"

    event = codeup.normalize_push(payload)
    text = render_message_text(event)

    assert "操作人：RayLeeTHU" in text
    assert "操作人：北京指边科技有限公司" not in text
    assert "推送时间：2026-04-30 03:03" in text
    assert "- (36c15369) RayLeeTHU [2026-04-30 03:03]: Merge branch 'develop' into feature/observability" in text


def test_after_commit_author_is_used_when_payload_lists_newest_commit_first() -> None:
    payload = load_fixture("codeup_push.json")
    payload["user_name"] = "北京指边科技有限公司"
    payload["commits"] = [
        {
            "id": "b6ccad8f00000000000000000000000000000000",
            "message": "Make skincare decisions actionable while preserving safety gates\n\nLong body omitted.",
            "timestamp": "2026-04-30T20:02:00.000+08:00",
            "url": "https://example.com/commit/b6ccad8f",
            "author": {
                "name": "RickyShaw",
                "email": "ricky@example.com",
            },
        },
        {
            "id": "36c1536900000000000000000000000000000000",
            "message": "Merge branch 'develop' into feature/observability\n",
            "timestamp": "2026-04-30T03:03:26.000+08:00",
            "url": "https://example.com/commit/36c15369",
            "author": {
                "name": "RayLeeTHU",
                "email": "ray@example.com",
            },
        },
    ]
    payload["total_commits_count"] = 2
    payload["before"] = "0000000000000000000000000000000000000000"
    payload["after"] = "b6ccad8f00000000000000000000000000000000"
    payload["ref"] = "refs/heads/feature/skincare-decision-llm-workflow-action-plan"

    event = codeup.normalize_push(payload)
    text = render_message_text(event)
    card = build_feishu_payload(event)["card"]
    summary = card["elements"][0]["text"]["content"]

    assert "操作人：RickyShaw" in text
    assert "操作人：RayLeeTHU" not in text
    assert "推送时间：2026-04-30 20:02" in text
    assert "**操作人：** RickyShaw" in summary


def test_remaining_commit_count_uses_total_count_when_payload_is_truncated() -> None:
    payload = load_fixture("codeup_push.json")
    payload["commits"] = [
        {
            "id": f"{index:040x}",
            "message": f"Commit {index}",
            "timestamp": f"2026-04-30T10:{index:02d}:00.000+08:00",
            "url": f"https://example.com/commit/{index}",
            "author": {
                "name": "RickyShaw",
                "email": "ricky@example.com",
            },
        }
        for index in range(20)
    ]
    payload["total_commits_count"] = 100
    payload["after"] = "0000000000000000000000000000000000000013"

    event = codeup.normalize_push(payload)
    text = render_message_text(event)
    card = build_feishu_payload(event)["card"]
    commits = card["elements"][2]["text"]["content"]

    assert "- 其余 90 个提交已省略" in text
    assert "- 其余 90 个提交已省略" in commits
