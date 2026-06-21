"""Tests for app.api.deps — FastAPI dependency injection helpers."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import pytest
from fastapi import HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials

from app.api.deps import get_current_user
from app.config import Settings
from app.core.security import create_access_token


def _test_settings(**overrides: object) -> Settings:
    """Return a Settings instance with known test values."""
    base = dict(
        jwt_secret="test_secret_for_testing",
        jwt_algorithm="HS256",
        mock_auth_enabled=True,
    )
    base.update(overrides)
    return Settings(**base)


class TestGetCurrentUser:
    """Tests for get_current_user()."""

    async def test_mock_mode_no_token_returns_mock_user(self) -> None:
        """With MOCK_AUTH_ENABLED=true and no credentials, return the mock user."""
        with patch("app.api.deps.get_settings", return_value=_test_settings(mock_auth_enabled=True)):
            user = await get_current_user()
        assert user["customer_id"] == "mock_001"
        assert user["email"] == "mock@clouddesk.com"
        assert user["name"] == "Mock User"

    async def test_mock_mode_with_valid_token_returns_token_user(self) -> None:
        """Even in mock mode, if a valid token is provided, verify and return claims."""
        with patch("app.api.deps.get_settings", return_value=_test_settings(mock_auth_enabled=True)):
            token = create_access_token(
                data={"sub": "token_user", "email": "token@test.com"},
            )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)
        with patch("app.api.deps.get_settings", return_value=_test_settings(mock_auth_enabled=True)):
            user = await get_current_user(credentials=creds)
        assert user["customer_id"] == "token_user"
        assert user["email"] == "token@test.com"

    async def test_no_mock_no_token_raises_401(self) -> None:
        """With MOCK_AUTH_ENABLED=false and no credentials, raise 401."""
        with patch("app.api.deps.get_settings", return_value=_test_settings(mock_auth_enabled=False)):
            with pytest.raises(HTTPException) as exc:
                await get_current_user()
        assert exc.value.status_code == 401
        assert "Authentication required" in exc.value.detail

    async def test_invalid_token_raises_401(self) -> None:
        """With a malformed / invalid token, raise 401."""
        creds = HTTPAuthorizationCredentials(
            scheme="Bearer",
            credentials="totally.invalid.token",
        )
        with patch("app.api.deps.get_settings", return_value=_test_settings(mock_auth_enabled=False)):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(credentials=creds)
        assert exc.value.status_code == 401
        assert "Invalid or expired token" in exc.value.detail

    async def test_expired_token_raises_401(self) -> None:
        """With an expired token, raise 401."""
        with patch("app.api.deps.get_settings", return_value=_test_settings()):
            expired_token = create_access_token(
                data={"sub": "expired_user"},
                expires_delta=timedelta(seconds=-1),
            )
        creds = HTTPAuthorizationCredentials(scheme="Bearer", credentials=expired_token)
        with patch("app.api.deps.get_settings", return_value=_test_settings(mock_auth_enabled=False)):
            with pytest.raises(HTTPException) as exc:
                await get_current_user(credentials=creds)
        assert exc.value.status_code == 401
        assert "Invalid or expired token" in exc.value.detail
