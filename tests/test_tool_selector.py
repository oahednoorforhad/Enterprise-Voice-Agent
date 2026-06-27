"""Tests for the ``ToolSelector`` class.

The selector is a pure deterministic policy — no mocking of external
services is needed.  Every test constructs a ``ToolSelector`` with an
explicit ``max_calls`` override so results are independent of
environment-specific settings.
"""

from __future__ import annotations

import pytest

from app.core.exceptions import InvalidIntentLabelError
from app.orchestrator.tool_selector import ToolSelector
from app.schemas.reasoning import IntentAnalysisResult, ToolSelectionPlan

# ── Intent-to-tool mapping tests ──────────────────────────────────────────


class TestBillingInquiry:
    """Billing inquiry produces the correct ordered tool list, capped at 4."""

    @pytest.mark.asyncio
    async def test_selects_ordered_tools_within_max(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=[
                "search_policies",
                "get_billing_history",
                "get_support_tickets",
                "get_ticket_status",
                "search_documentation",
            ],
            candidate_sources=[
                "billing_records",
                "support_tickets",
                "policies",
                "documentation",
            ],
        )
        plan = await selector.select(intent)

        # Expected: first 4 tools from the billing order.
        assert plan.selected_tools == [
            "get_billing_history",
            "get_support_tickets",
            "get_ticket_status",
            "search_policies",
        ]
        assert len(plan.selected_tools) <= 4
        assert isinstance(plan, ToolSelectionPlan)
        assert plan.customer_context == {}
        assert plan.max_tool_calls == 10


class TestSupportTicket:
    """Support-ticket intent produces the correct tool list, capped at 3."""

    @pytest.mark.asyncio
    async def test_selects_ordered_tools_within_max(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="support_ticket",
            confidence=0.85,
            candidate_tools=[
                "get_ticket_status",
                "get_support_tickets",
                "search_documentation",
                "search_policies",
                "get_customer_profile",  # not in support_ticket order → filtered
            ],
            candidate_sources=["support_tickets", "documentation"],
        )
        plan = await selector.select(intent)

        # get_customer_profile should be filtered out; capped at 3.
        assert plan.selected_tools == [
            "get_support_tickets",
            "get_ticket_status",
            "search_documentation",
        ]
        assert len(plan.selected_tools) <= 3


class TestKnowledgeQuery:
    """Knowledge-query intent produces the correct tool list, capped at 2."""

    @pytest.mark.asyncio
    async def test_selects_ordered_tools_within_max(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="knowledge_query",
            confidence=0.78,
            candidate_tools=["search_policies", "search_documentation"],
            candidate_sources=["documentation", "policies"],
        )
        plan = await selector.select(intent)

        assert plan.selected_tools == ["search_documentation", "search_policies"]
        assert len(plan.selected_tools) <= 2


class TestAccountQuery:
    """Account-query intent produces the correct tool list, capped at 2."""

    @pytest.mark.asyncio
    async def test_selects_ordered_tools_within_max(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="account_query",
            confidence=0.80,
            candidate_tools=["get_subscription_status", "get_customer_profile"],
            candidate_sources=["customer_profile", "subscription"],
        )
        plan = await selector.select(intent)

        assert plan.selected_tools == [
            "get_customer_profile",
            "get_subscription_status",
        ]
        assert len(plan.selected_tools) <= 2


class TestAnalyticsQuery:
    """Analytics-query intent produces the correct tool list, capped at 1."""

    @pytest.mark.asyncio
    async def test_selects_ordered_tools_within_max(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="analytics_query",
            confidence=0.90,
            candidate_tools=["get_usage_analytics"],
            candidate_sources=["usage_analytics"],
        )
        plan = await selector.select(intent)

        assert plan.selected_tools == ["get_usage_analytics"]
        assert len(plan.selected_tools) <= 1


# ── Empty / short-circuit intents ─────────────────────────────────────────


