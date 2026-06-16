"""FastAPI dependency stubs. Sprint 1: mock-only. Sprint 2 will implement real auth."""

from fastapi import HTTPException

from app.config import get_settings
from app.core.llm_client import LLMClient


async def get_current_user() -> dict:
    settings = get_settings()
    if not settings.mock_auth_enabled:
        raise HTTPException(status_code=401, detail="Authentication not configured")
    return {"customer_id": "mock_001", "name": "Mock User", "email": "mock@clouddesk.com"}


async def get_llm_client() -> LLMClient:
    """Return an ``LLMClient`` instance.

    Created as a dependency so tests can override it via
    ``app.dependency_overrides``.
    """
    return LLMClient()
