from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
import json
import logging
import time

from fastapi import APIRouter, HTTPException, Request

from service.domain.format_feishu import build_feishu_payload
from service.providers import gitlab

router = APIRouter(prefix="/webhooks/gitlab", tags=["webhooks"])
LOGGER = logging.getLogger(__name__)
SIGNATURE_TIMESTAMP_TOLERANCE_SECONDS = 300


def _validate_token(actual: str | None, expected: str | None) -> None:
    if not expected:
        LOGGER.error("webhook.rejected provider=gitlab reason=missing_configured_secret")
        raise HTTPException(status_code=503, detail="GitLab secret token is not configured")
    if not actual or not hmac.compare_digest(actual, expected):
        LOGGER.warning("webhook.rejected provider=gitlab reason=invalid_secret_token")
        raise HTTPException(status_code=401, detail="invalid GitLab secret token")


def _decode_signing_token(token: str) -> bytes:
    if not token.startswith("whsec_"):
        LOGGER.error("webhook.rejected provider=gitlab reason=invalid_signing_token_config")
        raise HTTPException(status_code=503, detail="GitLab signing token must start with whsec_")
    try:
        return base64.b64decode(token.removeprefix("whsec_"), validate=True)
    except binascii.Error as exc:
        LOGGER.error("webhook.rejected provider=gitlab reason=invalid_signing_token_config")
        raise HTTPException(status_code=503, detail="GitLab signing token is not valid base64") from exc


def _validate_signature_timestamp(timestamp: str | None) -> str:
    if not timestamp:
        LOGGER.warning("webhook.rejected provider=gitlab reason=missing_signature_timestamp")
        raise HTTPException(status_code=401, detail="missing GitLab webhook timestamp")
    try:
        request_time = int(timestamp)
    except ValueError as exc:
        LOGGER.warning("webhook.rejected provider=gitlab reason=invalid_signature_timestamp")
        raise HTTPException(status_code=401, detail="invalid GitLab webhook timestamp") from exc

    if abs(int(time.time()) - request_time) > SIGNATURE_TIMESTAMP_TOLERANCE_SECONDS:
        LOGGER.warning("webhook.rejected provider=gitlab reason=stale_signature_timestamp")
        raise HTTPException(status_code=401, detail="stale GitLab webhook timestamp")
    return timestamp


def _validate_signature(
    *,
    message_id: str | None,
    timestamp: str | None,
    signature_header: str,
    signing_token: str | None,
    body: bytes,
) -> None:
    if not signing_token:
        LOGGER.error("webhook.rejected provider=gitlab reason=missing_configured_signing_token")
        raise HTTPException(status_code=503, detail="GitLab signing token is not configured")
    if not message_id:
        LOGGER.warning("webhook.rejected provider=gitlab reason=missing_signature_message_id")
        raise HTTPException(status_code=401, detail="missing GitLab webhook id")

    timestamp = _validate_signature_timestamp(timestamp)
    key = _decode_signing_token(signing_token)
    signed_content = message_id.encode("utf-8") + b"." + timestamp.encode("utf-8") + b"." + body
    digest = hmac.new(key, signed_content, hashlib.sha256).digest()
    expected = "v1," + base64.b64encode(digest).decode("utf-8")

    signatures = [value for value in signature_header.split(" ") if value]
    if not any(hmac.compare_digest(expected, signature) for signature in signatures):
        LOGGER.warning("webhook.rejected provider=gitlab reason=invalid_signature")
        raise HTTPException(status_code=401, detail="invalid GitLab webhook signature")


def _validate_authentication(request: Request, body: bytes) -> None:
    settings = request.app.state.settings
    signature_header = request.headers.get("webhook-signature")
    if signature_header:
        _validate_signature(
            message_id=request.headers.get("webhook-id") or request.headers.get("Idempotency-Key"),
            timestamp=request.headers.get("webhook-timestamp"),
            signature_header=signature_header,
            signing_token=settings.gitlab_signing_token,
            body=body,
        )
        return

    _validate_token(request.headers.get("X-Gitlab-Token"), settings.gitlab_secret_token)


@router.post("")
async def receive_gitlab_push(request: Request) -> dict[str, object]:
    if request.headers.get("X-Gitlab-Event") != gitlab.PUSH_HEADER:
        LOGGER.warning("webhook.rejected provider=gitlab reason=unsupported_event event=%s", request.headers.get("X-Gitlab-Event"))
        raise HTTPException(status_code=400, detail="unsupported GitLab event")

    body = await request.body()
    _validate_authentication(request, body)

    try:
        payload = json.loads(body)
    except json.JSONDecodeError as exc:
        LOGGER.warning("webhook.rejected provider=gitlab reason=invalid_json")
        raise HTTPException(status_code=400, detail="invalid JSON payload") from exc

    try:
        event = gitlab.normalize_push(payload)
    except ValueError as exc:
        LOGGER.warning("webhook.rejected provider=gitlab reason=payload_normalization_failed error=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = request.app.state.store.enqueue(event, build_feishu_payload(event))
    LOGGER.info(
        "webhook.accepted provider=gitlab created=%s dedup_key=%s outbox_id=%s",
        result.created,
        result.dedup_key,
        result.outbox_id,
    )
    return {
        "status": "accepted" if result.created else "duplicate",
        "dedup_key": result.dedup_key,
        "outbox_id": result.outbox_id,
        "outbox_status": result.status,
    }
