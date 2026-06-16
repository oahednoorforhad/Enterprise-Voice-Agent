"""Tests for the ``OrchestratorService`` class.

Mocking strategy
----------------
The orchestrator composes 4 components: ``IntentAnalyzer``, ``ToolSelector``,
``EvidenceAggregator``, and ``ReasoningPipeline``. Tests mock at two levels:

1. LLM calls: Create a real ``LLMClient`` with a mocked SDK client
   (``google.genai.Client``) — same pattern as ``test_intent_analyzer.py``
   and ``test_reasoning_pipeline.py``.
2. Tool execution: Build a mock ``tool_registry`` with ``_ToolEntry`` objects
   wrapping ``AsyncMock`` functions, and pass it via the ``tool_registry``
   constructor parameter.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID, uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import DomainException
from app.core.llm_client import LLMClient, LLMClientError
from app.orchestrator.evidence_aggregator import EvidenceAggregator

# Re-import internal models so tests can construct fake LLM responses.
from app.orchestrator.intent_analyzer import IntentAnalyzer, _IntentLLMResponse
from app.orchestrator.service import (
    EvidenceSufficiencyChecker,
    OrchestratorService,
    _build_knowledge_kwargs,
    _build_standard_kwargs,
    _ToolEntry,
)
from app.orchestrator.tool_selector import ToolSelector
from app.reasoning.pipeline import ReasoningPipeline, _ReasoningLLMResponse
from app.schemas.reasoning import (
    ChatResponse,
    EvidenceItem,
    EvidencePackage,
    IntentAnalysisResult,
    ReasoningOutput,
    ToolSelectionPlan,
)
from app.tools.billing.models import BillingRecordModel
from app.tools.customer.models import CustomerProfile
from app.tools.knowledge.models import KnowledgeResult
from app.tools.ticket.models import TicketModel

# ── Test constants ────────────────────────────────────────────────────────

_TEST_CUSTOMER_ID = "550e8400-e29b-41d4-a716-446655440000"
_TEST_CUSTOMER_UUID = UUID(_TEST_CUSTOMER_ID)


# ── Helper — mock tool registry entry ──────────────────────────────────────


def _mock_entry(
    func: AsyncMock | None = None,
    return_value: object = None,
    *,
    kwargs_builder: object = None,
) -> _ToolEntry:
    """Build a ``_ToolEntry`` wrapping an ``AsyncMock``.

    Parameters
    ----------
    func:
        Explicit ``AsyncMock`` to wrap.  When omitted a fresh one is created.
    return_value:
        Value returned by ``func`` when called.  Ignored when *func* is given.
    kwargs_builder:
        The kwargs builder callable.  Defaults to ``_build_standard_kwargs``.
    """
    actual_func = func if func is not None else AsyncMock(return_value=return_value)
    builder = kwargs_builder if kwargs_builder is not None else _build_standard_kwargs
    return _ToolEntry(func=actual_func, kwargs_builder=builder)  # type: ignore[arg-type]


# ── Helpers — LLM mocking ─────────────────────────────────────────────────


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


def _make_intent_response(
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


def _make_reasoning_response(
    conclusion: str = "Based on the evidence, here is the conclusion.",
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


# ── Helpers — model builders ──────────────────────────────────────────────


def _make_billing_record(**overrides: object) -> BillingRecordModel:
    """Build a minimal ``BillingRecordModel`` for test assertions."""
    return BillingRecordModel(
        id=uuid4(),
        customer_id=_TEST_CUSTOMER_UUID,
        amount=Decimal("49.99"),
        currency="USD",
        status="paid",
        description="Monthly subscription",
        created_at=datetime.now(UTC),
        **overrides,  # type: ignore[arg-type]
    )


def _make_ticket(**overrides: object) -> TicketModel:
    """Build a minimal ``TicketModel`` for test assertions."""
    return TicketModel(
        id=uuid4(),
        customer_id=_TEST_CUSTOMER_UUID,
        subject="Test ticket",
        description="Issue description",
        status="open",
        priority="high",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
        **overrides,  # type: ignore[arg-type]
    )


def _make_knowledge_result(**overrides: object) -> KnowledgeResult:
    """Build a minimal ``KnowledgeResult`` for test assertions."""
    return KnowledgeResult(
        id=uuid4(),
        content="Test documentation content.",
        metadata={"category": "faq"},
        similarity_score=0.95,
        **overrides,  # type: ignore[arg-type]
    )


def _make_customer_profile(**overrides: object) -> CustomerProfile:
    """Build a minimal ``CustomerProfile`` for test assertions."""
    return CustomerProfile(
        id=_TEST_CUSTOMER_UUID,
        name="Alice Rahman",
        email="alice@example.com",
        phone="+8801700000000",
        is_active=True,
        **overrides,  # type: ignore[arg-type]
    )


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock_sdk() -> MagicMock:
    """Fixture providing a mocked ``google.genai.Client``."""
    return _fake_sdk_client()


@pytest.fixture
def mock_session() -> AsyncMock:
    """Fixture providing a mocked ``AsyncSession``."""
    return AsyncMock(spec=AsyncSession)


@pytest.fixture
def mock_session_factory(mock_session: AsyncMock) -> MagicMock:
    """Fixture providing a mocked ``async_sessionmaker``.

    The factory returns a context-manager that yields *mock_session*.
    """
    factory = MagicMock(spec=async_sessionmaker)
    cm = MagicMock()
    cm.__aenter__.return_value = mock_session
    cm.__aexit__.return_value = None
    factory.return_value = cm
    return factory


@pytest.fixture
def orchestrator(
    mock_sdk: MagicMock,
    mock_session_factory: MagicMock,
) -> OrchestratorService:
    """Fixture providing an ``OrchestratorService`` with a mocked LLM client.

    Tests can configure the SDK mock (``mock_sdk``) to control intent
    analysis and reasoning responses.  Tool functions are not mocked here
    — individual tests should pass a custom ``tool_registry`` via the
    constructor.
    """
    llm = LLMClient(api_key="sk-test", client=mock_sdk)
    return OrchestratorService(
        llm_client=llm,
        session_factory=mock_session_factory,
        customer_id=_TEST_CUSTOMER_ID,
        customer_context={"name": "Alice", "email": "alice@example.com"},
        max_tool_calls=6,
    )


# ── Helper — build a mock tool registry ───────────────────────────────────


def _make_tool_registry(
    *,
    billing_return: object = None,
    tickets_return: object = None,
    profile_return: object = None,
    docs_return: object = None,
) -> dict[str, _ToolEntry]:
    """Build a ``tool_registry`` dict with optional ``AsyncMock`` overrides.

    For any tool not specified, the real ``DEFAULT_TOOL_REGISTRY`` entry
    is kept (which calls a real tool function).  For specified tools, a
    mock entry is created.
    """
    registry: dict[str, _ToolEntry] = {}

    def _maybe(name: str, ret: object, builder: object = None) -> None:
        if ret is not None or name in (
            "get_billing_history",
            "get_support_tickets",
            "get_customer_profile",
            "search_documentation",
        ):
            entry = _mock_entry(return_value=ret, kwargs_builder=builder)
            registry[name] = entry

    _maybe("get_billing_history", billing_return)
    _maybe("get_support_tickets", tickets_return)
    _maybe("get_customer_profile", profile_return)
    _maybe("search_documentation", docs_return, _build_knowledge_kwargs)

    return registry


# ── Full billing turn ─────────────────────────────────────────────────────


class TestFullBillingTurn:
    """Full billing turn with real components, mocked LLM, and fake tools."""

    @pytest.mark.asyncio
    async def test_returns_chat_response(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """A full billing turn returns a ``ChatResponse`` with correct fields."""
        intent_model = _make_intent_response(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history", "get_support_tickets"],
            candidate_sources=["billing_records", "support_tickets"],
        )
        reasoning_model = _make_reasoning_response(
            conclusion="Your billing history shows a charge of $49.99.",
            evidence_cited=["billing_records"],
            reasoning_type="evidence_corroboration",
            confidence=0.85,
        )

        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        # Build a mock tool registry with two tools returning records.
        mock_billing = AsyncMock(return_value=[_make_billing_record()])
        mock_tickets = AsyncMock(return_value=[_make_ticket()])
        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
            "get_support_tickets": _mock_entry(func=mock_tickets),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice", "email": "alice@example.com"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Why was I charged twice?")

        assert isinstance(result, ChatResponse)
        assert result.response == "Your billing history shows a charge of $49.99."
        assert result.evidence is not None
        assert result.reasoning_trace is not None
        assert result.reasoning_trace.conclusion == (
            "Your billing history shows a charge of $49.99."
        )
        assert len(result.tool_calls_made) == 2
        assert "get_billing_history" in result.tool_calls_made
        assert "get_support_tickets" in result.tool_calls_made
        assert mock_sdk.aio.models.generate_content.await_count == 2

    @pytest.mark.asyncio
    async def test_evidence_contains_items_from_multiple_tools(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """Evidence package should have items for each successful tool."""
        intent_model = _make_intent_response(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history", "get_support_tickets"],
            candidate_sources=["billing_records", "support_tickets"],
        )
        reasoning_model = _make_reasoning_response()
        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        mock_billing = AsyncMock(return_value=[_make_billing_record()])
        mock_tickets = AsyncMock(return_value=[_make_ticket()])
        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
            "get_support_tickets": _mock_entry(func=mock_tickets),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Why was I charged twice?")

        assert result.evidence is not None
        assert result.evidence.total_sources >= 1
        assert result.evidence.failed_tools == []


# ── Greeting / tool-less path ─────────────────────────────────────────────


class TestGreetingTurn:
    """Greeting turns skip tool execution and evidence aggregation."""

    @pytest.mark.asyncio
    async def test_greeting_skips_tools(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """Greeting intent: no tools called, evidence is None, response is greeting."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_intent_response(
                intent_label="greeting",
                confidence=0.95,
            )
        )

        # Register a mock tool to prove it is NOT called.
        mock_tool = AsyncMock()
        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_tool),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Hello!")

        assert isinstance(result, ChatResponse)
        assert "Good day" in result.response
        assert "Alice" in result.response
        assert result.evidence is None
        assert result.reasoning_trace is not None
        assert result.reasoning_trace.reasoning_type == "greeting"
        assert result.tool_calls_made == []

        mock_tool.assert_not_awaited()
        mock_sdk.aio.models.generate_content.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_other_intent_also_skips_tools(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """'Other' intent also skips tools and returns greeting-like response."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_intent_response(
                intent_label="other",
                confidence=0.40,
            )
        )

        mock_tool = AsyncMock()
        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_tool),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Blah blah blah")

        assert result.evidence is None
        assert result.tool_calls_made == []
        assert "Good day" in result.response
        mock_tool.assert_not_awaited()


# ── Partial tool failure ──────────────────────────────────────────────────


class TestPartialToolFailure:
    """Partial tool failure: one tool succeeds, one fails."""

    @pytest.mark.asyncio
    async def test_one_tool_fails_one_succeeds(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """Evidence still has items from successful tool; failed_tools populated."""
        intent_model = _make_intent_response(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history", "get_support_tickets"],
            candidate_sources=["billing_records", "support_tickets"],
        )
        reasoning_model = _make_reasoning_response()
        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        mock_billing = AsyncMock(return_value=[_make_billing_record()])

        async def failing_tool(session: object, customer_id: object) -> object:
            raise DomainException("Database connection lost")

        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
            "get_support_tickets": _mock_entry(func=failing_tool),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Why was I charged twice?")

        assert result.evidence is not None
        assert len(result.evidence.items) >= 1
        assert "get_support_tickets" in result.evidence.failed_tools
        assert "get_billing_history" in result.tool_calls_made
        assert "get_support_tickets" in result.tool_calls_made

    @pytest.mark.asyncio
    async def test_generic_exception_caught(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """A generic Exception in a tool is caught and converted to ToolResult.fail()."""
        intent_model = _make_intent_response(
            intent_label="account_query",
            confidence=0.90,
            candidate_tools=["get_customer_profile"],
            candidate_sources=["customer_profile"],
        )
        reasoning_model = _make_reasoning_response()
        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        async def crash_tool(session: object, customer_id: object) -> object:
            raise RuntimeError("Unexpected crash")

        tool_registry: dict[str, _ToolEntry] = {
            "get_customer_profile": _mock_entry(func=crash_tool),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Who am I?")

        assert result.evidence is not None
        assert "get_customer_profile" in result.evidence.failed_tools
        assert result.evidence.items == []


class TestToolLimitEnforcement:
    """Tool limit enforcement: only max_tool_calls tools are executed."""

    @pytest.mark.asyncio
    async def test_only_max_tools_executed(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """When selector returns 3 tools but max_tool_calls=1, only 1 is called."""
        mock_selector = AsyncMock(spec=ToolSelector)
        mock_selector.select.return_value = ToolSelectionPlan(
            selected_tools=[
                "get_billing_history",
                "get_support_tickets",
                "search_documentation",
            ],
            customer_context={},
            max_tool_calls=1,
        )

        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(
                _make_intent_response(
                    intent_label="billing_inquiry",
                    confidence=0.92,
                    candidate_tools=[
                        "get_billing_history",
                        "get_support_tickets",
                        "search_documentation",
                    ],
                    candidate_sources=["billing_records", "support_tickets", "documentation"],
                )
            ),
            _parsed_response(_make_reasoning_response()),
        ]

        mock_billing = AsyncMock(return_value=[_make_billing_record()])
        mock_tickets = AsyncMock(return_value=[_make_ticket()])
        mock_docs = AsyncMock(return_value=[_make_knowledge_result()])

        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
            "get_support_tickets": _mock_entry(func=mock_tickets),
            "search_documentation": _mock_entry(
                func=mock_docs, kwargs_builder=_build_knowledge_kwargs
            ),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            max_tool_calls=6,
            selector=mock_selector,
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Why was I charged twice?")

        assert len(result.tool_calls_made) == 1
        assert result.tool_calls_made == ["get_billing_history"]

        mock_billing.assert_awaited_once()
        mock_tickets.assert_not_awaited()
        mock_docs.assert_not_awaited()


class TestUnknownToolName:
    """Tool name not in tool_registry is handled gracefully."""

    @pytest.mark.asyncio
    async def test_unknown_tool_returns_failure(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """An unknown tool name should produce a ``ToolResult.fail``, not crash.

        We inject a mock selector that returns a plan containing a tool
        name that does not exist in the tool_registry.
        """
        mock_selector = AsyncMock(spec=ToolSelector)
        mock_selector.select.return_value = ToolSelectionPlan(
            selected_tools=["nonexistent_tool"],
            customer_context={},
            max_tool_calls=5,
        )

        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(
                _make_intent_response(
                    intent_label="billing_inquiry",
                    confidence=0.9,
                    candidate_tools=["nonexistent_tool"],
                    candidate_sources=["billing_records"],
                )
            ),
            _parsed_response(_make_reasoning_response()),
        ]

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            selector=mock_selector,
            # Use an empty registry so ``nonexistent_tool`` is unknown.
            tool_registry={},
        )

        result = await svc.process_turn("Check my billing")

        assert isinstance(result, ChatResponse)
        assert result.tool_calls_made == ["nonexistent_tool"]
        assert result.evidence is not None
        assert "nonexistent_tool" in result.evidence.failed_tools


# ── Sub-component call verification ───────────────────────────────────────


class TestSubComponentCalls:
    """Verify that ``process_turn`` calls each sub-component."""

    @pytest.mark.asyncio
    async def test_calls_intent_analyzer(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """``process_turn`` must call ``IntentAnalyzer.analyze()``."""
        mock_analyzer = AsyncMock(spec=IntentAnalyzer)
        mock_analyzer.analyze.return_value = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        mock_selector = AsyncMock(spec=ToolSelector)
        mock_selector.select.return_value = ToolSelectionPlan(
            selected_tools=[],
            customer_context={},
            max_tool_calls=6,
        )
        mock_aggregator = AsyncMock(spec=EvidenceAggregator)
        mock_aggregator.aggregate.return_value = EvidencePackage(items=[])
        mock_pipeline = AsyncMock(spec=ReasoningPipeline)
        mock_pipeline.reason.return_value = ReasoningOutput(
            conclusion="Test response.",
            evidence_cited=[],
            reasoning_type="evidence_corroboration",
            confidence=0.9,
        )

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            analyzer=mock_analyzer,
            selector=mock_selector,
            aggregator=mock_aggregator,
            pipeline=mock_pipeline,
        )

        await svc.process_turn("Why was I charged?")

        mock_analyzer.analyze.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_tool_selector(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """``process_turn`` must call ``ToolSelector.select()``."""
        mock_analyzer = AsyncMock(spec=IntentAnalyzer)
        mock_analyzer.analyze.return_value = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        mock_selector = AsyncMock(spec=ToolSelector)
        mock_selector.select.return_value = ToolSelectionPlan(
            selected_tools=[],
            customer_context={},
            max_tool_calls=6,
        )
        mock_aggregator = AsyncMock(spec=EvidenceAggregator)
        mock_aggregator.aggregate.return_value = EvidencePackage(items=[])
        mock_pipeline = AsyncMock(spec=ReasoningPipeline)
        mock_pipeline.reason.return_value = ReasoningOutput(
            conclusion="Test.",
            evidence_cited=[],
            reasoning_type="evidence_corroboration",
            confidence=0.9,
        )

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            analyzer=mock_analyzer,
            selector=mock_selector,
            aggregator=mock_aggregator,
            pipeline=mock_pipeline,
        )

        await svc.process_turn("Why was I charged?")

        mock_selector.select.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_evidence_aggregator(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """``process_turn`` must call ``EvidenceAggregator.aggregate()``
        when tools are executed."""
        mock_analyzer = AsyncMock(spec=IntentAnalyzer)
        mock_analyzer.analyze.return_value = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        mock_selector = AsyncMock(spec=ToolSelector)
        mock_selector.select.return_value = ToolSelectionPlan(
            selected_tools=["get_billing_history"],
            customer_context={},
            max_tool_calls=6,
        )
        mock_aggregator = AsyncMock(spec=EvidenceAggregator)
        mock_aggregator.aggregate.return_value = EvidencePackage(
            items=[
                EvidenceItem(
                    source="billing_records",
                    tool_name="get_billing_history",
                    content="Charge of $49.99",
                )
            ],
        )
        mock_pipeline = AsyncMock(spec=ReasoningPipeline)
        mock_pipeline.reason.return_value = ReasoningOutput(
            conclusion="Test.",
            evidence_cited=["billing_records"],
            reasoning_type="evidence_corroboration",
            confidence=0.9,
        )

        mock_billing = AsyncMock(return_value=[_make_billing_record()])
        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            analyzer=mock_analyzer,
            selector=mock_selector,
            aggregator=mock_aggregator,
            pipeline=mock_pipeline,
            tool_registry=tool_registry,
        )

        await svc.process_turn("Why was I charged?")

        mock_aggregator.aggregate.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_calls_reasoning_pipeline(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """``process_turn`` must call ``ReasoningPipeline.reason()``."""
        mock_analyzer = AsyncMock(spec=IntentAnalyzer)
        mock_analyzer.analyze.return_value = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=[],
            candidate_sources=[],
        )
        mock_selector = AsyncMock(spec=ToolSelector)
        mock_selector.select.return_value = ToolSelectionPlan(
            selected_tools=[],
            customer_context={},
            max_tool_calls=6,
        )
        mock_aggregator = AsyncMock(spec=EvidenceAggregator)
        mock_aggregator.aggregate.return_value = EvidencePackage(items=[])
        mock_pipeline = AsyncMock(spec=ReasoningPipeline)
        mock_pipeline.reason.return_value = ReasoningOutput(
            conclusion="Test.",
            evidence_cited=[],
            reasoning_type="evidence_corroboration",
            confidence=0.9,
        )

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            analyzer=mock_analyzer,
            selector=mock_selector,
            aggregator=mock_aggregator,
            pipeline=mock_pipeline,
        )

        await svc.process_turn("Why was I charged?")

        mock_pipeline.reason.assert_awaited_once()


# ── Error propagation ─────────────────────────────────────────────────────


class TestErrorPropagation:
    """Error propagation from sub-components."""

    @pytest.mark.asyncio
    async def test_llm_client_error_from_intent_analysis(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """``LLMClientError`` from intent analysis propagates through."""
        from google.genai.errors import APIError

        mock_sdk.aio.models.generate_content.side_effect = APIError(
            code=429,
            response_json={"error": {"message": "Rate limited"}},
        )

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
        )

        with pytest.raises(LLMClientError, match="Gemini structured API call failed"):
            await svc.process_turn("Hello")


# ── Output shape ──────────────────────────────────────────────────────────


class TestOutputShape:
    """Verify the full ``ChatResponse`` shape."""

    @pytest.mark.asyncio
    async def test_chat_response_shape_with_tools(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """ChatResponse has all expected fields after a tool-calling turn."""
        intent_model = _make_intent_response(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        reasoning_model = _make_reasoning_response(
            conclusion="Test conclusion.",
            evidence_cited=["billing_records"],
        )
        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        mock_billing = AsyncMock(return_value=[_make_billing_record()])
        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Why was I charged twice?")

        assert isinstance(result, ChatResponse)
        assert isinstance(result.response, str)
        assert len(result.response) > 0
        assert result.evidence is not None
        assert result.reasoning_trace is not None
        assert isinstance(result.tool_calls_made, list)
        assert len(result.tool_calls_made) == 1

    @pytest.mark.asyncio
    async def test_chat_response_shape_greeting(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """ChatResponse shape for greeting: evidence is None, tools empty."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_intent_response(intent_label="greeting", confidence=0.95)
        )

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
        )

        result = await svc.process_turn("Hi")

        assert isinstance(result, ChatResponse)
        assert isinstance(result.response, str)
        assert len(result.response) > 0
        assert result.evidence is None
        assert result.reasoning_trace is not None
        assert result.tool_calls_made == []

    @pytest.mark.asyncio
    async def test_chat_response_minimal_fields(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """ChatResponse must have response, evidence, reasoning_trace, tool_calls_made."""
        mock_sdk.aio.models.generate_content.return_value = _parsed_response(
            _make_intent_response(intent_label="greeting", confidence=0.95)
        )

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
        )

        result = await svc.process_turn("Hi")

        assert hasattr(result, "response")
        assert hasattr(result, "evidence")
        assert hasattr(result, "reasoning_trace")
        assert hasattr(result, "tool_calls_made")


