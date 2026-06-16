"""Comprehensive tests for ``EvidenceAggregator``.

Tests cover all 8 known tool families plus the generic/unknown-tool fallback,
list vs. scalar data branching, None/empty-edge cases, partial-failure
semantics, and determinism.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest

from app.orchestrator.evidence_aggregator import EvidenceAggregator
from app.schemas.reasoning import EvidenceItem
from app.schemas.tools import ToolResult
from app.tools.analytics.models import UsageAnalyticModel
from app.tools.billing.models import BillingRecordModel
from app.tools.customer.models import CustomerProfile, SubscriptionStatus
from app.tools.knowledge.models import KnowledgeResult
from app.tools.ticket.models import TicketModel

# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest.fixture
def aggregator() -> EvidenceAggregator:
    return EvidenceAggregator()


@pytest.fixture
def customer_id() -> UUID:
    return uuid4()


@pytest.fixture
def sample_profile(customer_id: UUID) -> CustomerProfile:
    return CustomerProfile(
        id=customer_id,
        name="Alice Rahman",
        email="alice@example.com",
        phone="+8801700000000",
        is_active=True,
    )


@pytest.fixture
def sample_subscription(customer_id: UUID) -> SubscriptionStatus:
    return SubscriptionStatus(
        id=customer_id,
        plan="premium",
        status="active",
        current_period_start=datetime(2026, 1, 1, tzinfo=UTC),
        current_period_end=datetime(2026, 7, 1, tzinfo=UTC),
    )


@pytest.fixture
def sample_billing_records(customer_id: UUID) -> list[BillingRecordModel]:
    return [
        BillingRecordModel(
            id=uuid4(),
            customer_id=customer_id,
            amount=Decimal("49.99"),
            currency="USD",
            status="paid",
            description="Monthly subscription",
            created_at=datetime(2026, 5, 1, tzinfo=UTC),
        ),
        BillingRecordModel(
            id=uuid4(),
            customer_id=customer_id,
            amount=Decimal("9.99"),
            currency="USD",
            status="pending",
            description="Add-on service",
            created_at=datetime(2026, 5, 15, tzinfo=UTC),
        ),
    ]


@pytest.fixture
def sample_tickets(customer_id: UUID) -> list[TicketModel]:
    return [
        TicketModel(
            id=uuid4(),
            customer_id=customer_id,
            subject="Cannot log in",
            description="Getting 403 error",
            status="open",
            priority="high",
            created_at=datetime(2026, 5, 10, tzinfo=UTC),
            updated_at=datetime(2026, 5, 10, tzinfo=UTC),
        ),
    ]


@pytest.fixture
def sample_single_ticket(customer_id: UUID) -> TicketModel:
    return TicketModel(
        id=uuid4(),
        customer_id=customer_id,
        subject="Payment issue",
        description="Invoice not reflecting",
        status="in_progress",
        priority="medium",
        created_at=datetime(2026, 5, 12, tzinfo=UTC),
        updated_at=datetime(2026, 5, 13, tzinfo=UTC),
    )


@pytest.fixture
def sample_knowledge_docs() -> list[KnowledgeResult]:
    return [
        KnowledgeResult(
            id=uuid4(),
            content="To reset your password, visit the account settings page.",
            metadata={"category": "faq"},
            similarity_score=0.95,
        ),
    ]


@pytest.fixture
def sample_knowledge_policies() -> list[KnowledgeResult]:
    return [
        KnowledgeResult(
            id=uuid4(),
            content="Refunds are processed within 5-7 business days.",
            metadata={"category": "policy"},
            similarity_score=0.88,
        ),
    ]


@pytest.fixture
def sample_usage_analytics(customer_id: UUID) -> list[UsageAnalyticModel]:
    return [
        UsageAnalyticModel(
            id=uuid4(),
            customer_id=customer_id,
            metric_name="api_calls",
            metric_value=1423.0,
            period_start=datetime(2026, 5, 1, tzinfo=UTC),
            period_end=datetime(2026, 5, 31, tzinfo=UTC),
        ),
    ]


# ── Helpers ───────────────────────────────────────────────────────────────────


def _assert_evidence_item(
    item: EvidenceItem,
    *,
    source: str,
    tool_name: str,
    metadata: dict | None = None,
) -> None:
    """Assert common fields on an evidence item without checking content."""
    assert item.source == source, f"expected source={source!r}, got {item.source!r}"
    assert item.tool_name == tool_name, (
        f"expected tool_name={tool_name!r}, got {item.tool_name!r}"
    )
    assert item.timestamp is not None, "timestamp must not be None"
    if metadata is not None:
        assert item.metadata == metadata, (
            f"expected metadata={metadata!r}, got {item.metadata!r}"
        )


# ── Single-object tools ───────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_single_customer_profile(
    aggregator: EvidenceAggregator,
    sample_profile: CustomerProfile,
) -> None:
    """A single CustomerProfile produces exactly one EvidenceItem."""
    result = ToolResult.ok(sample_profile)
    package = await aggregator.aggregate({"get_customer_profile": result})

    assert len(package.items) == 1
    assert package.total_sources == 1
    assert package.failed_tools == []

    item = package.items[0]
    _assert_evidence_item(
        item,
        source="customer_profile",
        tool_name="get_customer_profile",
        metadata={
            "customer_id": str(sample_profile.id),
            "is_active": True,
        },
    )
    # Content should be a JSON string with the profile fields.
    parsed = json.loads(item.content)
    assert parsed["name"] == "Alice Rahman"
    assert parsed["email"] == "alice@example.com"


@pytest.mark.asyncio
async def test_single_subscription_status(
    aggregator: EvidenceAggregator,
    sample_subscription: SubscriptionStatus,
) -> None:
    """A single SubscriptionStatus produces exactly one EvidenceItem."""
    result = ToolResult.ok(sample_subscription)
    package = await aggregator.aggregate({"get_subscription_status": result})

    assert len(package.items) == 1
    assert package.total_sources == 1
    assert package.failed_tools == []

    item = package.items[0]
    _assert_evidence_item(
        item,
        source="subscription",
        tool_name="get_subscription_status",
        metadata={"plan": "premium", "status": "active"},
    )
    parsed = json.loads(item.content)
    assert parsed["plan"] == "premium"
    assert parsed["status"] == "active"


@pytest.mark.asyncio
async def test_single_ticket_status(
    aggregator: EvidenceAggregator,
    sample_single_ticket: TicketModel,
) -> None:
    """A single TicketModel (get_ticket_status) produces one EvidenceItem."""
    result = ToolResult.ok(sample_single_ticket)
    package = await aggregator.aggregate({"get_ticket_status": result})

    assert len(package.items) == 1
    assert package.total_sources == 1

    item = package.items[0]
    _assert_evidence_item(
        item,
        source="support_tickets",
        tool_name="get_ticket_status",
        metadata={
            "ticket_id": str(sample_single_ticket.id),
            "status": "in_progress",
            "priority": "medium",
        },
    )
    parsed = json.loads(item.content)
    assert parsed["subject"] == "Payment issue"


# ── List-returning tools ─────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_billing_history_list(
    aggregator: EvidenceAggregator,
    sample_billing_records: list[BillingRecordModel],
) -> None:
    """Each billing record becomes a separate EvidenceItem."""
    result = ToolResult.ok(sample_billing_records)
    package = await aggregator.aggregate({"get_billing_history": result})

    assert len(package.items) == 2
    assert package.total_sources == 2
    assert package.failed_tools == []

    for i, item in enumerate(package.items):
        _assert_evidence_item(
            item,
            source="billing_records",
            tool_name="get_billing_history",
            metadata={
                "record_id": str(sample_billing_records[i].id),
                "status": sample_billing_records[i].status,
                "amount": str(sample_billing_records[i].amount),
            },
        )
        parsed = json.loads(item.content)
        assert parsed["currency"] == "USD"
        assert parsed["status"] == sample_billing_records[i].status


@pytest.mark.asyncio
async def test_support_tickets_list(
    aggregator: EvidenceAggregator,
    sample_tickets: list[TicketModel],
) -> None:
    """Each ticket becomes a separate EvidenceItem."""
    result = ToolResult.ok(sample_tickets)
    package = await aggregator.aggregate({"get_support_tickets": result})

    assert len(package.items) == 1
    assert package.total_sources == 1

    item = package.items[0]
    _assert_evidence_item(
        item,
        source="support_tickets",
        tool_name="get_support_tickets",
        metadata={
            "ticket_id": str(sample_tickets[0].id),
            "status": "open",
            "priority": "high",
        },
    )


@pytest.mark.asyncio
async def test_search_documentation_list(
    aggregator: EvidenceAggregator,
    sample_knowledge_docs: list[KnowledgeResult],
) -> None:
    """Each KnowledgeResult from search_documentation becomes an EvidenceItem
    with content set to the raw text (not JSON)."""
    result = ToolResult.ok(sample_knowledge_docs)
    package = await aggregator.aggregate({"search_documentation": result})

    assert len(package.items) == 1
    assert package.total_sources == 1

    item = package.items[0]
    _assert_evidence_item(
        item,
        source="documentation",
        tool_name="search_documentation",
        metadata={
            "doc_id": str(sample_knowledge_docs[0].id),
            "score": 0.95,
        },
    )
    # Content is raw text, not JSON.
    assert item.content == "To reset your password, visit the account settings page."


@pytest.mark.asyncio
async def test_search_policies_list(
    aggregator: EvidenceAggregator,
    sample_knowledge_policies: list[KnowledgeResult],
) -> None:
    """Each KnowledgeResult from search_policies becomes an EvidenceItem
    with content set to the raw text (not JSON)."""
    result = ToolResult.ok(sample_knowledge_policies)
    package = await aggregator.aggregate({"search_policies": result})

    assert len(package.items) == 1
    assert package.total_sources == 1

    item = package.items[0]
    _assert_evidence_item(
        item,
        source="policies",
        tool_name="search_policies",
        metadata={
            "doc_id": str(sample_knowledge_policies[0].id),
            "score": 0.88,
        },
    )
    assert item.content == "Refunds are processed within 5-7 business days."


@pytest.mark.asyncio
async def test_usage_analytics_list(
    aggregator: EvidenceAggregator,
    sample_usage_analytics: list[UsageAnalyticModel],
) -> None:
    """Each UsageAnalyticModel becomes a separate EvidenceItem."""
    result = ToolResult.ok(sample_usage_analytics)
    package = await aggregator.aggregate({"get_usage_analytics": result})

    assert len(package.items) == 1
    assert package.total_sources == 1

    item = package.items[0]
    _assert_evidence_item(
        item,
        source="usage_analytics",
        tool_name="get_usage_analytics",
        metadata={
            "record_id": str(sample_usage_analytics[0].id),
            "metric": "api_calls",
            "value": 1423.0,
        },
    )
    parsed = json.loads(item.content)
    assert parsed["metric_name"] == "api_calls"
    assert parsed["metric_value"] == 1423.0


# ── Failure / edge-case semantics ────────────────────────────────────────────


@pytest.mark.asyncio
async def test_failed_tool_added_to_failed_tools(
    aggregator: EvidenceAggregator,
) -> None:
    """A failed tool result adds the tool name to ``failed_tools``."""
    result = ToolResult.fail("service unavailable")
    package = await aggregator.aggregate({"get_usage_analytics": result})

    assert len(package.items) == 0
    assert package.total_sources == 0
    assert package.failed_tools == ["get_usage_analytics"]


@pytest.mark.asyncio
async def test_mixed_success_and_failure(
    aggregator: EvidenceAggregator,
    sample_profile: CustomerProfile,
) -> None:
    """Successful and failed tools are handled independently."""
    results = {
        "get_customer_profile": ToolResult.ok(sample_profile),
        "get_billing_history": ToolResult.fail("db timeout"),
        "get_subscription_status": ToolResult.fail("not found"),
    }
    package = await aggregator.aggregate(results)

    assert len(package.items) == 1
    assert package.total_sources == 1
    assert sorted(package.failed_tools) == ["get_billing_history", "get_subscription_status"]

    item = package.items[0]
    assert item.tool_name == "get_customer_profile"
    assert item.source == "customer_profile"


@pytest.mark.asyncio
async def test_none_data_skipped_not_failed(
    aggregator: EvidenceAggregator,
) -> None:
    """``success=True, data=None`` produces no item and is NOT in failed_tools."""
    result = ToolResult.ok(data=None)
    package = await aggregator.aggregate({"get_customer_profile": result})

    assert len(package.items) == 0
    assert package.total_sources == 0
    assert package.failed_tools == []


@pytest.mark.asyncio
async def test_empty_list_skipped(
    aggregator: EvidenceAggregator,
) -> None:
    """An empty list produces no evidence items."""
    result = ToolResult.ok([])
    package = await aggregator.aggregate({"get_billing_history": result})

    assert len(package.items) == 0
    assert package.total_sources == 0
    assert package.failed_tools == []


@pytest.mark.asyncio
async def test_empty_input_dict(
    aggregator: EvidenceAggregator,
) -> None:
    """Empty input returns an empty-but-valid EvidencePackage."""
    package = await aggregator.aggregate({})

    assert package.items == []
    assert package.failed_tools == []
    assert package.total_sources == 0


# ── Unknown / generic tool ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_unknown_tool_creates_generic_item(
    aggregator: EvidenceAggregator,
) -> None:
    """An unknown tool name creates a generic EvidenceItem."""
    result = ToolResult.ok("raw string data")
    package = await aggregator.aggregate({"some_unknown_tool": result})

    assert len(package.items) == 1
    assert package.total_sources == 1

    item = package.items[0]
    assert item.source == "some_unknown_tool"
    assert item.tool_name == "some_unknown_tool"
    assert item.content == "raw string data"
    assert item.metadata == {}
    assert item.timestamp is not None


@pytest.mark.asyncio
async def test_unknown_tool_with_list_data(
    aggregator: EvidenceAggregator,
) -> None:
    """An unknown tool with list data creates one generic item per element."""
    result = ToolResult.ok(["a", "b", "c"])
    package = await aggregator.aggregate({"custom_tool": result})

    assert len(package.items) == 3
    assert package.total_sources == 3

    for i, item in enumerate(package.items):
        assert item.source == "custom_tool"
        assert item.tool_name == "custom_tool"
        assert item.content == ["a", "b", "c"][i]


# ── EvidencePackage structural guarantees ─────────────────────────────────────


@pytest.mark.asyncio
async def test_timestamp_is_iso_format(
    aggregator: EvidenceAggregator,
    sample_profile: CustomerProfile,
) -> None:
    """Timestamp must be a valid ISO 8601 string."""
    result = ToolResult.ok(sample_profile)
    package = await aggregator.aggregate({"get_customer_profile": result})

    ts = package.items[0].timestamp
    assert ts is not None
    # Parse it — should not raise.
    datetime.fromisoformat(ts)


@pytest.mark.asyncio
async def test_total_sources_matches_item_count(
    aggregator: EvidenceAggregator,
    sample_billing_records: list[BillingRecordModel],
    sample_tickets: list[TicketModel],
) -> None:
    """``total_sources`` always equals ``len(items)``."""
    results = {
        "get_billing_history": ToolResult.ok(sample_billing_records),
        "get_support_tickets": ToolResult.ok(sample_tickets),
    }
    package = await aggregator.aggregate(results)

    assert package.total_sources == len(package.items)
    # 2 billing records + 1 ticket = 3 items
    assert package.total_sources == 3


# ── Multi-tool integration ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_multiple_successful_tools(
    aggregator: EvidenceAggregator,
    sample_profile: CustomerProfile,
    sample_subscription: SubscriptionStatus,
) -> None:
    """Two successful tools produce one item each."""
    results = {
        "get_customer_profile": ToolResult.ok(sample_profile),
        "get_subscription_status": ToolResult.ok(sample_subscription),
    }
    package = await aggregator.aggregate(results)

    assert len(package.items) == 2
    assert package.total_sources == 2
    assert package.failed_tools == []

    sources = {item.source for item in package.items}
    assert sources == {"customer_profile", "subscription"}


@pytest.mark.asyncio
async def test_all_known_tools_together(
    aggregator: EvidenceAggregator,
    sample_profile: CustomerProfile,
    sample_subscription: SubscriptionStatus,
    sample_billing_records: list[BillingRecordModel],
    sample_tickets: list[TicketModel],
    sample_single_ticket: TicketModel,
    sample_knowledge_docs: list[KnowledgeResult],
    sample_knowledge_policies: list[KnowledgeResult],
    sample_usage_analytics: list[UsageAnalyticModel],
) -> None:
    """All 8 known tool types produce correct evidence items in one call."""
    results = {
        "get_customer_profile": ToolResult.ok(sample_profile),
        "get_subscription_status": ToolResult.ok(sample_subscription),
        "get_billing_history": ToolResult.ok(sample_billing_records),
        "get_support_tickets": ToolResult.ok(sample_tickets),
        "get_ticket_status": ToolResult.ok(sample_single_ticket),
        "search_documentation": ToolResult.ok(sample_knowledge_docs),
        "search_policies": ToolResult.ok(sample_knowledge_policies),
        "get_usage_analytics": ToolResult.ok(sample_usage_analytics),
    }
    package = await aggregator.aggregate(results)

    # 1 profile + 1 subscription + 2 billing + 1 ticket list + 1 single ticket
    # + 1 doc + 1 policy + 1 analytic = 9 items
    assert len(package.items) == 9
    assert package.total_sources == 9
    assert package.failed_tools == []

    # Verify sources present.
    source_set = {item.source for item in package.items}
    assert source_set == {
        "customer_profile",
        "subscription",
        "billing_records",
        "support_tickets",
        "documentation",
        "policies",
        "usage_analytics",
    }

    # Verify tool_names present.
    tool_set = {item.tool_name for item in package.items}
    assert tool_set == {
        "get_customer_profile",
        "get_subscription_status",
        "get_billing_history",
        "get_support_tickets",
        "get_ticket_status",
        "search_documentation",
        "search_policies",
        "get_usage_analytics",
    }


# ── Determinism ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_deterministic_output(
    aggregator: EvidenceAggregator,
    sample_profile: CustomerProfile,
) -> None:
    """Same input yields identical output."""
    result = ToolResult.ok(sample_profile)
    results = {"get_customer_profile": result}

    package_a = await aggregator.aggregate(results)
    package_b = await aggregator.aggregate(results)

    assert len(package_a.items) == len(package_b.items)
    assert package_a.failed_tools == package_b.failed_tools
    assert package_a.total_sources == package_b.total_sources
    # Items should match structurally (content, metadata, source, tool_name).
    for a, b in zip(package_a.items, package_b.items, strict=True):
        assert a.source == b.source
        assert a.tool_name == b.tool_name
        assert a.content == b.content
        assert a.metadata == b.metadata
        # Timestamps will differ since they're generated per call, so skip that.


# ── Partial-failure edge case (explicitly called out in plan) ─────────────────


@pytest.mark.asyncio
async def test_partial_failure_with_mixed_list_and_single(
    aggregator: EvidenceAggregator,
    sample_billing_records: list[BillingRecordModel],
    sample_profile: CustomerProfile,
) -> None:
    """Partial failure: some tools succeed, some fail, mix of list and single."""
    results = {
        "get_billing_history": ToolResult.ok(sample_billing_records),  # 2 items
        "get_customer_profile": ToolResult.ok(sample_profile),  # 1 item
        "get_support_tickets": ToolResult.ok([]),  # empty → 0 items
        "get_subscription_status": ToolResult.fail("db error"),  # failed
        "get_usage_analytics": ToolResult.fail("timeout"),  # failed
        "get_ticket_status": ToolResult.ok(data=None),  # None → skip, not failed
    }
    package = await aggregator.aggregate(results)

    # 2 billing + 1 profile = 3 items total
    assert len(package.items) == 3
    assert package.total_sources == 3
    # 2 tools failed: get_subscription_status, get_usage_analytics
    assert sorted(package.failed_tools) == ["get_subscription_status", "get_usage_analytics"]

    # Verify items are correct.
    sources = sorted(item.source for item in package.items)
    assert sources == ["billing_records", "billing_records", "customer_profile"]

    # Verify failed tools are NOT in items.
    item_tools = {item.tool_name for item in package.items}
    assert "get_subscription_status" not in item_tools
    assert "get_usage_analytics" not in item_tools
