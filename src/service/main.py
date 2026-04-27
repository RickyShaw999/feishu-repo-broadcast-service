from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from service.config import Settings
from service.domain.retry_policy import RetryPolicy
from service.http.routes import health, webhooks_codeup, webhooks_gitlab
from service.infrastructure.feishu_client import FeishuClient
from service.infrastructure.sqlite_store import SQLiteStore
from service.logging import configure_logging
from service.worker.retry_loop import DeliveryWorker


def create_app(
    *,
    settings: Settings | None = None,
    store: SQLiteStore | None = None,
    feishu_client: FeishuClient | None = None,
) -> FastAPI:
    resolved_settings = settings or Settings.from_env()
    configure_logging(resolved_settings.log_level)
    resolved_store = store or SQLiteStore(resolved_settings.database_path)
    client = feishu_client or FeishuClient(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        resolved_store.initialize()
        worker = DeliveryWorker(
            resolved_store,
            client,
            lease_seconds=resolved_settings.lease_timeout_seconds,
            interval_seconds=resolved_settings.worker_interval_seconds,
            retry_policy=RetryPolicy(max_attempts=resolved_settings.max_delivery_attempts),
        )
        app.state.worker = worker
        task: asyncio.Task[None] | None = None
        if resolved_settings.worker_enabled:
            task = asyncio.create_task(worker.run_forever())
        try:
            yield
        finally:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass

    app = FastAPI(title=resolved_settings.service_name, version="0.1.0", lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.store = resolved_store
    app.include_router(health.router)
    app.include_router(webhooks_codeup.router)
    app.include_router(webhooks_gitlab.router)
    return app


app = create_app()

