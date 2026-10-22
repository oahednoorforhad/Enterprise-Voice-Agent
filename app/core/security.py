from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings

# Short-lived bearer token kept in browser memory; the long-lived refresh
# token lives in an httpOnly cookie and is only accepted by /auth/refresh.
ACCESS_TOKEN_TTL = timedelta(minutes=15)
REFRESH_TOKEN_TTL = timedelta(days=14)


def _encode(data: dict, token_type: str, expires_delta: timedelta) -> str:
    settings = get_settings()
    payload = data.copy()
    payload["type"] = token_type
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    return _encode(data, "access", expires_delta or ACCESS_TOKEN_TTL)


def create_refresh_token(data: dict) -> str:
    # ponytail: stateless refresh tokens can't be revoked server-side before
    # expiry; add a token_version column on customers if remote logout is needed.
    return _encode(data, "refresh", REFRESH_TOKEN_TTL)


def verify_token(token: str, expected_type: str = "access") -> dict:
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
    # Tokens issued before typing existed carry no "type"; they were access tokens.
    if payload.get("type", "access") != expected_type:
        raise jwt.InvalidTokenError(f"expected {expected_type} token")
    return payload
