"""Auth router — Google OAuth login and callback.

Mounted at ``/api/v1/auth``.  Provides:
- ``GET /login/google`` — redirects to Google's OAuth consent screen.
- ``GET /callback/google`` — exchanges auth code, syncs customer, issues JWT.
"""

from authlib.integrations.starlette_client import OAuth
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from app.config import get_settings
from app.core.security import create_access_token
from app.db import get_db_session
from app.db.models import Customer  # noqa: TC001

auth_router = APIRouter(prefix="/api/v1/auth", tags=["Auth"])


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
        settings.google_redirect_uri,
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
    4. Issue a short-lived JWT.
    5. Redirect to the frontend with the token.
    """
    oauth = _get_oauth(request)

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

    jwt_token = create_access_token(
        data={"sub": str(customer.id), "email": customer.email},
    )

    # Redirect to the frontend with the JWT
    frontend_callback_url = (
        f"{settings.frontend_url}/auth/callback?token={jwt_token}"
    )
    return RedirectResponse(url=frontend_callback_url)
