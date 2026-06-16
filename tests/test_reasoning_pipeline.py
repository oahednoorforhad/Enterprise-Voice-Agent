"""Tests for the ``ReasoningPipeline`` class.

Mocking strategy
----------------
``ReasoningPipeline`` depends on an injected ``LLMClient``.  Tests create an
``LLMClient`` with a mocked ``google.genai.Client`` so no real API calls
are ever made.  The mock SDK client's ``generate_content`` is configured to
return fake ``GenerateContentResponse`` objects with a pre-built
``_ReasoningLLMResponse`` as ``.parsed``.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from app.core.llm_client import LLMClient, LLMClientError

# Re-import the internal model so tests can construct fake LLM responses.
from app.reasoning.pipeline import ReasoningPipeline, _ReasoningLLMResponse
from app.schemas.reasoning import EvidenceItem, EvidencePackage, ReasoningOutput

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
    conclusion: str = "Based on the evidence, the customer is eligible.",
    evidence_cited: list[str] | None = None,
    reasoning_type: str = "evidence_corroboration",
    confidence: float = 0.85,
    warnings: list[str] | None = None,
) -> _ReasoningLLMResponse:
    """Convenience helper to build a ``_ReasoningLLMResponse`` instance."""
    return _ReasoningLLMResponse(
        conclusion=conclusion,
        evidence_cited=evidence_cited or [],
        reasoning_type=reasoning_type,
        confidence=confidence,
        warnings=warnings or [],
    )


def _make_evidence_item(
    source: str = "billing_records",
    tool_name: str = "get_billing_history",
    content: str = "Customer was charged $49.99 on 2026-05-15",
) -> EvidenceItem:
    """Convenience helper to build an ``EvidenceItem`` instance."""
    return EvidenceItem(
        source=source,
        tool_name=tool_name,
        content=content,
    )


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_sdk() -> MagicMock:
    """Fixture providing a mocked ``google.genai.Client``."""
    return _fake_sdk_client()


@pytest.fixture
def pipeline(mock_sdk: MagicMock) -> ReasoningPipeline:
    """Fixture providing a ``ReasoningPipeline`` with a mocked LLM client.

    The underlying SDK mock is available as the ``mock_sdk`` fixture so
    tests can configure return values or assert call parameters.
    """
    llm = LLMClient(api_key="sk-test", client=mock_sdk)
    return ReasoningPipeline(llm_client=llm)


@pytest.fixture
def empty_package() -> EvidencePackage:
    """An evidence package with no items and no failed tools."""
    return EvidencePackage(items=[], failed_tools=[], total_sources=0)


@pytest.fixture
def single_evidence_package() -> EvidencePackage:
    """An evidence package with one billing evidence item."""
    return EvidencePackage(
        items=[
            _make_evidence_item(
                source="billing_records",
                tool_name="get_billing_history",
                content="Customer was charged $49.99 on 2026-05-15",
            ),
        ],
        failed_tools=[],
        total_sources=1,
    )


@pytest.fixture
def multi_evidence_package() -> EvidencePackage:
    """An evidence package with multiple evidence items."""
    return EvidencePackage(
        items=[
            _make_evidence_item(
                source="billing_records",
                tool_name="get_billing_history",
                content="Customer was charged $49.99 on 2026-05-15",
            ),
            _make_evidence_item(
                source="support_tickets",
                tool_name="get_support_tickets",
                content="Ticket #1234: Billing discrepancy reported on 2026-05-16",
            ),
            _make_evidence_item(
                source="policies",
                tool_name="search_policies",
                content="Refund policy: 30-day money-back guarantee",
            ),
        ],
        failed_tools=["get_subscription_status"],
        total_sources=3,
    )


# ── Tests ─────────────────────────────────────────────────────────────────


class TestReasoningPipelineConstruction:
    """``ReasoningPipeline`` construction and type contract."""

    def test_accepts_llm_client(self, mock_sdk: MagicMock) -> None:
        """``ReasoningPipeline`` should accept an ``LLMClient`` instance."""
        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        pipeline = ReasoningPipeline(llm_client=llm)
        assert isinstance(pipeline, ReasoningPipeline)


class TestInsufficientEvidence:
    """Deterministic fallback when no evidence items are present."""

    @pytest.mark.asyncio
    async def test_empty_evidence_non_greeting_returns_deterministic_fallback(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        empty_package: EvidencePackage,
    ) -> None:
        """Empty evidence with non-greeting intent returns deterministic fallback
        and does NOT call the LLM."""
        result = await pipeline.reason(
            evidence_package=empty_package,
            intent="billing_inquiry",
        )

        assert isinstance(result, ReasoningOutput)
        assert result.conclusion == (
            "I do not have enough information to answer your question. "
            "Please provide more details or contact support for assistance."
        )
        assert result.evidence_cited == []
        assert result.reasoning_type == "insufficient_evidence"
        assert result.confidence == 0.0
        assert result.warnings == [
            "No evidence was retrieved to support this turn",
        ]

        # Verify the LLM was NOT called
        mock_sdk.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_evidence_with_none_intent(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        empty_package: EvidencePackage,
    ) -> None:
        """Empty evidence with ``None`` intent (unknown) returns fallback."""
        result = await pipeline.reason(
            evidence_package=empty_package,
            intent=None,
        )

        assert result.reasoning_type == "insufficient_evidence"
        assert result.confidence == 0.0
        mock_sdk.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_empty_evidence_without_intent_param(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        empty_package: EvidencePackage,
    ) -> None:
        """Empty evidence with no intent param (default None) returns fallback."""
        result = await pipeline.reason(
            evidence_package=empty_package,
        )

        assert result.reasoning_type == "insufficient_evidence"
        assert result.confidence == 0.0
        mock_sdk.aio.models.generate_content.assert_not_awaited()


class TestEmptyEvidenceGreeting:
    """Deterministic greeting response when intent is greeting/other."""

    @pytest.mark.asyncio
    async def test_greeting_without_customer_context(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        empty_package: EvidencePackage,
    ) -> None:
        """Empty evidence with greeting intent returns friendly greeting
        without personalisation."""
        result = await pipeline.reason(
            evidence_package=empty_package,
            intent="greeting",
        )

        assert isinstance(result, ReasoningOutput)
        assert "Good day" in result.conclusion
        assert "EVA" in result.conclusion
        assert result.evidence_cited == []
        assert result.reasoning_type == "greeting"
        assert result.confidence == 1.0
        assert result.warnings == []

        # Verify the LLM was NOT called
        mock_sdk.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_greeting_with_customer_context(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        empty_package: EvidencePackage,
    ) -> None:
        """Empty evidence with greeting intent includes customer name."""
        ctx = {"customer_id": "mock_001", "name": "Alice"}
        result = await pipeline.reason(
            evidence_package=empty_package,
            customer_context=ctx,
            intent="greeting",
        )

        assert "Alice" in result.conclusion
        assert "Good day" in result.conclusion
        assert result.reasoning_type == "greeting"
        assert result.confidence == 1.0
        mock_sdk.aio.models.generate_content.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_other_intent_empty_evidence(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        empty_package: EvidencePackage,
    ) -> None:
        """Empty evidence with 'other' intent also returns greeting-
        style response (treats as friendly fallback)."""
        result = await pipeline.reason(
            evidence_package=empty_package,
            intent="other",
        )

        assert "Good day" in result.conclusion
        assert result.reasoning_type == "greeting"
        assert result.confidence == 1.0
        mock_sdk.aio.models.generate_content.assert_not_awaited()


class TestEvidenceBackedReasoning:
    """LLM-based reasoning when evidence items are present."""

    @pytest.mark.asyncio
    async def test_calls_generate_structured(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """``reason()`` must call ``generate_structured()`` on the LLM client
        when evidence items exist."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(),
        )

        await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        mock_sdk.aio.models.generate_content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_returns_reasoning_output_instance(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """The return type must be ``ReasoningOutput``."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(),
        )

        result = await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        assert isinstance(result, ReasoningOutput)

    @pytest.mark.asyncio
    async def test_all_fields_populated_correctly(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """All ``ReasoningOutput`` fields should be populated from the LLM
        response."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                conclusion="The customer was charged $49.99 on May 15.",
                evidence_cited=["billing_records"],
                reasoning_type="evidence_corroboration",
                confidence=0.85,
                warnings=[],
            ),
        )

        result = await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        assert result.conclusion == "The customer was charged $49.99 on May 15."
        assert result.evidence_cited == ["billing_records"]
        assert result.reasoning_type == "evidence_corroboration"
        assert result.confidence == 0.85
        assert result.warnings == []

    @pytest.mark.asyncio
    async def test_evidence_cited_contains_source_names(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        multi_evidence_package: EvidencePackage,
    ) -> None:
        """``evidence_cited`` should contain source names from the evidence."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                evidence_cited=[
                    "billing_records",
                    "support_tickets",
                    "policies",
                ],
            ),
        )

        result = await pipeline.reason(
            evidence_package=multi_evidence_package,
            intent="billing_inquiry",
        )

        assert "billing_records" in result.evidence_cited
        assert "support_tickets" in result.evidence_cited
        assert "policies" in result.evidence_cited

    @pytest.mark.asyncio
    async def test_reasoning_type_is_valid(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """``reasoning_type`` should be one of the 4 valid types."""
        valid_types = {
            "evidence_corroboration",
            "policy_application",
            "root_cause_analysis",
            "decision_support",
        }

        for rtype in valid_types:
            mock_sdk.aio.models.generate_content.return_value = _parsed_response(
                _make_llm_response(reasoning_type=rtype),
            )

            result = await pipeline.reason(
                evidence_package=single_evidence_package,
                intent="billing_inquiry",
            )

            assert result.reasoning_type in valid_types

    @pytest.mark.asyncio
    async def test_confidence_within_range(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """``confidence`` should always be within 0.0 to 1.0 range."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(confidence=0.92),
        )

        result = await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        assert 0.0 <= result.confidence <= 1.0

    @pytest.mark.asyncio
    async def test_confidence_clamped_above_range(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """Confidence values above 1.0 should be clamped to 1.0."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(confidence=2.5),
        )

        result = await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        assert result.confidence == 1.0

    @pytest.mark.asyncio
    async def test_confidence_clamped_below_range(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """Confidence values below 0.0 should be clamped to 0.0."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(confidence=-0.5),
        )

        result = await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        assert result.confidence == 0.0

    @pytest.mark.asyncio
    async def test_warnings_populated(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """Warnings should be populated when evidence is contradictory or
        incomplete."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                conclusion="There is conflicting information about the charge.",
                evidence_cited=["billing_records", "support_tickets"],
                reasoning_type="evidence_corroboration",
                confidence=0.4,
                warnings=[
                    "Billing records show $49.99 but support ticket mentions "
                    "$39.99",
                    "The available evidence does not directly address the "
                    "refund question",
                ],
            ),
        )

        result = await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        assert len(result.warnings) > 0
        assert "Billing records" in result.warnings[0]
        assert "does not directly address" in result.warnings[1]

    @pytest.mark.asyncio
    async def test_customer_context_included_in_prompt(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """When customer_context is provided, it should appear in the prompt."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(),
        )

        ctx = {"customer_id": "mock_001", "name": "Alice", "plan_tier": "premium"}
        await pipeline.reason(
            evidence_package=single_evidence_package,
            customer_context=ctx,
            intent="billing_inquiry",
        )

        call_kwargs = mock_sdk.aio.models.generate_content.call_args.kwargs
        prompt = call_kwargs.get("contents", "")
        assert "mock_001" in prompt
        assert "Alice" in prompt
        assert "premium" in prompt

    @pytest.mark.asyncio
    async def test_evidence_items_formatted_in_prompt(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """Evidence items should be formatted in the prompt with
        source/tool_name/content."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(),
        )

        await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        call_kwargs = mock_sdk.aio.models.generate_content.call_args.kwargs
        prompt = call_kwargs.get("contents", "")
        assert "Source: billing_records" in prompt
        assert "Tool: get_billing_history" in prompt
        assert "Customer was charged $49.99" in prompt

    @pytest.mark.asyncio
    async def test_failed_tools_listed_in_prompt(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        multi_evidence_package: EvidencePackage,
    ) -> None:
        """Failed tools should be listed in the prompt."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(),
        )

        await pipeline.reason(
            evidence_package=multi_evidence_package,
            intent="billing_inquiry",
        )

        call_kwargs = mock_sdk.aio.models.generate_content.call_args.kwargs
        prompt = call_kwargs.get("contents", "")
        assert "Failed tools" in prompt
        assert "get_subscription_status" in prompt

    @pytest.mark.asyncio
    async def test_multi_evidence_formatted(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        multi_evidence_package: EvidencePackage,
    ) -> None:
        """Multiple evidence items should each be formatted with
        index numbers."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(),
        )

        await pipeline.reason(
            evidence_package=multi_evidence_package,
            intent="billing_inquiry",
        )

        call_kwargs = mock_sdk.aio.models.generate_content.call_args.kwargs
        prompt = call_kwargs.get("contents", "")
        assert "[Item 1]" in prompt
        assert "[Item 2]" in prompt
        assert "[Item 3]" in prompt

    @pytest.mark.asyncio
    async def test_intent_included_in_prompt(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """The intent should be included in the LLM prompt."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(),
        )

        await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        call_kwargs = mock_sdk.aio.models.generate_content.call_args.kwargs
        prompt = call_kwargs.get("contents", "")
        assert "Customer intent: billing_inquiry" in prompt

    @pytest.mark.asyncio
    async def test_invalid_reasoning_type_falls_back(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """An invalid reasoning_type from the LLM should fall back to
        'evidence_corroboration'."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(reasoning_type="invalid_type"),
        )

        result = await pipeline.reason(
            evidence_package=single_evidence_package,
            intent="billing_inquiry",
        )

        assert result.reasoning_type == "evidence_corroboration"


class TestLLMErrorHandling:
    """Error propagation from the LLM client."""

    @pytest.mark.asyncio
    async def test_llm_client_error_propagates(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        single_evidence_package: EvidencePackage,
    ) -> None:
        """``LLMClientError`` from the underlying client must propagate."""
        from google.genai.errors import APIError

        mock_sdk.aio.models.generate_content.side_effect = APIError(
            code=429,
            response_json={"error": {"message": "Rate limited"}},
        )

        with pytest.raises(LLMClientError, match="Gemini structured API call failed"):
            await pipeline.reason(
                evidence_package=single_evidence_package,
                intent="billing_inquiry",
            )


class TestOutputShape:
    """Verifying the full output shape matches ReasoningOutput."""

    @pytest.mark.asyncio
    async def test_full_output_shape(
        self,
        pipeline: ReasoningPipeline,
        mock_sdk: MagicMock,
        multi_evidence_package: EvidencePackage,
    ) -> None:
        """All fields should be correctly mapped to ReasoningOutput."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_llm_response(
                conclusion="The customer is eligible for a refund under the "
                "30-day policy.",
                evidence_cited=[
                    "billing_records",
                    "support_tickets",
                    "policies",
                ],
                reasoning_type="policy_application",
                confidence=0.78,
                warnings=[
                    "The billing record and ticket dates should be verified",
                ],
            ),
        )

        ctx = {"customer_id": "mock_001", "name": "Alice"}
        result = await pipeline.reason(
            evidence_package=multi_evidence_package,
            customer_context=ctx,
            intent="billing_inquiry",
        )

        assert result.conclusion == (
            "The customer is eligible for a refund under the 30-day policy."
        )
        assert result.evidence_cited == [
            "billing_records",
            "support_tickets",
            "policies",
        ]
        assert result.reasoning_type == "policy_application"
        assert result.confidence == 0.78
        assert result.warnings == [
            "The billing record and ticket dates should be verified",
        ]

    @pytest.mark.asyncio
    async def test_empty_evidence_without_intent_full_shape(
        self,
        pipeline: ReasoningPipeline,
        empty_package: EvidencePackage,
    ) -> None:
        """Empty evidence without intent returns the correct shape."""
        result = await pipeline.reason(
            evidence_package=empty_package,
        )

        assert result.conclusion is not None
        assert isinstance(result.conclusion, str)
        assert result.evidence_cited == []
        assert result.reasoning_type == "insufficient_evidence"
        assert result.confidence == 0.0
        assert isinstance(result.warnings, list)
        assert len(result.warnings) == 1
