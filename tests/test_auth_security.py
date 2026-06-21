"""Tests for app.core.security — JWT creation and verification."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

import jwt
import pytest

from app.config import Settings
from app.core.security import create_access_token, verify_token


def _test_settings(**overrides: object) -> Settings:
    """Return a Settings instance with known test values."""
    base = dict(
        jwt_secret="test_secret_for_testing",
        jwt_algorithm="HS256",
        mock_auth_enabled=True,
    )
    base.update(overrides)
    return Settings(**base)


class TestCreateAccessToken:
    """Tests for create_access_token()."""

    def test_returns_jwt_string(self) -> None:
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            token = create_access_token(data={"sub": "test_user"})
        assert isinstance(token, str)
        # JWT consists of three base64url-encoded segments
        assert len(token.split(".")) == 3

    def test_custom_expiry(self) -> None:
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            token = create_access_token(
                data={"sub": "test_user"},
                expires_delta=timedelta(hours=1),
            )
        # Verify the token can be decoded back
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            payload = verify_token(token)
        assert payload["sub"] == "test_user"

    def test_embeds_custom_claims(self) -> None:
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            token = create_access_token(
                data={"sub": "cust_abc", "email": "a@b.com", "role": "admin"},
            )
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            payload = verify_token(token)
        assert payload["sub"] == "cust_abc"
        assert payload["email"] == "a@b.com"
        assert payload["role"] == "admin"


class TestVerifyToken:
    """Tests for verify_token()."""

    def test_valid_token_returns_claims(self) -> None:
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            token = create_access_token(
                data={"sub": "cust_123", "email": "a@b.com"},
            )
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            payload = verify_token(token)
        assert payload["sub"] == "cust_123"
        assert payload["email"] == "a@b.com"

    def test_expired_token_raises(self) -> None:
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            token = create_access_token(
                data={"sub": "test_user"},
                expires_delta=timedelta(seconds=-1),
            )
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            with pytest.raises(jwt.ExpiredSignatureError):
                verify_token(token)

    def test_invalid_signature_raises(self) -> None:
        # Create a token with one secret, verify with a different one
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            token = create_access_token(data={"sub": "test_user"})
        with patch(
            "app.core.security.get_settings",
            return_value=_test_settings(jwt_secret="different_secret"),
        ):
            with pytest.raises(jwt.InvalidSignatureError):
                verify_token(token)

    def test_malformed_token_raises(self) -> None:
        with patch("app.core.security.get_settings", return_value=_test_settings()):
            with pytest.raises(jwt.DecodeError):
                verify_token("not-a-jwt-at-all")
