from service.domain.format_feishu import build_feishu_payload, render_message_text
from service.providers import codeup

from tests.conftest import load_fixture


def test_message_contains_technical_and_original_sections() -> None:
    event = codeup.normalize_push(load_fixture("codeup_push.json"))

    text = render_message_text(event)

    assert "Technical Explanation Protocol" in text
    assert "Original Event" in text
    assert "Codeup User" in text
    assert "pengleni" in text
    assert "f2e2d57" in text


def test_feishu_payload_uses_text_message() -> None:
    event = codeup.normalize_push(load_fixture("codeup_push.json"))

    payload = build_feishu_payload(event)

    assert payload["msg_type"] == "text"
    assert "Technical Explanation Protocol" in payload["content"]["text"]

