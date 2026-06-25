"""Langfuse tracing and metrics emission.

Provides a global Langfuse client initialised from settings during the
FastAPI lifespan, plus a shutdown helper to flush pending traces.

All initialisation is wrapped in try/except so missing or invalid
credentials never crash the application — the ``@observe()`` decorator
silently becomes a no-op when the global client is ``None``.

Langfuse v4 note: ``@observe()`` resolves its client via
``LangfuseResourceManager._instances``, which is populated when a
``Langfuse(public_key=..., secret_key=...)`` object is constructed with
valid (non-empty) credentials.  Constructing the client here is therefore
sufficient — no additional wiring is required.
"""

from __future__ import annotations

from typing import Any

import structlog
from langfuse import Langfuse as _Langfuse

logger = structlog.get_logger(__name__)

_langfuse_instance: _Langfuse | None = None


def init_langfuse(
    public_key: str,
    secret_key: str,
    host: str = "https://cloud.langfuse.com",
    base_url: str = "",
    **kwargs: Any,
) -> _Langfuse | None:
    """Create and register the global Langfuse client.

    Once called, ``@observe()`` decorators in other modules automatically
    pick up this instance and start emitting traces (Langfuse v4 singleton
    registry via ``LangfuseResourceManager._instances``).

    Returns ``None`` if initialisation fails (bad credentials, network
    error, etc.) — callers should tolerate ``None`` gracefully.
    """
    global _langfuse_instance  # noqa: PLW0603
    try:
        resolved_url = base_url or host
        _langfuse_instance = _Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            base_url=resolved_url,
            **kwargs,
        )
        logger.info(
            "langfuse initialized",
            key_prefix=public_key[:15] + "..." if public_key else "",
            base_url=resolved_url,
        )
        return _langfuse_instance
    except Exception as exc:  # noqa: BLE001
        logger.warning("langfuse init failed", error=str(exc))
        _langfuse_instance = None
        return None


def get_langfuse() -> _Langfuse | None:
    """Return the global Langfuse client, if initialised."""
    return _langfuse_instance


def shutdown_langfuse() -> None:
    """Flush any pending traces and release the client."""
    global _langfuse_instance  # noqa: PLW0603
    if _langfuse_instance is not None:
        try:
            _langfuse_instance.flush()
        except Exception as exc:  # noqa: BLE001
            logger.warning("langfuse flush during shutdown failed", error=str(exc))
        _langfuse_instance = None
