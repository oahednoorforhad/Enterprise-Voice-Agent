"""Tests for the ``IntentAnalyzer`` class.

Mocking strategy
----------------
``IntentAnalyzer`` depends on an injected ``LLMClient``.  Tests create an
``LLMClient`` with a mocked ``google.genai.Client`` so no real API calls
are ever made.  The mock SDK client's ``generate_content`` is configured to
return fake ``GenerateContentResponse`` objects with a pre-built
``_IntentLLMResponse`` as ``.parsed``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.llm_client import LLMClient, LLMClientError

# Re-import the internal model so tests can construct fake LLM responses.
from app.orchestrator.intent_analyzer import IntentAnalyzer, _IntentLLMResponse
from app.schemas.reasoning import IntentAnalysisResult

# ── Helpers ───────────────────────────────────────────────────────────────


def _fake_sdk_client() -> MagicMock:
    """Return a ``MagicMock`` shaped like ``google.genai.Client``."""
    client = MagicMock()
    client.aio = MagicMock()
    client.aio.models = MagicMock()
    client.aio.models.generate_content = AsyncMock()
    return client


def _parsed_response(model: object) -> MagicMock:
    """Build a fake ``GenerateContentResponse`` with a pre-parsed model."""
    resp = MagicMock()
    resp.text = None
    resp.parsed = model
    resp.prompt_feedback = None
    return resp


def _make_llm_response(
    intent_label: str = "other",
    confidence: float = 0.5,
    candidate_tools: list[str] | None = None,
    candidate_sources: list[str] | None = None,
    notes: str | None = None,
) -> _IntentLLMResponse:
    """Convenience helper to build an ``_IntentLLMResponse`` instance."""
    return _IntentLLMResponse(
        intent_label=intent_label,
        confidence=confidence,
        candidate_tools=candidate_tools or [],
        candidate_sources=candidate_sources or [],
        notes=notes,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_sdk() -> MagicMock:
    """Fixture providing a mocked ``google.genai.Client``."""
    return _fake_sdk_client()


@pytest.fixture
def analyzer(mock_sdk: MagicMock) -> IntentAnalyzer:
    """Fixture providing an ``IntentAnalyzer`` with a mocked LLM client.

    The underlying SDK mock is available as the ``mock_sdk`` fixture so
    tests can configure return values or assert call parameters.
    """
    llm = LLMClient(api_key="sk-test", client=mock_sdk)
    return IntentAnalyzer(llm_client=llm)


# ── Tests ─────────────────────────────────────────────────────────────────


class TestIntentAnalyzerConstruction:
    """``IntentAnalyzer`` construction and type contract."""

    def test_accepts_llm_client(self, mock_sdk: MagicMock) -> None:
        """``IntentAnalyzer`` should accept an ``LLMClient`` instance."""
        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        analyzer = IntentAnalyzer(llm_client=llm)
        assert isinstance(analyzer, IntentAnalyzer)


class TestAnalyzeReturnsIntentAnalysisResult:
    """``analyze()`` contract: always returns an ``IntentAnalysisResult``."""

    @pytest.mark.asyncio
    async def test_returns_intent_analysis_result_instance(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """The return type must be ``IntentAnalysisResult``."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="billing_inquiry",
                confidence=0.92,
                candidate_tools=["get_billing_history"],
                candidate_sources=["billing_records"],
                notes="User is asking about charges",
            )
        )

        result = await analyzer.analyze("Why was I charged twice?")

        assert isinstance(result, IntentAnalysisResult)

    @pytest.mark.asyncio
    async def test_calls_generate_structured(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """``analyze()`` must call ``generate_structured()`` on the LLM client.

        We verify this by checking that the underlying SDK mock was invoked.
        """
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(intent_label="greeting", confidence=0.95)
        )

        await analyzer.analyze("Hello")

        mock_sdk.aio.models.generate_content.assert_awaited_once()


class TestBillingInquiry:
    """Billing inquiry classification."""

    @pytest.mark.asyncio
    async def test_english_billing_inquiry(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """English billing questions should return billing_inquiry intent."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="billing_inquiry",
                confidence=0.92,
                candidate_tools=[
                    "get_billing_history",
                    "get_support_tickets",
                    "search_policies",
                ],
                candidate_sources=["billing_records", "support_tickets", "policies"],
                notes="Customer is asking about duplicate charges",
            )
        )

        result = await analyzer.analyze("Why was I charged twice?")

        assert result.intent_label == "billing_inquiry"
        assert result.confidence >= 0.9
        assert "get_billing_history" in result.candidate_tools
        assert "billing_records" in result.candidate_sources

    @pytest.mark.asyncio
    async def test_bangla_billing_inquiry(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """Bangla billing questions should also classify as billing_inquiry."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="billing_inquiry",
                confidence=0.91,
                candidate_tools=[
                    "get_billing_history",
                    "get_support_tickets",
                    "search_policies",
                ],
                candidate_sources=["billing_records", "support_tickets", "policies"],
                notes="Customer is asking about being overcharged (Bangla)",
            )
        )

        result = await analyzer.analyze("আমাকে কেন দ্বিগুণ চার্জ করা হয়েছে?")

        assert result.intent_label == "billing_inquiry"
        assert "get_billing_history" in result.candidate_tools
        assert "billing_records" in result.candidate_sources


