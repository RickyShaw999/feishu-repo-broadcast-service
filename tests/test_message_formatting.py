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
    assert "推送时间：2019-01-03T23:36:29+08:00" in text
    assert "提交内容：" in text
    assert "Fix webhook docs." in text
    assert "- (f2e2d57" in text
    assert "\n\n- (eb63d027" in text
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
