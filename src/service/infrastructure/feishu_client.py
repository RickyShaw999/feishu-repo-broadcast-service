from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
from typing import Any

import httpx

from service.config import Settings
from service.domain.delivery import DeliveryResult


def build_feishu_sign(timestamp: int, secret: str) -> str:
    string_to_sign = f"{timestamp}\n{secret}"
    digest = hmac.new(string_to_sign.encode("utf-8"), b"", hashlib.sha256).digest()
    return base64.b64encode(digest).decode("utf-8")


class FeishuClient:
    def __init__(self, settings: Settings, *, timeout_seconds: float = 10.0) -> None:
        self.settings = settings
        self.timeout_seconds = timeout_seconds

    async def send(self, payload: dict[str, Any]) -> DeliveryResult:
        if self.settings.dry_run:
            return DeliveryResult.delivered(status_code=0, response_body=json.dumps(payload, ensure_ascii=False))

        if not self.settings.feishu_webhook_url:
            return DeliveryResult.fail(error="FEISHU_WEBHOOK_URL is required when DELIVERY_MODE=live")

        body = dict(payload)
        if self.settings.feishu_signing_secret:
            timestamp = int(time.time())
            body["timestamp"] = str(timestamp)
            body["sign"] = build_feishu_sign(timestamp, self.settings.feishu_signing_secret)

        try:
            async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
                response = await client.post(self.settings.feishu_webhook_url, json=body)
        except httpx.TimeoutException as exc:
            return DeliveryResult.retry(error=f"timeout sending to Feishu: {exc}")
        except httpx.TransportError as exc:
            return DeliveryResult.retry(error=f"transport error sending to Feishu: {exc}")

        text = response.text
        if response.status_code == 429 or response.status_code >= 500:
            return DeliveryResult.retry(status_code=response.status_code, response_body=text)
        if response.status_code >= 400:
            return DeliveryResult.fail(status_code=response.status_code, response_body=text)

        try:
            parsed = response.json()
        except ValueError:
            return DeliveryResult.delivered(status_code=response.status_code, response_body=text)

        code = parsed.get("code", parsed.get("StatusCode", 0))
        if code in (0, "0"):
            return DeliveryResult.delivered(status_code=response.status_code, response_body=text)
        return DeliveryResult.fail(status_code=response.status_code, response_body=text, error=f"Feishu returned non-zero code: {code}")

