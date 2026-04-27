from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from service.domain.dedup import dedup_key
from service.domain.delivery import DeliveryResult
from service.domain.models import PushEvent
from service.domain.outbox import DELIVERED, FAILED_TERMINAL, IN_PROGRESS, PENDING, RETRY_SCHEDULED, EnqueueResult


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


class SQLiteStore:
    def __init__(self, path: str) -> None:
        self.path = path

    @contextmanager
    def connect(self) -> Iterator[sqlite3.Connection]:
        db_path = Path(self.path)
        if db_path.parent:
            db_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.path, timeout=30)
        conn.row_factory = sqlite3.Row
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def initialize(self) -> None:
        with self.connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS inbound_events (
                    dedup_key TEXT PRIMARY KEY,
                    provider TEXT NOT NULL,
                    event_json TEXT NOT NULL,
                    received_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS outbox (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    dedup_key TEXT NOT NULL UNIQUE,
                    provider TEXT NOT NULL,
                    status TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    attempts INTEGER NOT NULL DEFAULT 0,
                    next_attempt_at TEXT,
                    lease_expires_at TEXT,
                    last_error TEXT,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    delivered_at TEXT,
                    FOREIGN KEY (dedup_key) REFERENCES inbound_events(dedup_key)
                );

                CREATE TABLE IF NOT EXISTS delivery_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    outbox_id INTEGER NOT NULL,
                    attempted_at TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    retryable INTEGER NOT NULL,
                    terminal INTEGER NOT NULL,
                    status_code INTEGER,
                    response_body TEXT,
                    error TEXT,
                    FOREIGN KEY (outbox_id) REFERENCES outbox(id)
                );
                """
            )

    def enqueue(self, event: PushEvent, feishu_payload: dict[str, Any]) -> EnqueueResult:
        key = dedup_key(event)
        now = iso(utc_now())
        event_json = json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True)
        payload_json = json.dumps(feishu_payload, ensure_ascii=False, sort_keys=True)

        with self.connect() as conn:
            try:
                conn.execute(
                    "INSERT INTO inbound_events (dedup_key, provider, event_json, received_at) VALUES (?, ?, ?, ?)",
                    (key, event.provider, event_json, now),
                )
                cursor = conn.execute(
                    """
                    INSERT INTO outbox (dedup_key, provider, status, payload_json, next_attempt_at, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (key, event.provider, PENDING, payload_json, now, now, now),
                )
                return EnqueueResult(created=True, dedup_key=key, outbox_id=int(cursor.lastrowid), status=PENDING)
            except sqlite3.IntegrityError:
                row = conn.execute(
                    "SELECT id, status FROM outbox WHERE dedup_key = ?",
                    (key,),
                ).fetchone()
                if row is None:
                    raise
                return EnqueueResult(created=False, dedup_key=key, outbox_id=int(row["id"]), status=str(row["status"]))

    def sweep_stale_in_progress(self, *, now: datetime | None = None) -> int:
        current = iso(now or utc_now())
        with self.connect() as conn:
            cursor = conn.execute(
                """
                UPDATE outbox
                SET status = ?, next_attempt_at = ?, lease_expires_at = NULL, updated_at = ?
                WHERE status = ? AND lease_expires_at IS NOT NULL AND lease_expires_at <= ?
                """,
                (RETRY_SCHEDULED, current, current, IN_PROGRESS, current),
            )
            return int(cursor.rowcount)

    def claim_next_due(self, *, lease_seconds: int, now: datetime | None = None) -> sqlite3.Row | None:
        current_dt = now or utc_now()
        current = iso(current_dt)
        lease_expires = iso(current_dt + timedelta(seconds=lease_seconds))

        with self.connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """
                SELECT * FROM outbox
                WHERE status = ?
                   OR (status = ? AND next_attempt_at IS NOT NULL AND next_attempt_at <= ?)
                ORDER BY created_at ASC
                LIMIT 1
                """,
                (PENDING, RETRY_SCHEDULED, current),
            ).fetchone()
            if row is None:
                return None
            conn.execute(
                """
                UPDATE outbox
                SET status = ?, lease_expires_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (IN_PROGRESS, lease_expires, current, row["id"]),
            )
            return conn.execute("SELECT * FROM outbox WHERE id = ?", (row["id"],)).fetchone()

    def record_attempt(self, outbox_id: int, result: DeliveryResult) -> int:
        with self.connect() as conn:
            conn.execute(
                """
                INSERT INTO delivery_attempts
                    (outbox_id, attempted_at, success, retryable, terminal, status_code, response_body, error)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    outbox_id,
                    iso(utc_now()),
                    int(result.success),
                    int(result.retryable),
                    int(result.terminal),
                    result.status_code,
                    result.response_body,
                    result.error,
                ),
            )
            row = conn.execute("UPDATE outbox SET attempts = attempts + 1 WHERE id = ?", (outbox_id,))
            attempts = conn.execute("SELECT attempts FROM outbox WHERE id = ?", (outbox_id,)).fetchone()
            if attempts is None or row.rowcount != 1:
                raise ValueError(f"outbox row not found: {outbox_id}")
            return int(attempts["attempts"])

    def mark_delivered(self, outbox_id: int) -> None:
        now = iso(utc_now())
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE outbox
                SET status = ?, lease_expires_at = NULL, last_error = NULL, updated_at = ?, delivered_at = ?
                WHERE id = ?
                """,
                (DELIVERED, now, now, outbox_id),
            )

    def schedule_retry(self, outbox_id: int, *, next_attempt_at: datetime, error: str | None) -> None:
        now = iso(utc_now())
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE outbox
                SET status = ?, next_attempt_at = ?, lease_expires_at = NULL, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (RETRY_SCHEDULED, iso(next_attempt_at), error, now, outbox_id),
            )

    def mark_failed_terminal(self, outbox_id: int, *, error: str | None) -> None:
        now = iso(utc_now())
        with self.connect() as conn:
            conn.execute(
                """
                UPDATE outbox
                SET status = ?, lease_expires_at = NULL, last_error = ?, updated_at = ?
                WHERE id = ?
                """,
                (FAILED_TERMINAL, error, now, outbox_id),
            )

    def list_outbox(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM outbox ORDER BY id").fetchall()
            return [dict(row) for row in rows]

    def list_attempts(self) -> list[dict[str, Any]]:
        with self.connect() as conn:
            rows = conn.execute("SELECT * FROM delivery_attempts ORDER BY id").fetchall()
            return [dict(row) for row in rows]

    def ready(self) -> bool:
        with self.connect() as conn:
            conn.execute("SELECT 1").fetchone()
        return True
