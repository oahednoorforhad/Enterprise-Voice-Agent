"""API-level tests for Ticket & Analytics tool endpoints.

Verifies that the GET endpoints return HTTP 200 with a ``ToolResult`` JSON
body — the uniform response shape consumed by the LLM.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from httpx import ASGITransport, AsyncClient

from app.db.models import Customer, SupportTicket, UsageAnalytic
from app.main import app

pytestmark = pytest.mark.asyncio

_NOW = datetime.now(UTC)


# ---------------------------------------------------------------------------
# Ticket endpoints
# ---------------------------------------------------------------------------


class TestTicketListEndpoint:
    """GET /api/v1/tools/ticket/list."""

    async def test_list_returns_toolresult_with_tickets(self, async_session):
        """Happy path — seeded ticket returned in ToolResult."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Test",
                email=f"{customer_id}@test.com",
                is_active=True,
            )
        )
        ticket_id = uuid.uuid4()
        async_session.add(
            SupportTicket(
                id=ticket_id,
                customer_id=customer_id,
                title="My printer is on fire",
                description="Smoke coming from the USB port",
                status="open",
                priority="high",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/api/v1/tools/ticket/list?customer_id={customer_id}"
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["error"] is None
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1
        assert body["data"][0]["id"] == str(ticket_id)

    async def test_list_returns_empty_when_no_tickets(self, async_session):
        """No tickets for the customer returns an empty data list."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Empty",
                email=f"{customer_id}@test.com",
                is_active=True,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/api/v1/tools/ticket/list?customer_id={customer_id}"
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["data"] == []


class TestTicketStatusEndpoint:
    """GET /api/v1/tools/ticket/status."""

    async def test_status_returns_toolresult_with_ticket(self, async_session):
        """Happy path — valid customer & ticket returns the ticket."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Test",
                email=f"{customer_id}@test.com",
                is_active=True,
            )
        )
        ticket_id = uuid.uuid4()
        async_session.add(
            SupportTicket(
                id=ticket_id,
                customer_id=customer_id,
                title="Login issue",
                description="Cannot log in after password reset",
                status="in_progress",
                priority="medium",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/api/v1/tools/ticket/status"
                f"?customer_id={customer_id}&ticket_id={ticket_id}"
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["error"] is None
        assert body["data"]["id"] == str(ticket_id)
        assert body["data"]["status"] == "in_progress"
        assert body["data"]["subject"] == "Login issue"

    async def test_status_returns_fail_on_wrong_customer(self, async_session):
        """Ticket belongs to another customer → DomainException → ToolResult(success=False)."""
        owner_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=owner_id,
                name="Owner",
                email=f"{owner_id}@test.com",
                is_active=True,
            )
        )
        attacker_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=attacker_id,
                name="Attacker",
                email=f"{attacker_id}@test.com",
                is_active=True,
            )
        )
        ticket_id = uuid.uuid4()
        async_session.add(
            SupportTicket(
                id=ticket_id,
                customer_id=owner_id,
                title="Secret",
                description="For owner's eyes only",
                status="open",
                priority="low",
                created_at=_NOW,
                updated_at=_NOW,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/api/v1/tools/ticket/status"
                f"?customer_id={attacker_id}&ticket_id={ticket_id}"
            )

        # DomainException is caught by the global handler → 200 ToolResult(success=False)
        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is False
        assert body["data"] is None
        assert body["error"] is not None
        assert str(ticket_id) in body["error"]


# ---------------------------------------------------------------------------
# Analytics endpoint
# ---------------------------------------------------------------------------


class TestUsageAnalyticsEndpoint:
    """GET /api/v1/tools/analytics/usage."""

    async def test_usage_returns_toolresult_with_data(self, async_session):
        """Happy path — seeded analytics returned in ToolResult."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Analytics Customer",
                email=f"{customer_id}@test.com",
                is_active=True,
            )
        )
        async_session.add(
            UsageAnalytic(
                id=uuid.uuid4(),
                customer_id=customer_id,
                metric_name="api_calls",
                metric_value=42.0,
                period_start=_NOW - timedelta(days=1),
                period_end=_NOW,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/api/v1/tools/analytics/usage?customer_id={customer_id}"
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["error"] is None
        assert isinstance(body["data"], list)
        assert len(body["data"]) == 1
        assert body["data"][0]["metric_name"] == "api_calls"
        assert body["data"][0]["metric_value"] == 42.0

    async def test_usage_filters_by_metric_name(self, async_session):
        """Optional metric_name parameter filters results."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="Filter Test",
                email=f"{customer_id}@test.com",
                is_active=True,
            )
        )
        async_session.add_all(
            [
                UsageAnalytic(
                    id=uuid.uuid4(),
                    customer_id=customer_id,
                    metric_name="api_calls",
                    metric_value=100.0,
                    period_start=_NOW - timedelta(days=1),
                    period_end=_NOW,
                ),
                UsageAnalytic(
                    id=uuid.uuid4(),
                    customer_id=customer_id,
                    metric_name="token_usage",
                    metric_value=5000.0,
                    period_start=_NOW - timedelta(days=1),
                    period_end=_NOW,
                ),
            ]
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/api/v1/tools/analytics/usage"
                f"?customer_id={customer_id}&metric_name=token_usage"
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert len(body["data"]) == 1
        assert body["data"][0]["metric_name"] == "token_usage"

    async def test_usage_returns_empty_when_no_data(self, async_session):
        """No analytics records → empty data list."""
        customer_id = uuid.uuid4()
        async_session.add(
            Customer(
                id=customer_id,
                name="No Data",
                email=f"{customer_id}@test.com",
                is_active=True,
            )
        )
        await async_session.commit()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                f"/api/v1/tools/analytics/usage?customer_id={customer_id}"
            )

        assert response.status_code == 200, response.text
        body = response.json()
        assert body["success"] is True
        assert body["data"] == []
