"""FastAPI dependency stubs. Sprint 1: mock-only. Sprint 2 will implement real auth."""

from fastapi import HTTPException

from app.config import get_settings


async def get_current_user() -> dict:
    settings = get_settings()
    if not settings.mock_auth_enabled:
        raise HTTPException(status_code=401, detail="Authentication not configured")
    return {"customer_id": "mock_001", "name": "Mock User", "email": "mock@clouddesk.com"}
