"""Pydantic response model for the Analytics tool family."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class UsageAnalyticModel(BaseModel):
    """Usage analytics record returned by get_usage_analytics."""

    id: UUID
    customer_id: UUID
    metric_name: str
    metric_value: float
    period_start: datetime
    period_end: datetime | None = None
