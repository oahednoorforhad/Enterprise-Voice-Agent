"""Auth router — Google OAuth login and callback.

Mounted at ``/api/v1/auth``.  Provides:
- ``GET /login/google`` — redirects to Google's OAuth consent screen.
- ``GET /callback/google`` — exchanges auth code, syncs customer, sets refresh cookie.
- ``POST /refresh`` — trades the refresh cookie for a short-lived access token.
- ``POST /logout`` — clears the refresh cookie.
"""

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Cookie, Depends, HTTPException, Response
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.config import get_settings
from app.core.security import (
    REFRESH_TOKEN_TTL,
    create_access_token,
    create_refresh_token,
    verify_token,
)
from app.db import get_db_session
from app.db.models import Customer  # noqa: TC001

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])

REFRESH_COOKIE = "eva_refresh"
_COOKIE_PATH = "/api/v1/auth"  # browser only sends it to auth endpoints


def _set_refresh_cookie(response: Response, claims: dict) -> None:
    response.set_cookie(
        REFRESH_COOKIE,
        create_refresh_token(claims),
        max_age=int(REFRESH_TOKEN_TTL.total_seconds()),
        path=_COOKIE_PATH,
        httponly=True,
        secure=get_settings().environment == "production",
        samesite="lax",
    )


def _get_oauth(request: Request) -> OAuth:
    """Create or reuse an OAuth client instance at runtime.

    ``authlib`` stores the client on ``request.app.state.oauth`` so that
    the configuration is shared across requests.
    """
    if not hasattr(request.app.state, "oauth"):
        settings = get_settings()
        oauth = OAuth()
        oauth.register(
            name="google",
            client_id=settings.google_client_id,
            client_secret=settings.google_client_secret,
            server_metadata_url=(
                "https://accounts.google.com/.well-known/openid-configuration"
            ),
            client_kwargs={"scope": "openid email profile"},
        )
        request.app.state.oauth = oauth
    return request.app.state.oauth


@auth_router.get("/login/google")
async def login_google(request: Request):
    """Redirect the user to Google's OAuth consent screen.

    After consent, Google redirects back to ``/callback/google`` with
    an authorisation code.
    """
    oauth = _get_oauth(request)
    settings = get_settings()
    return await oauth.google.authorize_redirect(
        request,
        settings.resolved_google_redirect_uri,
    )


@auth_router.get("/callback/google")
async def callback_google(
    request: Request,
    session: AsyncSession = Depends(get_db_session),
):
    """Handle the OAuth callback from Google.

    1. Exchange the authorisation code for an access token.
    2. Fetch userinfo from Google.
    3. Look up an existing customer by email; create one if it doesn't exist.
    4. Set the long-lived refresh token as an httpOnly cookie.
    5. Redirect to the frontend, which calls ``/refresh`` for an access token.
    """
    oauth = _get_oauth(request)
    settings = get_settings()

    token = await oauth.google.authorize_access_token(request)
    if token is None:
        raise HTTPException(status_code=400, detail="OAuth authorisation failed")

    userinfo = token.get("userinfo")
    if userinfo is None:
        raise HTTPException(status_code=400, detail="Failed to fetch user info")

    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name", "")

    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google")

    # Look up existing customer by email
    result = await session.execute(select(Customer).where(Customer.email == email))
    customer = result.scalar_one_or_none()

    if customer is None:
        # Derive company from email domain
        company = email.split("@")[-1] if "@" in email else None

        customer = Customer(
            name=name,
            email=email,
            google_id=google_id,
            company=company,
            plan_tier="free",
            is_active=True,
            is_demo=True,
        )
        session.add(customer)
        await session.flush()
        await session.refresh(customer)
    else:
        # Update google_id if not already set (link accounts)
        if customer.google_id is None and google_id:
            customer.google_id = google_id
            session.add(customer)
            await session.flush()

    # No token in the URL: it would land in browser history and access logs
    response = RedirectResponse(url=f"{settings.frontend_url}/auth/callback")
    _set_refresh_cookie(response, {"sub": str(customer.id), "email": customer.email})
    return response


@auth_router.post("/refresh")
async def refresh(
    request: Request,
    response: Response,
    eva_refresh: str | None = Cookie(default=None),
) -> dict:
    """Exchange the refresh cookie for a new access token (and rotate the cookie)."""
    # CSRF: SameSite=Lax already blocks cross-site POSTs; also reject foreign Origins
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().cors_origins:
        raise HTTPException(status_code=403, detail="Origin not allowed")

    try:
        payload = verify_token(eva_refresh or "", expected_type="refresh")
    except Exception:
        response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)
        raise HTTPException(status_code=401, detail="Session expired") from None

    claims = {"sub": payload["sub"], "email": payload.get("email")}
    _set_refresh_cookie(response, claims)
    return {"access_token": create_access_token(claims), "token_type": "bearer"}


@auth_router.post("/logout", status_code=204)
async def logout(response: Response) -> None:
    response.delete_cookie(REFRESH_COOKIE, path=_COOKIE_PATH)
