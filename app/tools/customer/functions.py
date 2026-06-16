"""Async query functions for the Customer tool family."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import CustomerNotFoundError
from app.db.models import Customer, Subscription
from app.tools.customer.models import CustomerProfile, SubscriptionStatus


async def get_customer_profile(
    session: AsyncSession, customer_id: UUID
) -> CustomerProfile:
    """Get customer profile by ID.

    Raises ``CustomerNotFoundError`` if no customer exists with the given ID.
    """
    result = await session.execute(
        select(Customer).where(Customer.id == customer_id)
    )
    customer = result.scalar_one_or_none()
    if customer is None:
        raise CustomerNotFoundError(f"Customer {customer_id} not found")

    return CustomerProfile(
        id=customer.id,
        name=customer.name,
        email=customer.email,
        phone=customer.phone,
        is_active=customer.is_active,
    )


async def get_subscription_status(
    session: AsyncSession, customer_id: UUID
) -> SubscriptionStatus:
    """Get subscription by customer_id.

    Raises ``CustomerNotFoundError`` if no subscription is found for the
    given customer.
    """
    result = await session.execute(
        select(Subscription).where(Subscription.customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if sub is None:
        raise CustomerNotFoundError(
            f"No subscription found for customer {customer_id}"
        )

    return SubscriptionStatus(
        id=sub.id,
        plan=sub.plan_name,
        status=sub.status,
        current_period_start=sub.start_date,
        current_period_end=sub.end_date,
    )
