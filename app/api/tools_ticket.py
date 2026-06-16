"""Ticket tool API endpoints — GET /api/v1/tools/ticket/list, /ticket/status.

All routes return ``ToolResult`` JSON so the LLM always receives a uniform
response shape.
"""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db_session
from app.schemas.tools import ToolResult
from app.tools.ticket.functions import get_support_tickets, get_ticket_status

router = APIRouter(prefix="/ticket", tags=["Ticket Tools"])


@router.get("/list", response_model=ToolResult)
async def list_tickets_endpoint(
    customer_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """List support tickets for a customer (with recency filtering)."""
    result = await get_support_tickets(session, customer_id)
    return ToolResult.ok(result)


@router.get("/status", response_model=ToolResult)
async def ticket_status_endpoint(
    customer_id: UUID,
    ticket_id: UUID,
    session: AsyncSession = Depends(get_db_session),
) -> ToolResult:
    """Get a single ticket's status by ticket ID (with customer isolation)."""
    result = await get_ticket_status(session, customer_id, ticket_id)
    return ToolResult.ok(result)
