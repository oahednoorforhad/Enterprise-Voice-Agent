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


class TicketPreview(BaseModel):
    """Pre-creation preview returned when confirmed=False."""

    title: str
    description: str | None = None
    category: str
    priority: str
    valid: bool = True
    validation_message: str | None = None


class TicketAnalysis(BaseModel):
    """Structured LLM output for ticket validation and field extraction."""

    title: str
    description: str | None = None
    category: str
    priority: str = "medium"
    is_specific_and_actionable: bool = True
    is_not_abusive: bool = True
    is_not_in_kb: bool = True
    is_product_related: bool = True
    validation_message: str | None = None