class TestSupportTicket:
    """Support ticket classification."""

    @pytest.mark.asyncio
    async def test_support_ticket(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """Questions about tickets should return support_ticket intent."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="support_ticket",
                confidence=0.88,
                candidate_tools=[
                    "get_support_tickets",
                    "get_ticket_status",
                    "search_documentation",
                ],
                candidate_sources=["support_tickets", "documentation"],
                notes="Customer wants to check ticket status",
            )
        )

        result = await analyzer.analyze("What is the status of my support ticket?")

        assert result.intent_label == "support_ticket"
        assert "get_support_tickets" in result.candidate_tools
        assert "support_tickets" in result.candidate_sources


class TestKnowledgeQuery:
    """Knowledge query classification."""

    @pytest.mark.asyncio
    async def test_knowledge_query(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """Questions about features/docs should return knowledge_query intent."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="knowledge_query",
                confidence=0.85,
                candidate_tools=["search_documentation", "search_policies"],
                candidate_sources=["documentation", "policies"],
                notes="Customer wants to know how to reset password",
            )
        )

        result = await analyzer.analyze("How do I reset my password?")

        assert result.intent_label == "knowledge_query"
        assert "search_documentation" in result.candidate_tools
        assert "documentation" in result.candidate_sources


class TestAccountQuery:
    """Account query classification."""

    @pytest.mark.asyncio
    async def test_account_query(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """Questions about profile/subscription should return account_query."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="account_query",
                confidence=0.90,
                candidate_tools=[
                    "get_customer_profile",
                    "get_subscription_status",
                ],
                candidate_sources=["customer_profile", "subscription"],
                notes="Customer wants to check account details",
            )
        )

        result = await analyzer.analyze("What plan am I on?")

        assert result.intent_label == "account_query"
        assert "get_customer_profile" in result.candidate_tools
        assert "customer_profile" in result.candidate_sources


class TestGreeting:
    """Greeting classification."""

    @pytest.mark.asyncio
    async def test_english_greeting(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """English greetings should return greeting intent with high confidence."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="greeting",
                confidence=0.95,
                notes="Simple greeting with no follow-up intent",
            )
        )

        result = await analyzer.analyze("Hello, how are you?")

        assert result.intent_label == "greeting"
        assert result.confidence >= 0.9
        assert result.candidate_tools == []
        assert result.candidate_sources == []

    @pytest.mark.asyncio
    async def test_bangla_greeting(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """Bangla greetings should also return greeting intent."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="greeting",
                confidence=0.95,
                notes="Bangla greeting detected",
            )
        )

        result = await analyzer.analyze("নমস্কার, কেমন আছেন?")

        assert result.intent_label == "greeting"
        assert result.confidence >= 0.9
        assert result.candidate_tools == []
        assert result.candidate_sources == []


class TestCustomerContext:
    """Customer context passing."""

    @pytest.mark.asyncio
    async def test_customer_context_passed_to_llm(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """When customer_context is provided, it should appear in the prompt."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(intent_label="account_query", confidence=0.90)
        )

        ctx = {"customer_id": "mock_001", "name": "Alice", "plan_tier": "premium"}
        await analyzer.analyze("What plan am I on?", customer_context=ctx)

        # Verify the prompt sent to the SDK included the customer context.
        call_kwargs = mock_sdk.aio.models.generate_content.call_args.kwargs
        prompt = call_kwargs.get("contents", "")
        assert "mock_001" in prompt
        assert "Alice" in prompt
        assert "premium" in prompt

    @pytest.mark.asyncio
    async def test_customer_context_none_by_default(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """When no customer_context is provided, only the message is in the prompt."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(intent_label="greeting", confidence=0.95)
        )

        await analyzer.analyze("Hi")

        call_kwargs = mock_sdk.aio.models.generate_content.call_args.kwargs
        prompt = call_kwargs.get("contents", "")
        assert "Customer message: Hi" in prompt
        assert "Customer context:" not in prompt


class TestErrorHandling:
    """Error propagation from the LLM client."""

    @pytest.mark.asyncio
    async def test_llm_client_error_propagates(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """``LLMClientError`` from the underlying client must propagate."""
        from google.genai.errors import APIError

        mock_sdk.aio.models.generate_content.side_effect = APIError(
            code=429,
            response_json={"error": {"message": "Rate limited"}},
        )

        with pytest.raises(LLMClientError, match="Gemini structured API call failed"):
            await analyzer.analyze("Hello")


class TestOutputShape:
    """Verifying the full output shape matches IntentAnalysisResult."""

    @pytest.mark.asyncio
    async def test_full_output_shape(
        self,
        mock_sdk: MagicMock,
        analyzer: IntentAnalyzer,
    ) -> None:
        """All fields should be correctly mapped to IntentAnalysisResult."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                intent_label="support_ticket",
                confidence=0.87,
                candidate_tools=["get_support_tickets", "search_documentation"],
                candidate_sources=["support_tickets", "documentation"],
                notes="Customer has an open ticket they want to follow up on",
            )
        )

        result = await analyzer.analyze("I need help with my open ticket #1234")

        assert result.intent_label == "support_ticket"
        assert result.confidence == 0.87
        assert result.candidate_tools == [
            "get_support_tickets",
            "search_documentation",
        ]
        assert result.candidate_sources == ["support_tickets", "documentation"]
        assert result.notes is not None
        assert "open ticket" in result.notes
