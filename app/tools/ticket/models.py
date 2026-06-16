"""Pydantic response models for the Ticket tool family."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class TicketModel(BaseModel):
    """Support ticket returned by get_support_tickets / get_ticket_status."""

    id: UUID
    customer_id: UUID
    subject: str
    description: str | None = None
    status: str  # open, in_progress, closed, resolved
    priority: str | None = None
    created_at: datetime
    updated_at: datetime
