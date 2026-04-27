from __future__ import annotations

import hmac
import logging

from fastapi import APIRouter, HTTPException, Request

from service.domain.format_feishu import build_feishu_payload
from service.providers import codeup

router = APIRouter(prefix="/webhooks/codeup", tags=["webhooks"])
LOGGER = logging.getLogger(__name__)


def _validate_token(actual: str | None, expected: str | None) -> None:
    if not expected:
        LOGGER.error("webhook.rejected provider=codeup reason=missing_configured_secret")
        raise HTTPException(status_code=503, detail="Codeup secret token is not configured")
    if not actual or not hmac.compare_digest(actual, expected):
        LOGGER.warning("webhook.rejected provider=codeup reason=invalid_secret_token")
        raise HTTPException(status_code=401, detail="invalid Codeup secret token")


@router.post("")
async def receive_codeup_push(request: Request) -> dict[str, object]:
    settings = request.app.state.settings
    if request.headers.get("Codeup-Event") != codeup.PUSH_HEADER:
        LOGGER.warning("webhook.rejected provider=codeup reason=unsupported_event event=%s", request.headers.get("Codeup-Event"))
        raise HTTPException(status_code=400, detail="unsupported Codeup event")
    _validate_token(request.headers.get("X-Codeup-Token"), settings.codeup_secret_token)

    payload = await request.json()
    try:
        event = codeup.normalize_push(payload)
    except ValueError as exc:
        LOGGER.warning("webhook.rejected provider=codeup reason=payload_normalization_failed error=%s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    result = request.app.state.store.enqueue(event, build_feishu_payload(event))
    LOGGER.info(
        "webhook.accepted provider=codeup created=%s dedup_key=%s outbox_id=%s",
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
