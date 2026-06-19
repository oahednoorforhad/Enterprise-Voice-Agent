"""Pydantic response models for the Billing tool family."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class BillingRecordModel(BaseModel):
    """Billing record returned by get_billing_history."""

    id: UUID
    customer_id: UUID
    amount: Decimal
    currency: str
    status: str  # paid, pending, overdue, refunded
    description: str | None = None
    created_at: datetime
    paid_at: datetime | None = None
    due_date: datetime | None = None
    # Frontend display field: most relevant date for the record
    date: datetime | None = None
