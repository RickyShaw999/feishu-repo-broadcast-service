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
    assert "- (f2e2d57) Codeup User [2019-01-01 00:08]: Update readme." in text
    assert "\n\n- (eb63d027) Codeup User [2019-01-03 23:36]: Fix webhook docs." in text
    assert "仓库链接：https://codeup.aliyun.com/demo/pengleni" in text
    assert "Original Event" not in text
    assert '"object_kind"' not in text
    assert "Codeup User" in text
    assert "f2e2d57" in text


def test_feishu_payload_uses_text_message() -> None:
    event = codeup.normalize_push(load_fixture("codeup_push.json"))

    payload = build_feishu_payload(event)

    assert payload["msg_type"] == "text"
    assert "代码推送通知" in payload["content"]["text"]


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