class TestGreeting:
    """Greeting intent always returns an empty tool list."""

    @pytest.mark.asyncio
    async def test_greeting_returns_empty(self) -> None:
        selector = ToolSelector()
        intent = IntentAnalysisResult(
            intent_label="greeting",
            confidence=0.95,
            candidate_tools=[],
            candidate_sources=[],
        )
        plan = await selector.select(intent)
        assert plan.selected_tools == []

    @pytest.mark.asyncio
    async def test_greeting_with_candidate_tools_still_empty(self) -> None:
        """Even if the LLM accidentally sets candidate_tools, return empty."""
        selector = ToolSelector()
        intent = IntentAnalysisResult(
            intent_label="greeting",
            confidence=0.95,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        plan = await selector.select(intent)
        assert plan.selected_tools == []


class TestOther:
    """Other/unknown intent always returns an empty tool list."""

    @pytest.mark.asyncio
    async def test_other_returns_empty(self) -> None:
        selector = ToolSelector()
        intent = IntentAnalysisResult(
            intent_label="other",
            confidence=0.40,
            candidate_tools=[],
            candidate_sources=[],
        )
        plan = await selector.select(intent)
        assert plan.selected_tools == []

    @pytest.mark.asyncio
    async def test_other_with_candidate_tools_still_empty(self) -> None:
        """Even if the LLM accidentally sets candidate_tools, return empty."""
        selector = ToolSelector()
        intent = IntentAnalysisResult(
            intent_label="other",
            confidence=0.40,
            candidate_tools=["get_customer_profile"],
            candidate_sources=["customer_profile"],
        )
        plan = await selector.select(intent)
        assert plan.selected_tools == []


# ── Capping behaviour ────────────────────────────────────────────────────


class TestMaxToolCallCap:
    """The global or per-construct max_calls cap is enforced."""

    @pytest.mark.asyncio
    async def test_max_calls_enforced(self) -> None:
        """Set max_calls=2 for a billing inquiry, expect ≤ 2 tools."""
        selector = ToolSelector(max_calls=2)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=[
                "get_billing_history",
                "get_support_tickets",
                "get_ticket_status",
                "search_policies",
            ],
            candidate_sources=["billing_records", "support_tickets", "policies"],
        )
        plan = await selector.select(intent)

        # cap = min(2, 4) = 2
        assert len(plan.selected_tools) <= 2
        assert plan.selected_tools == ["get_billing_history", "get_support_tickets"]

    @pytest.mark.asyncio
    async def test_global_max_caps_intent_max(self) -> None:
        """When global max_calls is lower than intent max, global wins."""
        selector = ToolSelector(max_calls=1)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=[
                "get_billing_history",
                "get_support_tickets",
                "get_ticket_status",
                "search_policies",
            ],
            candidate_sources=["billing_records"],
        )
        plan = await selector.select(intent)

        # cap = min(1, 4) = 1
        assert len(plan.selected_tools) == 1
        assert plan.selected_tools == ["get_billing_history"]


class TestLowConfidenceCap:
    """Confidence < 0.3 caps to at most 1 tool."""

    @pytest.mark.asyncio
    async def test_low_confidence_caps_to_one(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.20,
            candidate_tools=[
                "get_billing_history",
                "get_support_tickets",
                "get_ticket_status",
                "search_policies",
            ],
            candidate_sources=["billing_records"],
        )
        plan = await selector.select(intent)

        # cap = min(10, 4, 1) = 1
        assert len(plan.selected_tools) <= 1
        assert plan.selected_tools == ["get_billing_history"]


# ── Validation behaviour ──────────────────────────────────────────────────


class TestUnknownToolFiltering:
    """Unknown tool names are silently filtered out."""

    @pytest.mark.asyncio
    async def test_unknown_tools_removed(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.80,
            candidate_tools=[
                "get_billing_history",
                "non_existent_tool",
                "another_fake",
                "get_support_tickets",
            ],
            candidate_sources=["billing_records"],
        )
        plan = await selector.select(intent)

        assert "non_existent_tool" not in plan.selected_tools
        assert "another_fake" not in plan.selected_tools
        assert plan.selected_tools == ["get_billing_history", "get_support_tickets"]

    @pytest.mark.asyncio
    async def test_empty_candidate_tools_returns_empty(self) -> None:
        selector = ToolSelector()
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.80,
            candidate_tools=[],
            candidate_sources=[],
        )
        plan = await selector.select(intent)
        assert plan.selected_tools == []


