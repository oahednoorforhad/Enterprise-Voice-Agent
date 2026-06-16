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


class SubscriptionStatus(BaseModel):
    """Subscription details for a customer (returned by get_subscription_status)."""

    id: UUID
    plan: str
    status: str
    current_period_start: datetime | None = None
    current_period_end: datetime | None = None
