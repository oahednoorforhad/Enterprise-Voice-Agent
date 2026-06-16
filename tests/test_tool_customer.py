"""Tests for the Customer tool family."""

import uuid
from datetime import UTC, datetime

import pytest

from app.core.exceptions import CustomerNotFoundError
from app.db.models import Customer, Subscription
from app.tools.customer.functions import (
    get_customer_profile,
    get_subscription_status,
)
from app.tools.customer.models import CustomerProfile, SubscriptionStatus

pytestmark = pytest.mark.asyncio


class TestGetCustomerProfile:
    """Tests for get_customer_profile."""

    async def test_returns_profile_when_found(self, async_session):
        """Insert a customer, fetch profile, verify shape."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Alice",
                email=f"alice_{customer_id}@example.com",
                phone="+8801700000001",
                is_active=True,
            )
        )
        await async_session.commit()

        profile = await get_customer_profile(async_session, customer_id)

        assert isinstance(profile, CustomerProfile)
        assert profile.id == customer_id
        assert profile.name == "Alice"
        assert profile.email == f"alice_{customer_id}@example.com"
        assert profile.phone == "+8801700000001"
        assert profile.is_active is True

    async def test_raises_when_missing(self, async_session):
        """Query a non-existent customer -> CustomerNotFoundError."""
        fake_id = uuid.uuid4()
        with pytest.raises(CustomerNotFoundError) as exc:
            await get_customer_profile(async_session, fake_id)
        assert str(fake_id) in str(exc.value)


class TestGetSubscriptionStatus:
    """Tests for get_subscription_status."""

    async def test_returns_status_when_found(self, async_session):
        """Insert a customer + subscription, fetch, verify shape."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Bob",
                email=f"bob_{customer_id}@example.com",
                is_active=True,
            )
        )
        await async_session.flush()

        sub_id = uuid.uuid4()
        now = datetime.now(UTC)
        async_session.add(
            Subscription(
                id=sub_id,
                customer_id=customer_id,
                plan_name="premium",
                status="active",
                start_date=now,
                end_date=None,
            )
        )
        await async_session.commit()

        result = await get_subscription_status(async_session, customer_id)

        assert isinstance(result, SubscriptionStatus)
        assert result.id == sub_id
        assert result.plan == "premium"
        assert result.status == "active"
        assert result.current_period_start == now
        assert result.current_period_end is None

    async def test_raises_when_no_subscription(self, async_session):
        """Customer exists but has no subscription -> CustomerNotFoundError."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Charlie",
                email=f"charlie_{customer_id}@example.com",
                is_active=True,
            )
        )
        await async_session.commit()

        with pytest.raises(CustomerNotFoundError) as exc:
            await get_subscription_status(async_session, customer_id)
        assert str(customer_id) in str(exc.value)

    async def test_raises_when_customer_missing(self, async_session):
        """No customer exists at all -> CustomerNotFoundError."""
        fake_id = uuid.uuid4()
        with pytest.raises(CustomerNotFoundError):
            await get_subscription_status(async_session, fake_id)

