"""Billing tool endpoints — wrapped as GET routes returning ToolResult.

All routes are mounted under ``/api/v1/tools/billing`` and return a uniform
``ToolResult`` JSON shape for LLM consumption.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.tools import ToolResult
from app.tools.billing.functions import get_billing_history

router = APIRouter(prefix="/billing", tags=["Billing Tools"])


@router.get("/history", response_model=ToolResult)
async def get_billing_history_endpoint(
    customer_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """Return the billing history for a given customer."""
    result = await get_billing_history(session, customer_id)
    return ToolResult.ok(result)


@router.get("/refunds", response_model=ToolResult)
async def get_refunds_endpoint(
    customer_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """Return refunded billing records for a given customer."""
    records = await get_billing_history(session, customer_id)
    refunded = [r for r in records if r.status == "refunded"]
    return ToolResult.ok(refunded)
