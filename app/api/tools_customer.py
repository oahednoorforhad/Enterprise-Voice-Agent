"""Customer tool endpoints — wrapped as GET routes returning ToolResult.

All routes are mounted under ``/api/v1/tools/customer`` and return a uniform
``ToolResult`` JSON shape for LLM consumption.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.tools import ToolResult
from app.tools.customer.functions import (
    get_customer_profile,
    get_subscription_status,
)

router = APIRouter(prefix="/customer", tags=["Customer Tools"])


@router.get("/profile", response_model=ToolResult)
async def get_profile_endpoint(
    customer_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """Return the profile for a given customer."""
    result = await get_customer_profile(session, customer_id)
    return ToolResult.ok(result)


@router.get("/subscription", response_model=ToolResult)
async def get_subscription_endpoint(
    customer_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """Return the subscription status for a given customer."""
    result = await get_subscription_status(session, customer_id)
    return ToolResult.ok(result)
