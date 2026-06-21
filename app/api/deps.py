"""FastAPI dependency stubs. Sprint 1: mock-only. Sprint 2 will implement real auth."""

from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer
from fastapi.security.http import HTTPAuthorizationCredentials

from app.config import get_settings
from app.core.llm_client import LLMClient
from app.core.security import verify_token

_security_scheme = HTTPBearer(auto_error=False)


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_security_scheme),
) -> dict:
    """Resolve the authenticated user from the ``Authorization`` header.

    Behaviour
    ---------
    * **Mock mode** (``MOCK_AUTH_ENABLED=true``) **+ no token**:
      return a hard-coded mock user dict.
    * **Mock mode + token present** (or **mock disabled**):
      verify the JWT via ``verify_token()`` and return user claims
      (``customer_id`` from ``sub``, ``email``, …).

    Returns
    -------
    dict
        At minimum ``{"customer_id": str, "email": str | None}``.
    """
    settings = get_settings()

    # Support direct invocation (e.g. from tests) where FastAPI DI is not active.
    # When called directly, ``credentials`` receives the raw ``Depends()`` sentinel
    # rather than ``None`` or ``HTTPAuthorizationCredentials``.
    if not isinstance(credentials, (HTTPAuthorizationCredentials, type(None))):
        credentials = None

    # Mock mode with no token → return the dev/test mock user
    if settings.mock_auth_enabled and credentials is None:
        return {
            "customer_id": "mock_001",
            "name": "Mock User",
            "email": "mock@clouddesk.com",
        }

    # All other cases require a token
    if credentials is None:
        raise HTTPException(status_code=401, detail="Authentication required")

    try:
        payload = verify_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    return {
        "customer_id": payload.get("sub", ""),
        "email": payload.get("email"),
    }


async def get_llm_client() -> LLMClient:
    """Return an ``LLMClient`` instance.

    Created as a dependency so tests can override it via
    ``app.dependency_overrides``.
    """
    return LLMClient()