class TestInvalidIntentLabel:
    """Unknown intent label raises ``InvalidIntentLabelError``."""

    @pytest.mark.asyncio
    async def test_unknown_label_raises_invalid_intent_label_error(self) -> None:
        """A label that is not in the known set should raise."""
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="unknown_intent",
            confidence=0.80,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        with pytest.raises(
            InvalidIntentLabelError,
            match="Unknown intent label: unknown_intent",
        ):
            await selector.select(intent)

    @pytest.mark.asyncio
    async def test_nonexistent_label_raises_error(self) -> None:
        """Completely made-up label should also raise."""
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="this_does_not_exist_at_all",
            confidence=0.99,
            candidate_tools=[],
            candidate_sources=[],
        )
        with pytest.raises(InvalidIntentLabelError):
            await selector.select(intent)

    @pytest.mark.asyncio
    async def test_known_label_does_not_raise(self) -> None:
        """Known labels should not raise ``InvalidIntentLabelError``."""
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        plan = await selector.select(intent)
        assert plan.selected_tools == ["get_billing_history"]


# ── Defaults and overrides ────────────────────────────────────────────────


class TestDefaultsAndOverrides:
    """Default handling for customer_context and max_calls."""

    @pytest.mark.asyncio
    async def test_customer_context_defaults_to_empty_dict(self) -> None:
        selector = ToolSelector()
        intent = IntentAnalysisResult(
            intent_label="account_query",
            confidence=0.80,
            candidate_tools=["get_customer_profile"],
            candidate_sources=["customer_profile"],
        )
        plan = await selector.select(intent, customer_context=None)
        assert plan.customer_context == {}

    @pytest.mark.asyncio
    async def test_customer_context_passed_through(self) -> None:
        selector = ToolSelector()
        ctx = {"customer_id": "mock_001", "plan_tier": "premium"}
        intent = IntentAnalysisResult(
            intent_label="account_query",
            confidence=0.80,
            candidate_tools=["get_customer_profile"],
            candidate_sources=["customer_profile"],
        )
        plan = await selector.select(intent, customer_context=ctx)
        assert plan.customer_context == ctx
        assert plan.customer_context["customer_id"] == "mock_001"

    @pytest.mark.asyncio
    async def test_custom_max_calls_override(self) -> None:
        selector = ToolSelector(max_calls=3)
        assert selector._max_calls == 3

    @pytest.mark.asyncio
    async def test_default_max_calls_from_settings(self) -> None:
        selector = ToolSelector()
        # Default in settings is 6; if env overrides, that's fine — just
        # verify it's a reasonable positive integer.
        assert selector._max_calls > 0

    @pytest.mark.asyncio
    async def test_customer_context_not_mutated(self) -> None:
        """The selector must not mutate the passed customer_context."""
        selector = ToolSelector()
        ctx = {"customer_id": "mock_001"}
        ctx_copy = dict(ctx)
        intent = IntentAnalysisResult(
            intent_label="account_query",
            confidence=0.80,
            candidate_tools=["get_customer_profile"],
            candidate_sources=["customer_profile"],
        )
        await selector.select(intent, customer_context=ctx)
        assert ctx == ctx_copy


# ── Determinism ───────────────────────────────────────────────────────────


class TestDeterminism:
    """Same input always yields the same output — no randomness."""

    @pytest.mark.asyncio
    async def test_same_input_same_output(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=[
                "search_policies",
                "get_billing_history",
                "get_support_tickets",
                "get_ticket_status",
                "search_documentation",
            ],
            candidate_sources=["billing_records"],
        )
        plan1 = await selector.select(intent)
        plan2 = await selector.select(intent)

        assert plan1.selected_tools == plan2.selected_tools
        assert plan1.max_tool_calls == plan2.max_tool_calls
        assert plan1.customer_context == plan2.customer_context


