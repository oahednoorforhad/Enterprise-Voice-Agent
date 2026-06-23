"""Pydantic response models for the Customer tool family."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CustomerProfile(BaseModel):
    """Public profile of a customer (returned by get_customer_profile)."""

    id: UUID
    name: str
    email: str
    phone: str | None = None
    is_active: bool
    # Frontend display fields
    created_at: datetime | None = None
    tier: str | None = None
    status: str | None = None
    active_scenario: str | None = None


class SubscriptionStatus(BaseModel):
    """Subscription details for a customer (returned by get_subscription_status)."""

    id: UUID
    plan: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
    # Frontend display fields
    customer_id: UUID | None = None
    start_date: datetime | None = None
    end_date: datetime | None = None
    auto_renew: bool = True
    amount: float | None = None
    currency: str = "USD"
