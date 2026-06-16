"""Async query functions for the Ticket tool family."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import TicketNotFoundError
from app.db.models import SupportTicket
from app.tools.ticket.models import TicketModel


async def get_support_tickets(
    session: AsyncSession, customer_id: UUID
) -> list[TicketModel]:
    """Get support tickets with business-aware recency.

    Rules:
    - ALL open and in_progress tickets are returned (regardless of age).
    - closed/resolved tickets are returned only if
      ``updated_at >= NOW() - 30 days``.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)

    result = await session.execute(
        select(SupportTicket)
        .where(
            SupportTicket.customer_id == customer_id,
            or_(
                SupportTicket.status.in_(["open", "in_progress"]),
                and_(
                    SupportTicket.status.in_(["closed", "resolved"]),
                    SupportTicket.updated_at >= cutoff,
                ),
            ),
        )
        .order_by(SupportTicket.updated_at.desc())
    )
    rows = result.scalars().all()
    return [
        TicketModel(
            id=t.id,
            customer_id=t.customer_id,
            subject=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in rows
    ]


async def get_ticket_status(
    session: AsyncSession, customer_id: UUID, ticket_id: UUID
) -> TicketModel:
    """Get a single ticket by ID.  Enforces customer_id ownership.

    Raises ``TicketNotFoundError`` if the ticket does not exist **or** if it
    belongs to a different customer.
    """
    result = await session.execute(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.customer_id == customer_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise TicketNotFoundError(
            f"Ticket {ticket_id} not found for customer {customer_id}"
        )

    return TicketModel(
        id=ticket.id,
        customer_id=ticket.customer_id,
        subject=ticket.title,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )
