import asyncio

from service.config import Settings
from service.domain.format_feishu import build_feishu_payload
from service.domain.outbox import DELIVERED
from service.domain.retry_policy import RetryPolicy
from service.infrastructure.feishu_client import FeishuClient, build_feishu_sign
from service.infrastructure.sqlite_store import SQLiteStore
from service.providers import codeup
from service.worker.retry_loop import DeliveryWorker

from tests.conftest import load_fixture


def test_dry_run_worker_marks_delivery_without_external_call(tmp_path) -> None:
    settings = Settings(database_path=str(tmp_path / "service.db"), delivery_mode="dry_run")
    store = SQLiteStore(settings.database_path)
    store.initialize()
    event = codeup.normalize_push(load_fixture("codeup_push.json"))
    store.enqueue(event, build_feishu_payload(event))
    worker = DeliveryWorker(
        store,
        FeishuClient(settings),
        lease_seconds=60,
        interval_seconds=0.01,
        retry_policy=RetryPolicy(max_attempts=3),
    )

    processed = asyncio.run(worker.run_once())

    assert processed == 1
    assert store.list_outbox()[0]["status"] == DELIVERED
    attempt = store.list_attempts()[0]
    assert attempt["success"] == 1
    assert "Technical Explanation Protocol" in attempt["response_body"]


def test_feishu_sign_is_stable_for_known_timestamp() -> None:
    assert build_feishu_sign(1700000000, "secret") == "fiWS2+gh28DOydAv7hzONH/mDn9+b1Y4Y5ivXWXy8vA="
