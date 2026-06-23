"""Pydantic response models for the Billing tool family."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class BillingRecordModel(BaseModel):
    """Billing record returned by get_billing_history."""

    model_config = ConfigDict(coerce_numbers_to_str=False)

    id: UUID
    customer_id: UUID
    amount: float
    currency: str
    status: str  # paid, pending, overdue, refunded
    description: str | None = None
    created_at: datetime
    paid_at: datetime | None = None
    due_date: datetime | None = None
    # Frontend display field: most relevant date for the record
    date: datetime | None = None
