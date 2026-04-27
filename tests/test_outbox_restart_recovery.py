from datetime import timedelta

from service.domain.format_feishu import build_feishu_payload
from service.domain.outbox import DELIVERED, RETRY_SCHEDULED
from service.infrastructure.sqlite_store import SQLiteStore, utc_now
from service.providers import codeup

from tests.conftest import load_fixture


def test_stale_in_progress_is_reclaimed_on_startup_sweep(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path / "service.db"))
    store.initialize()
    event = codeup.normalize_push(load_fixture("codeup_push.json"))
    store.enqueue(event, build_feishu_payload(event))
    stale_now = utc_now()
    row = store.claim_next_due(lease_seconds=1, now=stale_now)
    assert row is not None

    reclaimed = store.sweep_stale_in_progress(now=stale_now + timedelta(seconds=2))

    assert reclaimed == 1
    assert store.list_outbox()[0]["status"] == RETRY_SCHEDULED
    assert store.list_outbox()[0]["attempts"] == 0
    assert store.list_attempts() == []


def test_delivered_rows_are_not_reclaimed_or_resent(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path / "service.db"))
    store.initialize()
    event = codeup.normalize_push(load_fixture("codeup_push.json"))
    store.enqueue(event, build_feishu_payload(event))
    row = store.claim_next_due(lease_seconds=1)
    assert row is not None
    store.mark_delivered(row["id"])

    reclaimed = store.sweep_stale_in_progress(now=utc_now() + timedelta(hours=1))
    due = store.claim_next_due(lease_seconds=1, now=utc_now() + timedelta(hours=1))

    assert reclaimed == 0
    assert due is None
    assert store.list_outbox()[0]["status"] == DELIVERED


def test_repeated_crash_after_claim_does_not_exhaust_retry_budget(tmp_path) -> None:
    store = SQLiteStore(str(tmp_path / "service.db"))
    store.initialize()
    event = codeup.normalize_push(load_fixture("codeup_push.json"))
    store.enqueue(event, build_feishu_payload(event))
    first_now = utc_now()

    first_claim = store.claim_next_due(lease_seconds=1, now=first_now)
    assert first_claim is not None
    store.sweep_stale_in_progress(now=first_now + timedelta(seconds=2))
    second_claim = store.claim_next_due(lease_seconds=1, now=first_now + timedelta(seconds=3))
    assert second_claim is not None
    store.sweep_stale_in_progress(now=first_now + timedelta(seconds=5))

    outbox = store.list_outbox()[0]
    assert outbox["status"] == RETRY_SCHEDULED
    assert outbox["attempts"] == 0
    assert store.list_attempts() == []
