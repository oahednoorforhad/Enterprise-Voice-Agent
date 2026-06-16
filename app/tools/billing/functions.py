"""Async query functions for the Billing tool family."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import BillingRecord
from app.tools.billing.models import BillingRecordModel


async def get_billing_history(
    session: AsyncSession, customer_id: UUID
) -> list[BillingRecordModel]:
    """Get billing history with business-aware recency.

    Rules:
    - ALL pending and overdue records are returned (regardless of age).
    - paid / refunded records are returned only if paid_at >= NOW() - 90 days.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=90)

    result = await session.execute(
        select(BillingRecord).where(
            BillingRecord.customer_id == customer_id,
            or_(
                BillingRecord.status.in_(["pending", "overdue"]),
                and_(
                    BillingRecord.status.in_(["paid", "refunded"]),
                    BillingRecord.paid_at >= cutoff,
                ),
            ),
        ).order_by(BillingRecord.created_at.desc())
    )
    rows = result.scalars().all()
    return [
        BillingRecordModel(
            id=r.id,
            customer_id=r.customer_id,
            amount=r.amount,
            currency=r.currency,
            status=r.status,
            description=r.description,
            created_at=r.created_at,
            paid_at=r.paid_at,
            due_date=r.due_date,
        )
        for r in rows
    ]
