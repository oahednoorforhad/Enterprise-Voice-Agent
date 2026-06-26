"""Tests for app.voice.tools — declarations and dispatch_tool()."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.tools.ticket.models import TicketModel
from app.voice.tools import GEMINI_TOOL_DECLARATIONS, dispatch_tool

# ── Declaration structure ─────────────────────────────────────────────────────

EXPECTED_TOOL_NAMES = {
    "create_support_ticket",
    "get_customer_profile",
    "get_subscription_status",
    "get_billing_history",
    "get_support_tickets",
    "get_ticket_status",
    "get_usage_analytics",
    "search_documentation",
    "search_policies",
    "get_session_history",
}


def test_declarations_count():
    assert len(GEMINI_TOOL_DECLARATIONS) == 10


def test_declaration_names():
    names = {d["name"] for d in GEMINI_TOOL_DECLARATIONS}
    assert names == EXPECTED_TOOL_NAMES


def test_no_customer_id_in_any_declaration():
    """Security gate: customer_id must NEVER appear as a declared parameter."""
    for decl in GEMINI_TOOL_DECLARATIONS:
        props = decl.get("parameters", {}).get("properties", {})
        assert "customer_id" not in props, (
            f"Tool '{decl['name']}' illegally exposes customer_id as a parameter"
        )


def test_declarations_have_required_fields():
    for decl in GEMINI_TOOL_DECLARATIONS:
        assert "name" in decl
        assert "description" in decl
        assert isinstance(decl["description"], str) and decl["description"]


def test_tool_with_no_user_params_has_empty_properties():
    no_param_tools = {
        "get_customer_profile",
        "get_subscription_status",
        "get_billing_history",
        "get_support_tickets",
    }
    for decl in GEMINI_TOOL_DECLARATIONS:
        if decl["name"] in no_param_tools:
            props = decl.get("parameters", {}).get("properties", {})
            assert props == {}, f"'{decl['name']}' should have no user-facing params"


def test_ticket_status_requires_ticket_id():
    decl = next(d for d in GEMINI_TOOL_DECLARATIONS if d["name"] == "get_ticket_status")
    assert "ticket_id" in decl["parameters"]["properties"]
    assert "ticket_id" in decl["parameters"].get("required", [])


def test_usage_analytics_has_optional_metric_name():
    decl = next(d for d in GEMINI_TOOL_DECLARATIONS if d["name"] == "get_usage_analytics")
    assert "metric_name" in decl["parameters"]["properties"]
    # metric_name should NOT be required
    required = decl["parameters"].get("required", [])
    assert "metric_name" not in required


def test_search_tools_require_query():
    for name in ("search_documentation", "search_policies"):
        decl = next(d for d in GEMINI_TOOL_DECLARATIONS if d["name"] == name)
        assert "query" in decl["parameters"]["properties"]
        assert "query" in decl["parameters"].get("required", [])


# ── dispatch_tool ─────────────────────────────────────────────────────────────

CUSTOMER_UUID = uuid.UUID("c63d2f89-9aa3-4157-8205-a7d6cfc23207")


def _make_session_factory(mock_session):
    """Build an async_sessionmaker-like context-manager mock."""
    cm = AsyncMock()
    cm.__aenter__ = AsyncMock(return_value=mock_session)
    cm.__aexit__ = AsyncMock(return_value=False)
    factory = MagicMock(return_value=cm)
    return factory


class _FakeModel:
    def model_dump(self, mode="python"):
        return {"id": "test", "name": "Acme"}


@pytest.mark.asyncio
async def test_dispatch_get_customer_profile():
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    with patch(
        "app.voice.tools.get_customer_profile",
        new=AsyncMock(return_value=_FakeModel()),
    ):
        result = await dispatch_tool("get_customer_profile", {}, factory, CUSTOMER_UUID)

    assert result == {"id": "test", "name": "Acme"}


@pytest.mark.asyncio
async def test_dispatch_get_billing_history():
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    with patch(
        "app.voice.tools.get_billing_history",
        new=AsyncMock(return_value=[_FakeModel(), _FakeModel()]),
    ):
        result = await dispatch_tool("get_billing_history", {}, factory, CUSTOMER_UUID)

    assert "records" in result
    assert len(result["records"]) == 2


@pytest.mark.asyncio
async def test_dispatch_get_ticket_status():
    ticket_uuid = uuid.uuid4()
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    with patch(
        "app.voice.tools.get_ticket_status",
        new=AsyncMock(return_value=_FakeModel()),
    ) as mock_fn:
        await dispatch_tool(
            "get_ticket_status",
            {"ticket_id": str(ticket_uuid)},
            factory,
            CUSTOMER_UUID,
        )

    # Verify customer_id was injected and ticket_id was passed
    call_args = mock_fn.call_args
    assert call_args.args[1] == CUSTOMER_UUID
    assert call_args.args[2] == ticket_uuid


@pytest.mark.asyncio
async def test_dispatch_get_usage_analytics_with_metric():
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    with patch(
        "app.voice.tools.get_usage_analytics",
        new=AsyncMock(return_value=[]),
    ) as mock_fn:
        await dispatch_tool(
            "get_usage_analytics",
            {"metric_name": "api_calls"},
            factory,
            CUSTOMER_UUID,
        )

    assert mock_fn.call_args.args[2] == "api_calls"


@pytest.mark.asyncio
async def test_dispatch_get_usage_analytics_without_metric():
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    with patch(
        "app.voice.tools.get_usage_analytics",
        new=AsyncMock(return_value=[]),
    ) as mock_fn:
        await dispatch_tool("get_usage_analytics", {}, factory, CUSTOMER_UUID)

    assert mock_fn.call_args.args[2] is None


@pytest.mark.asyncio
async def test_dispatch_search_documentation():
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    with patch(
        "app.voice.tools.search_documentation",
        new=AsyncMock(return_value=[]),
    ) as mock_fn:
        result = await dispatch_tool(
            "search_documentation", {"query": "SSO setup"}, factory, CUSTOMER_UUID
        )

    assert "results" in result
    assert mock_fn.call_args.args[1] == "SSO setup"


@pytest.mark.asyncio
async def test_dispatch_create_support_ticket():
    ticket_id = uuid.uuid4()
    now = datetime.now(tz=UTC)
    mock_ticket = TicketModel(
        id=ticket_id,
        customer_id=CUSTOMER_UUID,
        subject="Test issue",
        description="Something broke",
        status="open",
        priority="high",
        created_at=now,
        updated_at=now,
    )
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    with patch(
        "app.voice.tools.create_support_ticket",
        new=AsyncMock(return_value=mock_ticket),
    ) as mock_create:
        result = await dispatch_tool(
            "create_support_ticket",
            {
                "title": "Test issue",
                "description": "Something broke",
                "category": "Bug Report",
                "priority": "high",
                "confirmed": True,
            },
            factory,
            CUSTOMER_UUID,
        )

    mock_create.assert_awaited_once()
    # customer_id is injected server-side as a positional arg (not in kwargs)
    assert mock_create.call_args.args[1] == CUSTOMER_UUID
    assert mock_create.call_args.kwargs["title"] == "Test issue"
    assert mock_create.call_args.kwargs["confirmed"] is True
    assert mock_create.call_args.kwargs["category"] == "Bug Report"
    assert mock_create.call_args.kwargs["priority"] == "high"
    assert "customer_id" not in mock_create.call_args.kwargs
    assert result["id"] == str(ticket_id)
    assert result["subject"] == "Test issue"


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_returns_error():
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    result = await dispatch_tool("nonexistent_tool", {}, factory, CUSTOMER_UUID)
    assert "error" in result


@pytest.mark.asyncio
async def test_dispatch_tool_exception_returns_error():
    mock_session = AsyncMock()
    factory = _make_session_factory(mock_session)

    with patch(
        "app.voice.tools.get_customer_profile",
        new=AsyncMock(side_effect=RuntimeError("DB offline")),
    ):
        result = await dispatch_tool("get_customer_profile", {}, factory, CUSTOMER_UUID)

    assert "error" in result
    assert "DB offline" in result["error"]
