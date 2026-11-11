"""TrustShield AI — FastAPI application entry point."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.router import api_router
from app.core.config import get_settings
from app.core.errors import install_error_handlers
from app.core.logging import RequestContextMiddleware, configure_logging

configure_logging()
settings = get_settings()


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    # Load Presidio/spaCy once at boot rather than on the first employee request.
    from app.guardrails.pii import get_pii_detector

    get_pii_detector()
    loop = asyncio.create_task(_scheduler()) if settings.scheduler_enabled else None
    yield
    if loop:
        loop.cancel()


async def _scheduler() -> None:
    """Minimal in-process scheduler for compliance report schedules (no Celery/Redis at MVP scale)."""
    from app.workers.tasks import run_due_schedules

    while True:
        await asyncio.sleep(settings.scheduler_interval_seconds)
        try:
            await asyncio.to_thread(run_due_schedules)
        except Exception:  # pragma: no cover - logged, never fatal
            logging.getLogger("trustshield.scheduler").exception("scheduled report run failed")


app = FastAPI(
    lifespan=lifespan,
    title="TrustShield AI",
    version="0.1.0",
    description="Enterprise AI governance gateway: input/output guardrails, policy engine, human review, audit trail.",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url=None,
)
app.add_middleware(RequestContextMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-TrustShield-App-Key"],
    expose_headers=["X-Request-ID"],
)
install_error_handlers(app)
app.include_router(api_router)

