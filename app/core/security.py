from datetime import datetime, timedelta, timezone

import jwt

from app.config import get_settings


def create_access_token(
    data: dict,
    expires_delta: timedelta | None = None,
) -> str:
    settings = get_settings()
    payload = data.copy()
    if expires_delta is None:
        expires_delta = timedelta(hours=24)
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(
        payload,
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def verify_token(token: str) -> dict:
    settings = get_settings()
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=[settings.jwt_algorithm],
    )
