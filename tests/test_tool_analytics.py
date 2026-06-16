"""Tests for the Analytics tool family."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.db.models import Customer, UsageAnalytic
from app.tools.analytics.functions import get_usage_analytics
from app.tools.analytics.models import UsageAnalyticModel

pytestmark = pytest.mark.asyncio


class TestGetUsageAnalytics:
    """Tests for get_usage_analytics."""

    # ── helpers ───────────────────────────────────────────────────────

    @staticmethod
    def _make_analytic(
        customer_id: uuid.UUID,
        metric_name: str = "api_calls",
        metric_value: float = 42.0,
        days_ago: int = 1,
    ) -> UsageAnalytic:
        """Build a UsageAnalytic ORM instance with a period_start offset
        from *now*."""
        now = datetime.now(UTC)
        return UsageAnalytic(
            id=uuid.uuid4(),
            customer_id=customer_id,
            metric_name=metric_name,
            metric_value=metric_value,
            period_start=now - timedelta(days=days_ago),
            period_end=now - timedelta(days=days_ago) + timedelta(hours=1),
        )

    # ── within window ─────────────────────────────────────────────────

    async def test_returns_records_within_window(self, async_session):
        """Records with period_start < 90 days ago should be returned."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()

        async_session.add(self._make_analytic(customer_id, days_ago=1))
        async_session.add(self._make_analytic(customer_id, days_ago=50))
        async_session.add(self._make_analytic(customer_id, days_ago=89))
        await async_session.commit()

        result = await get_usage_analytics(async_session, customer_id)

        assert len(result) == 3
        for record in result:
            assert isinstance(record, UsageAnalyticModel)
            assert record.customer_id == customer_id

    # ── outside window ────────────────────────────────────────────────

    async def test_excludes_records_outside_window(self, async_session):
        """Records with period_start >= 90 days ago should be excluded."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()

        async_session.add(self._make_analytic(customer_id, days_ago=91))
        async_session.add(self._make_analytic(customer_id, days_ago=180))
        await async_session.commit()

        result = await get_usage_analytics(async_session, customer_id)

        assert len(result) == 0

    # ── mixed window ──────────────────────────────────────────────────

    async def test_mixed_window_only_returns_recent(self, async_session):
        """Only records within the 90-day window are returned."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()

        async_session.add(self._make_analytic(customer_id, days_ago=1))
        async_session.add(self._make_analytic(customer_id, days_ago=95))
        async_session.add(self._make_analytic(customer_id, days_ago=200))
        await async_session.commit()

        result = await get_usage_analytics(async_session, customer_id)

        assert len(result) == 1
        assert result[0].metric_value == 42.0

    # ── metric_name filter ────────────────────────────────────────────

    async def test_filters_by_metric_name(self, async_session):
        """When metric_name is given, only matching records are returned."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()

        async_session.add(
            self._make_analytic(customer_id, metric_name="api_calls")
        )
        async_session.add(
            self._make_analytic(customer_id, metric_name="storage_gb")
        )
        async_session.add(
            self._make_analytic(customer_id, metric_name="api_calls")
        )
        await async_session.commit()

        result = await get_usage_analytics(
            async_session, customer_id, metric_name="api_calls"
        )

        assert len(result) == 2
        assert all(r.metric_name == "api_calls" for r in result)

    # ── optional metric_name ──────────────────────────────────────────

    async def test_returns_all_metrics_when_name_omitted(self, async_session):
        """When metric_name is None, all metrics for the customer are
        returned."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()

        async_session.add(
            self._make_analytic(customer_id, metric_name="api_calls")
        )
        async_session.add(
            self._make_analytic(customer_id, metric_name="storage_gb")
        )
        await async_session.commit()

        result = await get_usage_analytics(async_session, customer_id)

        assert len(result) == 2

    # ── no records at all ─────────────────────────────────────────────

    async def test_returns_empty_for_unknown_customer(self, async_session):
        """A customer_id with no UsageAnalytic records returns [].

        Also verifies function does NOT raise (it returns []).
        """
        fake_id = uuid.uuid4()
        result = await get_usage_analytics(async_session, fake_id)
        assert result == []



