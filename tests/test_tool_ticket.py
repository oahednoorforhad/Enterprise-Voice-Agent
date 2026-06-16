"""Tests for the Ticket tool family."""

import uuid
from datetime import UTC, datetime, timedelta

import pytest

from app.core.exceptions import TicketNotFoundError
from app.db.models import Customer, SupportTicket
from app.tools.ticket.functions import get_support_tickets, get_ticket_status
from app.tools.ticket.models import TicketModel

pytestmark = pytest.mark.asyncio

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_NOW = datetime.now(UTC)


def _ticket(**overrides) -> SupportTicket:
    """Build a ``SupportTicket`` instance with sensible defaults."""
    defaults = dict(
        id=uuid.uuid4(),
        customer_id=uuid.uuid4(),
        title="Test ticket",
        description="A description",
        status="open",
        priority="medium",
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return SupportTicket(**defaults)


# ---------------------------------------------------------------------------
# get_support_tickets — recency logic
# ---------------------------------------------------------------------------


class TestGetSupportTickets:
    """Business-aware recency rules for get_support_tickets."""

    async def test_open_ticket_older_than_30_days_is_returned(self, async_session):
        """Open + in-progress tickets are always returned regardless of age."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501  # noqa: E501
        await async_session.flush()
        old = _NOW - timedelta(days=31)
        async_session.add(
            _ticket(
                customer_id=customer_id,
                status="open",
                updated_at=old,
                created_at=old,
            )
        )
        await async_session.commit()

        results = await get_support_tickets(async_session, customer_id)

        assert len(results) == 1
        assert results[0].status == "open"

    async def test_in_progress_ticket_older_than_30_days_is_returned(
        self, async_session
    ):
        """in_progress tickets are also always returned."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        old = _NOW - timedelta(days=31)
        async_session.add(
            _ticket(
                customer_id=customer_id,
                status="in_progress",
                updated_at=old,
                created_at=old,
            )
        )
        await async_session.commit()

        results = await get_support_tickets(async_session, customer_id)

        assert len(results) == 1
        assert results[0].status == "in_progress"

    async def test_closed_ticket_within_30_days_is_returned(self, async_session):
        """Closed/resolved tickets updated within 30 days are returned."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        recent = _NOW - timedelta(days=15)
        async_session.add(
            _ticket(
                customer_id=customer_id,
                status="closed",
                updated_at=recent,
                created_at=_NOW - timedelta(days=60),
            )
        )
        await async_session.commit()

        results = await get_support_tickets(async_session, customer_id)

        assert len(results) == 1
        assert results[0].status == "closed"

    async def test_closed_ticket_older_than_30_days_excluded(self, async_session):
        """Closed/resolved tickets older than 30 days are filtered out."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        old = _NOW - timedelta(days=31)
        async_session.add(
            _ticket(
                customer_id=customer_id,
                status="closed",
                updated_at=old,
                created_at=_NOW - timedelta(days=90),
            )
        )
        await async_session.commit()

        results = await get_support_tickets(async_session, customer_id)

        assert len(results) == 0

    async def test_resolved_ticket_older_than_30_days_excluded(self, async_session):
        """Resolved tickets older than 30 days are also filtered out."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        old = _NOW - timedelta(days=31)
        async_session.add(
            _ticket(
                customer_id=customer_id,
                status="resolved",
                updated_at=old,
                created_at=_NOW - timedelta(days=90),
            )
        )
        await async_session.commit()

        results = await get_support_tickets(async_session, customer_id)

        assert len(results) == 0

    async def test_mixed_tickets_respect_recency(self, async_session):
        """Only the old closed ticket should be excluded."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        old = _NOW - timedelta(days=31)
        recent = _NOW - timedelta(days=5)

        async_session.add_all(
            [
                _ticket(
                    customer_id=customer_id,
                    status="open",
                    updated_at=old,
                ),
                _ticket(
                    customer_id=customer_id,
                    status="in_progress",
                    updated_at=old,
                ),
                _ticket(
                    customer_id=customer_id,
                    status="closed",
                    updated_at=recent,
                ),
                _ticket(
                    customer_id=customer_id,
                    status="closed",
                    updated_at=old,
                ),
                _ticket(
                    customer_id=customer_id,
                    status="resolved",
                    updated_at=recent,
                ),
            ]
        )
        await async_session.commit()

        results = await get_support_tickets(async_session, customer_id)

        # 4 returned: open, in_progress, recent closed, recent resolved
        assert len(results) == 4
        statuses = {r.status for r in results}
        assert statuses == {"open", "in_progress", "closed", "resolved"}

    async def test_empty_when_no_tickets(self, async_session):
        """No tickets at all returns empty list."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        results = await get_support_tickets(async_session, customer_id)
        assert results == []

    async def test_only_returns_tickets_for_requested_customer(self, async_session):
        """Tickets belonging to other customers are not returned."""
        customer_a = uuid.uuid4()
        async_session.add(Customer(id=customer_a, name="A", email=f"{customer_a}@test.com", is_active=True))  # noqa: E501
        customer_b = uuid.uuid4()
        async_session.add(Customer(id=customer_b, name="B", email=f"{customer_b}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        async_session.add(
            _ticket(
                customer_id=customer_a,
                status="open",
            )
        )
        await async_session.commit()

        results = await get_support_tickets(async_session, customer_b)

        assert len(results) == 0


# ---------------------------------------------------------------------------
# get_ticket_status — single-ticket lookup + isolation
# ---------------------------------------------------------------------------


class TestGetTicketStatus:
    """Customer isolation for get_ticket_status."""

    async def test_returns_ticket_when_found(self, async_session):
        """Happy path — ticket exists and belongs to the requesting customer."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        ticket_id = uuid.uuid4()
        async_session.add(
            _ticket(
                id=ticket_id,
                customer_id=customer_id,
                title="Help needed",
                status="open",
                priority="high",
            )
        )
        await async_session.commit()

        result = await get_ticket_status(async_session, customer_id, ticket_id)

        assert isinstance(result, TicketModel)
        assert result.id == ticket_id
        assert result.customer_id == customer_id
        assert result.subject == "Help needed"
        assert result.status == "open"
        assert result.priority == "high"

    async def test_raises_when_ticket_missing(self, async_session):
        """Non-existent ticket raises TicketNotFoundError."""
        customer_id = uuid.uuid4()
        async_session.add(Customer(id=customer_id, name="Test", email=f"{customer_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        fake_id = uuid.uuid4()

        with pytest.raises(TicketNotFoundError) as exc:
            await get_ticket_status(async_session, customer_id, fake_id)
        assert str(fake_id) in str(exc.value)

    async def test_raises_when_wrong_customer(self, async_session):
        """Ticket exists but belongs to another customer — isolation enforced."""
        owner_id = uuid.uuid4()
        async_session.add(Customer(id=owner_id, name="O", email=f"{owner_id}@test.com", is_active=True))  # noqa: E501
        attacker_id = uuid.uuid4()
        async_session.add(Customer(id=attacker_id, name="A", email=f"{attacker_id}@test.com", is_active=True))  # noqa: E501
        await async_session.flush()
        ticket_id = uuid.uuid4()
        async_session.add(
            _ticket(
                id=ticket_id,
                customer_id=owner_id,
                status="open",
            )
        )
        await async_session.commit()

        with pytest.raises(TicketNotFoundError) as exc:
            await get_ticket_status(async_session, attacker_id, ticket_id)
        assert str(ticket_id) in str(exc.value)









