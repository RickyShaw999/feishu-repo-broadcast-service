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
