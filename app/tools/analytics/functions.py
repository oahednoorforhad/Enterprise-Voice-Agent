"""Analytics query functions — get_usage_analytics."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import UsageAnalytic
from app.tools.analytics.models import UsageAnalyticModel


async def get_usage_analytics(
    session: AsyncSession,
    customer_id: UUID,
    metric_name: str | None = None,
) -> list[UsageAnalyticModel]:
    """Get usage analytics filtered by customer_id and time window.

    Recency Logic: Filter by period_start >= NOW() - 90 days.
    Optional: Filter by metric_name if provided.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=90)

    query = select(UsageAnalytic).where(
        UsageAnalytic.customer_id == customer_id,
        UsageAnalytic.period_start >= cutoff,
    )

    if metric_name:
        query = query.where(UsageAnalytic.metric_name == metric_name)

    query = query.order_by(UsageAnalytic.period_start.desc())

    result = await session.execute(query)
    rows = result.scalars().all()

    return [
        UsageAnalyticModel(
            id=r.id,
            customer_id=r.customer_id,
            metric_name=r.metric_name,
            metric_value=r.metric_value,
            period_start=r.period_start,
            period_end=r.period_end,
        )
        for r in rows
    ]
