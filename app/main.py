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
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.chat_router import chat_router
from app.api.tools_router import tools_router
from app.api.voice_router import voice_router
from app.config import get_settings
from app.core.exceptions import DomainException
from app.db import dispose_engine, get_db_session
from app.observability import init_langfuse, shutdown_langfuse
from app.schemas.tools import ToolResult


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Initialise and release shared resources around the app lifetime."""

    settings = get_settings()
    app.state.settings = settings

    # ── Langfuse Observability ──────────────────────────────────────────
    if settings.langfuse_public_key and settings.langfuse_secret_key:
        try:
            init_langfuse(
                public_key=settings.langfuse_public_key,
                secret_key=settings.langfuse_secret_key,
                # LANGFUSE_BASE_URL takes precedence; fall back to langfuse_host
                base_url=settings.langfuse_base_url or settings.langfuse_host,
            )
        except Exception:  # noqa: BLE001
            pass  # silently bypass if init fails
    # Keys missing → silently skip (no warning spam).

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
        shutdown_langfuse()
        await dispose_engine()


def create_app() -> FastAPI:
    """Application factory used by `uvicorn app.main:app`."""

    settings = get_settings()

    # Stdlib `logging.getLogger(__name__)` calls throughout the codebase
    # (voice session, tool dispatch, etc.) are a separate system from the
    # structlog setup in lifespan() above — without this, the root logger
    # has no handler and INFO-level logs are silently dropped.
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        lifespan=lifespan,
    )

    # request_log is registered first so it becomes innermost (CORS wraps it).
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

    # CORSMiddleware added last = outermost layer, so CORS headers are always
    # present even when inner handlers return error responses.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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

    # ── Global exception handlers ──────────────────────────────────────
    @app.exception_handler(DomainException)
    async def domain_exception_handler(
        request, exc: DomainException
    ) -> JSONResponse:
        """Catch any ``DomainException`` and return it as a 200 ``ToolResult``.

        LLM-callable tools always return ``ToolResult(success=False, error=...)``
        wrapped in a 200 OK so the LLM never sees a 4xx/5xx and can always
        interpret the response as a structured result.
        """
        result = ToolResult.fail(str(exc))
        return JSONResponse(
            status_code=200,
            content=result.model_dump(),
        )

    # ── Routers ────────────────────────────────────────────────────────
    app.include_router(tools_router)
    app.include_router(chat_router)
    app.include_router(voice_router)

    return app


app = create_app()
