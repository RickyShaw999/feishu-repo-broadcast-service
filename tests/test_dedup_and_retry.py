from datetime import timedelta

from service.domain.delivery import DeliveryResult
from service.domain.format_feishu import build_feishu_payload
from service.domain.outbox import DELIVERED, FAILED_TERMINAL, IN_PROGRESS, PENDING, RETRY_SCHEDULED
from service.domain.retry_policy import RetryPolicy
from service.infrastructure.sqlite_store import SQLiteStore, utc_now
from service.providers import codeup

from tests.conftest import load_fixture


def test_enqueue_duplicate_reuses_existing_outbox(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path / "service.db"))
    store.initialize()
    event = codeup.normalize_push(load_fixture("codeup_push.json"))

    first = store.enqueue(event, build_feishu_payload(event))
    duplicate = store.enqueue(event, build_feishu_payload(event))

    assert first.created is True
    assert duplicate.created is False
    assert duplicate.outbox_id == first.outbox_id
    assert store.list_outbox()[0]["status"] == PENDING


def test_claim_and_mark_delivered(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path / "service.db"))
    store.initialize()
    event = codeup.normalize_push(load_fixture("codeup_push.json"))
    store.enqueue(event, build_feishu_payload(event))

    row = store.claim_next_due(lease_seconds=60)
    assert row is not None
    assert row["status"] == IN_PROGRESS

    store.record_attempt(row["id"], DeliveryResult.delivered(status_code=0, response_body="dry-run"))
    store.mark_delivered(row["id"])

    assert store.list_outbox()[0]["status"] == DELIVERED
    assert store.list_attempts()[0]["success"] == 1


def test_retry_policy_and_terminal_failure_states(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path / "service.db"))
    store.initialize()
    event = codeup.normalize_push(load_fixture("codeup_push.json"))
    store.enqueue(event, build_feishu_payload(event))
    row = store.claim_next_due(lease_seconds=60)
    assert row is not None

    retry_policy = RetryPolicy(max_attempts=2, initial_delay_seconds=1)
    result = DeliveryResult.retry(status_code=500, response_body="upstream failed")
    store.record_attempt(row["id"], result)
    store.schedule_retry(
        row["id"],
        next_attempt_at=utc_now() + timedelta(seconds=retry_policy.delay_for_attempt(row["attempts"])),
        error="upstream failed",
    )

    assert store.list_outbox()[0]["status"] == RETRY_SCHEDULED

    due_row = store.claim_next_due(lease_seconds=60, now=utc_now() + timedelta(seconds=2))
    assert due_row is not None
    store.mark_failed_terminal(due_row["id"], error="retry exhausted")

    assert store.list_outbox()[0]["status"] == FAILED_TERMINAL

