from __future__ import annotations

import asyncio
import json
import logging
from datetime import timedelta

from service.domain.retry_policy import RetryPolicy
from service.infrastructure.feishu_client import FeishuClient
from service.infrastructure.sqlite_store import SQLiteStore, utc_now

LOGGER = logging.getLogger(__name__)


class DeliveryWorker:
    def __init__(
        self,
        store: SQLiteStore,
        client: FeishuClient,
        *,
        lease_seconds: int,
        interval_seconds: float,
        retry_policy: RetryPolicy,
    ) -> None:
        self.store = store
        self.client = client
        self.lease_seconds = lease_seconds
        self.interval_seconds = interval_seconds
        self.retry_policy = retry_policy

    async def run_once(self) -> int:
        self.store.sweep_stale_in_progress()
        row = self.store.claim_next_due(lease_seconds=self.lease_seconds)
        if row is None:
            return 0

        payload = json.loads(row["payload_json"])
        result = await self.client.send(payload)
        attempts = self.store.record_attempt(int(row["id"]), result)

        if result.success:
            self.store.mark_delivered(int(row["id"]))
            LOGGER.info("delivery.delivered outbox_id=%s provider=%s", row["id"], row["provider"])
            return 1

        error = result.error or result.response_body or "delivery failed"
        if result.retryable and not self.retry_policy.exhausted(attempts):
            delay = self.retry_policy.delay_for_attempt(attempts)
            next_attempt_at = utc_now() + timedelta(seconds=delay)
            self.store.schedule_retry(int(row["id"]), next_attempt_at=next_attempt_at, error=error)
            LOGGER.warning("delivery.retry_scheduled outbox_id=%s attempts=%s delay=%s", row["id"], attempts, delay)
            return 1

        self.store.mark_failed_terminal(int(row["id"]), error=error)
        LOGGER.error("delivery.failed_terminal outbox_id=%s attempts=%s error=%s", row["id"], attempts, error)
        return 1

    async def run_forever(self) -> None:
        while True:
            try:
                await self.run_once()
            except Exception:
                LOGGER.exception("delivery.worker_error")
            await asyncio.sleep(self.interval_seconds)
