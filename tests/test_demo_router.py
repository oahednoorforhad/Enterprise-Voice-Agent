"""Tests for the demo router — apply-scenario endpoint."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db.models import (
    BillingRecord,
    CRMNote,
    Customer,
    Subscription,
    SupportTicket,
    UsageAnalytic,
)


# ── Helper ───────────────────────────────────────────────────────────────────

def _make_customer(**kwargs) -> Customer:
    """Build a Customer instance with sensible defaults."""
    return Customer(
        name=kwargs.pop("name", "Test User"),
        email=kwargs.pop("email", "test@test.com"),
        is_active=kwargs.pop("is_active", True),
        is_demo=kwargs.pop("is_demo", True),
        **kwargs,
    )


# ── apply-scenario endpoint ──────────────────────────────────────────────────


class TestApplyScenario:
    """POST /api/v1/demo/apply-scenario"""

    def _override_deps(self, app, async_session, customer_id: str, email: str):
        """Install dependency overrides pointing at the real async_session."""
        from app.api.deps import get_current_user
        from app.db import get_db_session

        async def _override_db():
            yield async_session

        async def _override_user():
            return {"customer_id": customer_id, "email": email}

        app.dependency_overrides[get_db_session] = _override_db
        app.dependency_overrides[get_current_user] = _override_user

    def _clear_overrides(self, app):
        """Remove dependency overrides installed by this test."""
        from app.api.deps import get_current_user
        from app.db import get_db_session

        app.dependency_overrides.pop(get_db_session, None)
        app.dependency_overrides.pop(get_current_user, None)

    async def test_apply_scenario_demo_user(self, async_session) -> None:
        """A demo user can apply a scenario — data is inserted with correct FK wiring."""
        from app.main import app

        # Arrange
        customer = _make_customer()
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        customer_id = str(customer.id)
        self._override_deps(app, async_session, customer_id, customer.email)

        client = TestClient(app, raise_server_exceptions=False)

        # Act
        response = client.post(
            "/api/v1/demo/apply-scenario",
            json={"scenario_id": "billing_dispute"},
        )

        # Assert
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["scenario_id"] == "billing_dispute"
        assert data["active_scenario"] == "billing_dispute"

        # Verify subscriptions inserted
        result = await async_session.execute(
            select(Subscription).where(Subscription.customer_id == customer.id)
        )
        subs = result.scalars().all()
        assert len(subs) == 1
        assert subs[0].plan_name is not None
        new_sub_id = subs[0].id

        # Verify billing records inserted with FK wired to the new subscription
        result = await async_session.execute(
            select(BillingRecord).where(BillingRecord.customer_id == customer.id)
        )
        bills = result.scalars().all()
        assert len(bills) > 0
        assert all(b.subscription_id == new_sub_id for b in bills)

        # Verify support tickets inserted
        result = await async_session.execute(
            select(SupportTicket).where(SupportTicket.customer_id == customer.id)
        )
        tickets = result.scalars().all()
        assert len(tickets) > 0

        # Verify usage analytics inserted
        result = await async_session.execute(
            select(UsageAnalytic).where(UsageAnalytic.customer_id == customer.id)
        )
        analytics = result.scalars().all()
        assert len(analytics) > 0

        # Verify CRM notes inserted
        result = await async_session.execute(
            select(CRMNote).where(CRMNote.customer_id == customer.id)
        )
        notes = result.scalars().all()
        assert len(notes) > 0

        # Clean up
        self._clear_overrides(app)

    async def test_apply_scenario_non_demo_user_403(self, async_session) -> None:
        """A non-demo user gets 403."""
        from app.main import app

        # Arrange
        customer = _make_customer(name="Real User", email="real@test.com", is_demo=False)
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        customer_id = str(customer.id)
        self._override_deps(app, async_session, customer_id, customer.email)

        client = TestClient(app, raise_server_exceptions=False)

        # Act
        response = client.post(
            "/api/v1/demo/apply-scenario",
            json={"scenario_id": "billing_dispute"},
        )

        # Assert
        assert response.status_code == 403, response.text
        assert "Only demo accounts" in response.text

        # Clean up
        self._clear_overrides(app)

    async def test_apply_scenario_invalid_id_400(self, async_session) -> None:
        """An unknown scenario_id returns 400."""
        from app.main import app

        # Arrange
        customer = _make_customer(name="Demo User 2", email="demo2@test.com")
        async_session.add(customer)
        await async_session.commit()
        await async_session.refresh(customer)

        customer_id = str(customer.id)
        self._override_deps(app, async_session, customer_id, customer.email)

        client = TestClient(app, raise_server_exceptions=False)

        # Act
        response = client.post(
            "/api/v1/demo/apply-scenario",
            json={"scenario_id": "nonexistent_scenario"},
        )

        # Assert
        assert response.status_code == 400, response.text
        assert "Unknown scenario_id" in response.text

        # Clean up
        self._clear_overrides(app)

    async def test_apply_scenario_customer_not_found_404(self, async_session) -> None:
        """When the customer_id from auth doesn't exist in DB, return 404."""
        from app.main import app

        # Use a UUID that does not correspond to any customer
        from uuid import uuid4

        fake_id = str(uuid4())
        self._override_deps(app, async_session, fake_id, "ghost@test.com")

        client = TestClient(app, raise_server_exceptions=False)

        # Act
        response = client.post(
            "/api/v1/demo/apply-scenario",
            json={"scenario_id": "billing_dispute"},
        )

        # Assert
        assert response.status_code == 404, response.text
        assert "Customer not found" in response.text

        # Clean up
        self._clear_overrides(app)


# ── Route registration (no DB, dependency-free smoke tests) ─────────────────


def test_demo_router_routes_registered() -> None:
    """Verify the demo router's routes are present on the app."""
    from app.main import app

    paths = {r.path for r in app.routes}
    assert "/api/v1/demo/apply-scenario" in paths
