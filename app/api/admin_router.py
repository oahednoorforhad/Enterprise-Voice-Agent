"""Admin router — protected admin operations.

Mounted at ``/api/v1/admin``.
"""

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import get_db_session
from app.db.models import Customer

admin_router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


class SetRealUserRequest(BaseModel):
    email: str


@admin_router.post("/set-real-user")
async def set_real_user(
    body: SetRealUserRequest,
    x_admin_secret: str | None = Header(default=None),
    session: AsyncSession = Depends(get_db_session),
) -> dict:
    """Promote a customer from demo to real user.

    Requires the ``X-Admin-Secret`` header to match ``settings.admin_secret_key``.
    Sets ``Customer.is_demo = False`` for the given email.
    """
    settings = get_settings()

    if not x_admin_secret or x_admin_secret != settings.admin_secret_key:
        raise HTTPException(status_code=403, detail="Invalid admin secret")

    result = await session.execute(
        select(Customer).where(Customer.email == body.email)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise HTTPException(status_code=404, detail=f"Customer {body.email!r} not found")

    customer.is_demo = False
    session.add(customer)
    await session.commit()

    return {"email": body.email, "is_demo": False}
