from __future__ import annotations

import os
from dataclasses import dataclass

from service.infrastructure.secrets import read_secret


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    service_name: str = "feishu-repo-broadcast-service"
    database_path: str = "data/service.db"
    delivery_mode: str = "dry_run"
    worker_enabled: bool = True
    worker_interval_seconds: float = 2.0
    lease_timeout_seconds: int = 300
    max_delivery_attempts: int = 5
    log_level: str = "INFO"
    codeup_secret_token: str | None = None
    gitlab_secret_token: str | None = None
    feishu_webhook_url: str | None = None
    feishu_signing_secret: str | None = None

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            service_name=os.getenv("SERVICE_NAME", cls.service_name),
            database_path=os.getenv("DATABASE_PATH", cls.database_path),
            delivery_mode=os.getenv("DELIVERY_MODE", cls.delivery_mode).strip().lower(),
            worker_enabled=_bool_env("WORKER_ENABLED", cls.worker_enabled),
            worker_interval_seconds=float(os.getenv("WORKER_INTERVAL_SECONDS", cls.worker_interval_seconds)),
            lease_timeout_seconds=int(os.getenv("LEASE_TIMEOUT_SECONDS", cls.lease_timeout_seconds)),
            max_delivery_attempts=int(os.getenv("MAX_DELIVERY_ATTEMPTS", cls.max_delivery_attempts)),
            log_level=os.getenv("LOG_LEVEL", cls.log_level),
            codeup_secret_token=read_secret("CODEUP_SECRET_TOKEN"),
            gitlab_secret_token=read_secret("GITLAB_SECRET_TOKEN"),
            feishu_webhook_url=read_secret("FEISHU_WEBHOOK_URL"),
            feishu_signing_secret=read_secret("FEISHU_SIGNING_SECRET"),
        )

    @property
    def dry_run(self) -> bool:
        return self.delivery_mode != "live"

