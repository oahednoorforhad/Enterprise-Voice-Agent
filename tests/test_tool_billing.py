"""Tests for the Billing tool family."""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from app.db.models import BillingRecord, Customer
from app.tools.billing.functions import get_billing_history

pytestmark = pytest.mark.asyncio


class TestGetBillingHistory:
    """Tests for get_billing_history."""

    async def test_returns_pending_regardless_of_age(self, async_session):
        """Pending records older than 90 days are still returned."""
        customer_id = uuid.uuid4()
        now = datetime.now(UTC)
        old_date = now - timedelta(days=100)

        async_session.add(
            Customer(
                id=customer_id,
                name="Alice",
                email=f"alice_{customer_id}@example.com",
                is_active=True,
            )
        )
        await async_session.flush()

        record_id = uuid.uuid4()
        async_session.add(
            BillingRecord(
                id=record_id,
                customer_id=customer_id,
                amount=Decimal("100.00"),
                currency="USD",
                status="pending",
                due_date=old_date,
                description="Old pending bill",
            )
        )
        await async_session.flush()

        # Override created_at to prove age doesn't affect filtering
        record = await async_session.get(BillingRecord, record_id)
        record.created_at = old_date
        await async_session.commit()

        results = await get_billing_history(async_session, customer_id)

        assert len(results) >= 1
        result_ids = [r.id for r in results]
        assert record_id in result_ids

    async def test_returns_paid_within_90_days(self, async_session):
        """Paid records with paid_at within the 90-day window are returned."""
        customer_id = uuid.uuid4()
        now = datetime.now(UTC)
        recent_date = now - timedelta(days=30)

        async_session.add(
            Customer(
                id=customer_id,
                name="Bob",
                email=f"bob_{customer_id}@example.com",
                is_active=True,
            )
        )
        await async_session.flush()

        record_id = uuid.uuid4()
        async_session.add(
            BillingRecord(
                id=record_id,
                customer_id=customer_id,
                amount=Decimal("200.00"),
                currency="USD",
                status="paid",
                paid_at=recent_date,
                due_date=now,
                description="Recent paid bill",
            )
        )
        await async_session.commit()

        results = await get_billing_history(async_session, customer_id)

        result_ids = [r.id for r in results]
        assert record_id in result_ids

    async def test_excludes_paid_older_than_90_days(self, async_session):
        """Paid records with paid_at older than 90 days are excluded."""
        customer_id = uuid.uuid4()
        now = datetime.now(UTC)
        old_date = now - timedelta(days=100)

        async_session.add(
            Customer(
                id=customer_id,
                name="Charlie",
                email=f"charlie_{customer_id}@example.com",
                is_active=True,
            )
        )
        await async_session.flush()

        record_id = uuid.uuid4()
        async_session.add(
            BillingRecord(
                id=record_id,
                customer_id=customer_id,
                amount=Decimal("300.00"),
                currency="USD",
                status="paid",
                paid_at=old_date,
                due_date=old_date,
                description="Old paid bill",
            )
        )
        await async_session.commit()

        results = await get_billing_history(async_session, customer_id)

        result_ids = [r.id for r in results]
        assert record_id not in result_ids

    async def test_returns_empty_list_for_no_records(self, async_session):
        """Unknown customer returns an empty list."""
        fake_id = uuid.uuid4()
        results = await get_billing_history(async_session, fake_id)
        assert results == []

