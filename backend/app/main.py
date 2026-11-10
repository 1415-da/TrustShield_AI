"""TrustShield AI — FastAPI application entry point."""

from __future__ import annotations

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
    yield


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