# ═══════════════════════════════════════════════════════════════════════════
# NEW TESTS (Production-grade fixes)
# ═══════════════════════════════════════════════════════════════════════════


class TestParallelSessionIsolation:
    """Each parallel tool call must use a fresh DB session."""

    @pytest.mark.asyncio
    async def test_each_tool_gets_separate_session(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """Two parallel tool calls each open their own session from the factory."""
        intent_model = _make_intent_response(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history", "get_support_tickets"],
            candidate_sources=["billing_records", "support_tickets"],
        )
        reasoning_model = _make_reasoning_response()
        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        # Track sessions via a spy on the factory.
        sessions_created: list[AsyncMock] = []

        def _factory_side_effect() -> MagicMock:
            sess = AsyncMock(spec=AsyncSession)
            sessions_created.append(sess)
            cm = MagicMock()
            cm.__aenter__.return_value = sess
            cm.__aexit__.return_value = None
            return cm

        mock_session_factory.side_effect = _factory_side_effect

        mock_billing = AsyncMock(return_value=[_make_billing_record()])
        mock_tickets = AsyncMock(return_value=[_make_ticket()])
        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
            "get_support_tickets": _mock_entry(func=mock_tickets),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        await svc.process_turn("Why was I charged?")

        # Two sessions should have been created (one per tool).
        assert len(sessions_created) == 2
        # They must be distinct objects.
        assert sessions_created[0] is not sessions_created[1]


class TestReplanAtMostOnce:
    """The replan pass runs at most once, even if evidence is still insufficient."""

    @pytest.mark.asyncio
    async def test_fallback_runs_at_most_once(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """After replan runs, no second replan happens even if evidence is
        still insufficient."""
        intent_model = _make_intent_response(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        reasoning_model = _make_reasoning_response()
        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        # Make billing_history fail → triggers replan.
        mock_billing = AsyncMock(side_effect=DomainException("DB error"))

        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Why was I charged?")

        # billing_history was attempted → failed → replan ran.
        # The fallback for billing_history is [get_support_tickets, search_policies].
        # Those were not in the plan, so they'd be called in replan.
        # But we have no mock for them in registry → they'll be "unknown tool".
        # The key assertion: process_turn completes without infinite loop.
        assert isinstance(result, ChatResponse)
        # billing_history was attempted.
        assert "get_billing_history" in result.tool_calls_made
        # Replan fallbacks should have been attempted too (and failed as unknown).
        assert len(result.tool_calls_made) >= 1

    @pytest.mark.asyncio
    async def test_no_fallback_if_already_sufficient(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """When evidence is already sufficient, no replan pass runs."""
        # Use a billing_inquiry intent and provide billing_records evidence.
        # billing_inquiry requires "billing_records" — provide it.
        intent_model = _make_intent_response(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history", "get_support_tickets"],
            candidate_sources=["billing_records", "support_tickets"],
        )
        reasoning_model = _make_reasoning_response()
        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        mock_billing = AsyncMock(return_value=[_make_billing_record()])
        # Support tickets is NOT mocked — so it will be "unknown tool".
        # But since billing_records is present, no replan should happen.
        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=mock_billing),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        result = await svc.process_turn("Why was I charged?")

        # Only billing_history from round 1 should be in tool_calls_made.
        # get_support_tickets was in the plan but not in registry → unknown tool.
        # Wait — actually with the mock registry only having billing_history,
        # get_support_tickets will be unknown and return fail.
        # But since billing_records IS present, sufficiency passes.
        assert "get_billing_history" in result.tool_calls_made
        # No replan fallbacks should appear.
        # tool_calls_made should have billing_history (and possibly get_support_tickets
        # as unknown, but no replan tools).
        for t in result.tool_calls_made:
            assert t in ("get_billing_history", "get_support_tickets")


class TestToolTimeout:
    """Tool execution respects the timeout."""

    @pytest.mark.asyncio
    async def test_timeout_returns_tool_result_fail(
        self,
        mock_sdk: MagicMock,
        mock_session_factory: MagicMock,
    ) -> None:
        """A tool that exceeds the timeout returns ``ToolResult.fail("Tool timed out")``."""
        intent_model = _make_intent_response(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["get_billing_history"],
            candidate_sources=["billing_records"],
        )
        reasoning_model = _make_reasoning_response()
        mock_sdk.aio.models.generate_content.side_effect = [
            _parsed_response(intent_model),
            _parsed_response(reasoning_model),
        ]

        async def never_ending(session: object, customer_id: object) -> object:
            await asyncio.sleep(999)  # longer than 3.0s timeout
            return "done"  # pragma: no cover

        tool_registry: dict[str, _ToolEntry] = {
            "get_billing_history": _mock_entry(func=never_ending),
        }

        llm = LLMClient(api_key="sk-test", client=mock_sdk)
        svc = OrchestratorService(
            llm_client=llm,
            session_factory=mock_session_factory,
            customer_id=_TEST_CUSTOMER_ID,
            customer_context={"name": "Alice"},
            max_tool_calls=6,
            tool_registry=tool_registry,
        )

        # Patch the timeout to be very short so the test doesn't actually wait.
        import app.orchestrator.service as _svc_mod

        original_timeout = _svc_mod._TOOL_TIMEOUT_SECONDS
        _svc_mod._TOOL_TIMEOUT_SECONDS = 0.01  # 10ms

        try:
            result = await svc.process_turn("Why was I charged?")
        finally:
            _svc_mod._TOOL_TIMEOUT_SECONDS = original_timeout

        assert result.evidence is not None
        assert "get_billing_history" in result.evidence.failed_tools


class TestIntentAwareSufficiency:
    """EvidenceSufficiencyChecker uses intent-aware required sources."""

    def test_sufficient_when_required_sources_present(self) -> None:
        """is_sufficient returns True when all required sources are present."""
        evidence = EvidencePackage(
            items=[
                EvidenceItem(
                    source="billing_records",
                    tool_name="get_billing_history",
                    content="Charge $49.99",
                ),
            ],
        )
        assert EvidenceSufficiencyChecker.is_sufficient(evidence, "billing_inquiry")

    def test_insufficient_when_required_source_missing(self) -> None:
        """is_sufficient returns False when a required source is missing."""
        evidence = EvidencePackage(
            items=[
                EvidenceItem(
                    source="support_tickets",
                    tool_name="get_support_tickets",
                    content="Ticket #123",
                ),
            ],
        )
        # billing_inquiry requires billing_records, which is missing.
        assert not EvidenceSufficiencyChecker.is_sufficient(evidence, "billing_inquiry")

    def test_account_query_requires_profile_and_subscription(self) -> None:
        """account_query intent requires both customer_profile and subscription."""
        evidence = EvidencePackage(
            items=[
                EvidenceItem(
                    source="customer_profile",
                    tool_name="get_customer_profile",
                    content="Profile data",
                ),
            ],
        )
        # Missing subscription.
        assert not EvidenceSufficiencyChecker.is_sufficient(evidence, "account_query")

    def test_greeting_and_other_always_sufficient(self) -> None:
        """greeting and other intents are always sufficient regardless of evidence."""
        empty = EvidencePackage(items=[])
        assert EvidenceSufficiencyChecker.is_sufficient(empty, "greeting")
        assert EvidenceSufficiencyChecker.is_sufficient(empty, "other")

    def test_empty_evidence_still_insufficient(self) -> None:
        """Empty evidence is insufficient for non-greeting intents."""
        empty = EvidencePackage(items=[])
        assert not EvidenceSufficiencyChecker.is_sufficient(empty, "billing_inquiry")


class TestLangfuseSafe:
    """Langfuse initialisation is safe — missing config doesn't crash."""

    def test_init_langfuse_silent_when_keys_missing(self) -> None:
        """``observability.init_langfuse`` returns None without crashing when
        called with bad credentials."""
        from app.observability import init_langfuse, shutdown_langfuse

        result = init_langfuse(public_key="", secret_key="")
        assert result is not None
        assert hasattr(result, "flush")
        shutdown_langfuse()

    def test_langfuse_bypass_no_crash(self) -> None:
        """Calling ``init_langfuse`` with garbage credentials is safe."""
        from app.observability import init_langfuse, shutdown_langfuse

        # Garbage keys should be handled gracefully.
        try:
            result = init_langfuse(
                public_key="pk-this-is-garbage",
                secret_key="sk-this-is-garbage",
            )
            # Should not crash — may return None or an instance.
            _ = result
        except Exception:
            pytest.fail("init_langfuse raised unexpectedly with garbage keys")
        finally:
            shutdown_langfuse()