# ── Output shape ──────────────────────────────────────────────────────────


class TestOutputShape:
    """ToolSelectionPlan is returned with the correct structure."""

    @pytest.mark.asyncio
    async def test_plan_has_expected_fields(self) -> None:
        selector = ToolSelector(max_calls=5)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history", "get_support_tickets"],
            candidate_sources=["billing_records"],
        )
        plan = await selector.select(intent, customer_context={"customer_id": "x"})

        assert isinstance(plan, ToolSelectionPlan)
        assert isinstance(plan.selected_tools, list)
        assert all(isinstance(t, str) for t in plan.selected_tools)
        assert isinstance(plan.customer_context, dict)
        assert isinstance(plan.max_tool_calls, int)
        assert plan.max_tool_calls == 5  # our override

    @pytest.mark.asyncio
    async def test_plan_with_context(self) -> None:
        selector = ToolSelector(max_calls=5)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        ctx = {"customer_id": "c123", "name": "Alice"}
        plan = await selector.select(intent, customer_context=ctx)

        assert plan.selected_tools == ["get_billing_history"]
        assert plan.customer_context == ctx
        assert plan.max_tool_calls == 5


# ── Deduplication ─────────────────────────────────────────────────────────


class TestDeduplication:
    """Duplicate tool names in candidate_tools are collapsed."""

    @pytest.mark.asyncio
    async def test_duplicates_are_removed(self) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.90,
            candidate_tools=[
                "get_billing_history",
                "get_billing_history",
                "get_support_tickets",
                "get_billing_history",
            ],
            candidate_sources=["billing_records"],
        )
        plan = await selector.select(intent)

        # "get_billing_history" should appear only once.
        assert plan.selected_tools.count("get_billing_history") == 1
        assert plan.selected_tools == ["get_billing_history", "get_support_tickets"]


# ── Parameterised cross-intent coverage ───────────────────────────────────


class TestIntentMappingParameterised:
    """Parameterised coverage of all intent → tool-list mappings."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("intent_label", "confidence", "candidate_tools", "expected"),
        [
            (
                "billing_inquiry",
                0.92,
                [
                    "get_billing_history",
                    "get_support_tickets",
                    "get_ticket_status",
                    "search_policies",
                    "search_documentation",
                ],
                [
                    "get_billing_history",
                    "get_support_tickets",
                    "get_ticket_status",
                    "search_policies",
                ],
            ),
            (
                "support_ticket",
                0.85,
                [
                    "get_support_tickets",
                    "get_ticket_status",
                    "search_documentation",
                    "search_policies",
                ],
                [
                    "get_support_tickets",
                    "get_ticket_status",
                    "search_documentation",
                ],
            ),
            (
                "knowledge_query",
                0.78,
                ["search_documentation", "search_policies"],
                ["search_documentation", "search_policies"],
            ),
            (
                "account_query",
                0.80,
                ["get_customer_profile", "get_subscription_status"],
                ["get_customer_profile", "get_subscription_status"],
            ),
            (
                "analytics_query",
                0.90,
                ["get_usage_analytics"],
                ["get_usage_analytics"],
            ),
            ("greeting", 0.95, ["get_billing_history"], []),
            ("other", 0.40, ["get_customer_profile"], []),
        ],
        ids=[
            "billing_inquiry",
            "support_ticket",
            "knowledge_query",
            "account_query",
            "analytics_query",
            "greeting",
            "other",
        ],
    )
    async def test_intent_mapping(
        self,
        intent_label: str,
        confidence: float,
        candidate_tools: list[str],
        expected: list[str],
    ) -> None:
        selector = ToolSelector(max_calls=10)
        intent = IntentAnalysisResult(
            intent_label=intent_label,
            confidence=confidence,
            candidate_tools=candidate_tools,
            candidate_sources=[],
        )
        plan = await selector.select(intent)
        assert plan.selected_tools == expected
