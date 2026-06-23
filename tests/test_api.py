"""API-level tests for the Sprint-1 FastAPI application.

Covers the health check, readiness probe (with a live database connection),
and the mock-authentication dependency stub.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app


def test_health_returns_ok() -> None:
    """Smoke test: GET /health returns 200 with status and env."""
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert "env" in body


def test_ready_returns_200_when_db_up() -> None:
    """GET /ready returns 200 when the database and vector extension are live.

    ``setup_db`` (session-scoped autouse) has overridden DATABASE_URL to
    point at the testcontainers Postgres instance and run Alembic
    migrations, so the /ready endpoint should report everything healthy.
    """
    client = TestClient(app)
    response = client.get("/ready")
    assert response.status_code == 200, (
        f"Expected 200, got {response.status_code}: {response.text}"
    )
    body = response.json()
    assert body["status"] == "ready"
    assert body["db"] is True
    assert body["vector"] is True


async def test_auth_stub_exists(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mock ``get_current_user`` dependency returns a dict with customer_id.

    This test temporarily enables ``MOCK_AUTH_ENABLED`` so the dependency
    returns the hard-coded stub user without requiring a real JWT.
    """
    monkeypatch.setenv("MOCK_AUTH_ENABLED", "true")
    from app.config import get_settings

    get_settings.cache_clear()

    from app.api.deps import get_current_user

    user = await get_current_user()
    assert isinstance(user, dict)
    assert "customer_id" in user
    assert user["customer_id"] == "mock_001"

    get_settings.cache_clear()
