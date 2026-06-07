"""FastAPI application entry point for EVA.

Wires the routers, configures logging, and manages startup/shutdown
lifecycle for the database engine and observability clients.
"""

import logging
import time
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import dispose_engine, get_db_session


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise and release shared resources around the app lifetime."""

    settings = get_settings()
    # Initialise observability, vector store clients, etc. here in later sprints.
    app.state.settings = settings

    # ── Structured logging ──────────────────────────────────────────────
    processors = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
    ]
    if settings.environment != "development":
        processors.append(structlog.processors.JSONRenderer())
    else:
        processors.append(structlog.dev.ConsoleRenderer())
    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
    )
    log = structlog.get_logger()
    log.info(
        "EVA backend starting",
        environment=settings.environment,
        cors_origins=settings.cors_origins,
    )

    try:
        yield
    finally:
        await dispose_engine()


def create_app() -> FastAPI:
    """Application factory used by `uvicorn app.main:app`."""

    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_log(request, call_next):
        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)
        structlog.get_logger().info(
            "request",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
        )
        return response

    @app.get("/health", tags=["meta"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.environment}

    @app.get("/ready", tags=["meta"])
    async def ready(session: AsyncSession = Depends(get_db_session)) -> dict:
        try:
            await session.execute(text("SELECT 1"))
            result = await session.execute(
                text("SELECT extname FROM pg_extension WHERE extname='vector'")
            )
            vector_ok = result.scalar() == "vector"
        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail={"status": "not ready", "db": False, "vector": False},
            ) from e
        if not vector_ok:
            raise HTTPException(
                status_code=503,
                detail={"status": "not ready", "db": True, "vector": False},
            )
        return {"status": "ready", "db": True, "vector": True}

    return app


app = create_app()
