"""API-level tests for the Customer and Billing tool endpoints.

Covers the 4 GET endpoints:
- /api/v1/tools/customer/profile
- /api/v1/tools/customer/subscription
- /api/v1/tools/billing/history
- /api/v1/tools/billing/refunds

All tests use FastAPI's TestClient (via httpx.AsyncClient) and seed real
database records so the endpoints execute their full query path.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import BillingRecord, Customer, Subscription
from app.main import app

pytestmark = pytest.mark.asyncio


class TestCustomerEndpoints:
    """Tests for /customer/profile and /customer/subscription."""

    async def test_get_profile_happy_path(self, async_session):
        """GET /customer/profile returns 200 with profile data."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Alice",
                email="alice@example.com",
                phone="+8801700000001",
                is_active=True,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tools/customer/profile",
                params={"customer_id": str(customer_id)},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is not None
        assert body["data"]["id"] == str(customer_id)
        assert body["data"]["name"] == "Alice"
        assert body["data"]["email"] == "alice@example.com"
        assert body["data"]["is_active"] is True
        assert body["error"] is None

    async def test_get_profile_missing(self, async_session):
        """GET /customer/profile with unknown ID returns success=False."""
        fake_id = uuid.uuid4()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tools/customer/profile",
                params={"customer_id": str(fake_id)},
            )

        # DomainException handler wraps it as 200 ToolResult(success=False)
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] is not None
        assert str(fake_id) in body["error"]
        assert body["data"] is None

    async def test_get_subscription_happy_path(self, async_session):
        """GET /customer/subscription returns 200 with subscription data."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Bob",
                email="bob@example.com",
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

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tools/customer/subscription",
                params={"customer_id": str(customer_id)},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] is not None
        assert body["data"]["id"] == str(sub_id)
        assert body["data"]["plan"] == "premium"
        assert body["data"]["status"] == "active"
        assert body["error"] is None

    async def test_get_subscription_missing(self, async_session):
        """GET /customer/subscription with no subscription returns success=False."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Charlie",
                email="charlie@example.com",
                is_active=True,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tools/customer/subscription",
                params={"customer_id": str(customer_id)},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is False
        assert body["error"] is not None
        assert body["data"] is None


class TestBillingEndpoints:
    """Tests for /billing/history and /billing/refunds."""

    async def test_get_billing_history_happy_path(self, async_session):
        """GET /billing/history returns 200 with billing records."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Diana",
                email="diana@example.com",
                is_active=True,
            )
        )
        await async_session.flush()

        record_id = uuid.uuid4()
        now = datetime.now(UTC)
        async_session.add(
            BillingRecord(
                id=record_id,
                customer_id=customer_id,
                amount=Decimal("150.00"),
                currency="USD",
                status="paid",
                paid_at=now,
                description="Monthly subscription",
                due_date=now,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tools/billing/history",
                params={"customer_id": str(customer_id)},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["error"] is None
        data = body["data"]
        assert isinstance(data, list)
        assert len(data) >= 1
        assert data[0]["id"] == str(record_id)
        assert data[0]["status"] == "paid"

    async def test_get_billing_history_empty(self, async_session):
        """GET /billing/history with unknown customer returns empty list."""
        fake_id = uuid.uuid4()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tools/billing/history",
                params={"customer_id": str(fake_id)},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == []
        assert body["error"] is None

    async def test_get_refunds_happy_path(self, async_session):
        """GET /billing/refunds returns 200 with only refunded records."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Eve",
                email="eve@example.com",
                is_active=True,
            )
        )
        await async_session.flush()

        now = datetime.now(UTC)
        # A refunded record
        refund_id = uuid.uuid4()
        async_session.add(
            BillingRecord(
                id=refund_id,
                customer_id=customer_id,
                amount=Decimal("50.00"),
                currency="USD",
                status="refunded",
                paid_at=now,
                description="Refunded charge",
                due_date=now,
            )
        )
        # A paid record (should NOT appear in refunds)
        paid_id = uuid.uuid4()
        async_session.add(
            BillingRecord(
                id=paid_id,
                customer_id=customer_id,
                amount=Decimal("100.00"),
                currency="USD",
                status="paid",
                paid_at=now,
                description="Paid charge",
                due_date=now,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tools/billing/refunds",
                params={"customer_id": str(customer_id)},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["error"] is None
        data = body["data"]
        assert isinstance(data, list)
        # Only the refunded record should be returned
        record_ids = [r["id"] for r in data]
        assert str(refund_id) in record_ids
        assert str(paid_id) not in record_ids
        # Every returned record has status "refunded"
        assert all(r["status"] == "refunded" for r in data)

    async def test_get_refunds_empty(self, async_session):
        """GET /billing/refunds with no refunds returns empty list."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Frank",
                email="frank@example.com",
                is_active=True,
            )
        )
        await async_session.flush()

        now = datetime.now(UTC)
        # Only a paid record, no refunds
        async_session.add(
            BillingRecord(
                id=uuid.uuid4(),
                customer_id=customer_id,
                amount=Decimal("75.00"),
                currency="USD",
                status="paid",
                paid_at=now,
                description="Paid charge",
                due_date=now,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tools/billing/refunds",
                params={"customer_id": str(customer_id)},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == []
        assert body["error"] is None
