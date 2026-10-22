"""Refresh-cookie session flow: /auth/refresh, /auth/logout, token typing."""

import pytest
from fastapi import HTTPException
from fastapi.security.http import HTTPAuthorizationCredentials
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.core.security import create_access_token, create_refresh_token, verify_token
from app.main import app

client = TestClient(app)
CLAIMS = {"sub": "cust_123", "email": "a@b.com"}


def _refresh(cookie: str | None = None, origin: str | None = None):
    headers = {}
    if cookie is not None:
        headers["Cookie"] = f"eva_refresh={cookie}"
    if origin is not None:
        headers["Origin"] = origin
    return client.post("/api/v1/auth/refresh", headers=headers)


def test_refresh_without_cookie_is_401():
    assert _refresh().status_code == 401


def test_refresh_issues_access_token_and_rotates_cookie():
    res = _refresh(create_refresh_token(CLAIMS))
    assert res.status_code == 200
    payload = verify_token(res.json()["access_token"])
    assert payload["sub"] == "cust_123" and payload["type"] == "access"
    set_cookie = res.headers["set-cookie"]
    assert "eva_refresh=" in set_cookie
    assert "HttpOnly" in set_cookie and "Path=/api/v1/auth" in set_cookie
    assert "samesite=lax" in set_cookie.lower()


def test_access_token_cannot_be_used_as_refresh_cookie():
    assert _refresh(create_access_token(CLAIMS)).status_code == 401


async def test_refresh_token_cannot_be_used_as_bearer():
    creds = HTTPAuthorizationCredentials(
        scheme="Bearer", credentials=create_refresh_token(CLAIMS)
    )
    with pytest.raises(HTTPException) as exc:
        await get_current_user(creds)
    assert exc.value.status_code == 401


def test_foreign_origin_is_rejected():
    res = _refresh(create_refresh_token(CLAIMS), origin="https://evil.example")
    assert res.status_code == 403


def test_logout_clears_cookie():
    res = client.post("/api/v1/auth/logout")
    assert res.status_code == 204
    assert 'eva_refresh=""' in res.headers["set-cookie"]
    assert "Max-Age=0" in res.headers["set-cookie"]


def test_failed_refresh_clears_the_cookie():
    res = _refresh("garbage")
    assert res.status_code == 401
    assert 'eva_refresh=""' in res.headers["set-cookie"]
    assert "Max-Age=0" in res.headers["set-cookie"]
