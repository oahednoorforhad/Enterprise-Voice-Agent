"""Tests for the reasoning / intent Pydantic schemas.

Covers construction, JSON serialisation, and missing-field validation
for every model in ``app.schemas.reasoning``.
"""

import json

import pytest
from pydantic import ValidationError

from app.schemas.reasoning import (
    ChatRequest,
    ChatResponse,
    EvidenceItem,
    EvidencePackage,
    IntentAnalysisResult,
    ReasoningOutput,
    ToolSelectionPlan,
)

# ── IntentAnalysisResult ──────────────────────────────────────────────────


class TestIntentAnalysisResult:
    def test_minimal(self) -> None:
        obj = IntentAnalysisResult(
            intent_label="billing_inquiry",
            confidence=0.92,
            candidate_tools=["tool_billing"],
            candidate_sources=["billing_records"],
        )
        d = json.loads(obj.model_dump_json())
        assert d["intent_label"] == "billing_inquiry"
        assert d["confidence"] == 0.92
        assert d["notes"] is None  # default

    def test_missing_intent_label(self) -> None:
        with pytest.raises(ValidationError):
            IntentAnalysisResult(
                confidence=0.92, candidate_tools=[], candidate_sources=[]
            )

    def test_missing_confidence(self) -> None:
        with pytest.raises(ValidationError):
            IntentAnalysisResult(
                intent_label="billing_inquiry",
                candidate_tools=[],
                candidate_sources=[],
            )

    def test_with_notes(self) -> None:
        obj = IntentAnalysisResult(
            intent_label="refund_request",
            confidence=0.85,
            candidate_tools=["tool_billing", "tool_ticket"],
            candidate_sources=["billing_records", "support_tickets", "refund_policy"],
            notes="Ambiguous — customer may also need subscription lookup",
        )
        d = json.loads(obj.model_dump_json())
        assert d["notes"] is not None
        assert "Ambiguous" in d["notes"]


# ── ToolSelectionPlan ────────────────────────────────────────────────────


class TestToolSelectionPlan:
    def test_minimal(self) -> None:
        obj = ToolSelectionPlan(
            selected_tools=["tool_billing", "tool_ticket"],
            customer_context={"customer_id": "mock_001", "plan_tier": "premium"},
            max_tool_calls=3,
        )
        d = json.loads(obj.model_dump_json())
        assert d["selected_tools"] == ["tool_billing", "tool_ticket"]
        assert d["customer_context"]["customer_id"] == "mock_001"
        assert d["max_tool_calls"] == 3

    def test_missing_selected_tools(self) -> None:
        with pytest.raises(ValidationError):
            ToolSelectionPlan(customer_context={}, max_tool_calls=3)

    def test_missing_customer_context(self) -> None:
        with pytest.raises(ValidationError):
            ToolSelectionPlan(selected_tools=[], max_tool_calls=3)

    def test_missing_max_tool_calls(self) -> None:
        with pytest.raises(ValidationError):
            ToolSelectionPlan(selected_tools=[], customer_context={})

    def test_empty_customer_context(self) -> None:
        obj = ToolSelectionPlan(
            selected_tools=["tool_knowledge"],
            customer_context={},
            max_tool_calls=1,
        )
        d = json.loads(obj.model_dump_json())
        assert d["customer_context"] == {}


# ── EvidenceItem ─────────────────────────────────────────────────────────


class TestEvidenceItem:
    def test_minimal(self) -> None:
        obj = EvidenceItem(
            source="billing_records",
            tool_name="tool_billing",
            content="Charge of $49.99 on 2026-05-01",
        )
        d = json.loads(obj.model_dump_json())
        assert d["source"] == "billing_records"
        assert d["content"] == "Charge of $49.99 on 2026-05-01"
        assert d["metadata"] == {}  # default
        assert d["timestamp"] is None  # default

    def test_missing_source(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceItem(tool_name="tool_billing", content="test")

    def test_missing_tool_name(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceItem(source="test", content="test")

    def test_missing_content(self) -> None:
        with pytest.raises(ValidationError):
            EvidenceItem(source="test", tool_name="test")

    def test_full(self) -> None:
        obj = EvidenceItem(
            source="support_tickets",
            tool_name="tool_ticket",
            content="Ticket #5678 — status: open",
            metadata={"ticket_id": "5678", "priority": "high"},
            timestamp="2026-06-10T12:00:00Z",
        )
        d = json.loads(obj.model_dump_json())
        assert d["metadata"]["ticket_id"] == "5678"
        assert d["timestamp"] == "2026-06-10T12:00:00Z"


# ── EvidencePackage ──────────────────────────────────────────────────────


class TestEvidencePackage:
    def test_minimal(self) -> None:
        item = EvidenceItem(
            source="billing_records",
            tool_name="tool_billing",
            content="Charge of $49.99",
        )
        obj = EvidencePackage(items=[item])
        d = json.loads(obj.model_dump_json())
        assert len(d["items"]) == 1
        assert d["items"][0]["source"] == "billing_records"
        assert d["failed_tools"] == []  # default
        assert d["total_sources"] == 0  # default

    def test_with_failed_tools(self) -> None:
        item = EvidenceItem(
            source="support_tickets",
            tool_name="tool_ticket",
            content="Ticket #1234",
        )
        obj = EvidencePackage(
            items=[item],
            failed_tools=["tool_analytics"],
            total_sources=2,
        )
        d = json.loads(obj.model_dump_json())
        assert "tool_analytics" in d["failed_tools"]
        assert d["total_sources"] == 2

    def test_missing_items(self) -> None:
        with pytest.raises(ValidationError):
            EvidencePackage()

    def test_multiple_items(self) -> None:
        items = [
            EvidenceItem(source="a", tool_name="ta", content="c1"),
            EvidenceItem(source="b", tool_name="tb", content="c2"),
        ]
        obj = EvidencePackage(items=items, total_sources=2)
        d = json.loads(obj.model_dump_json())
        assert len(d["items"]) == 2


# ── ReasoningOutput ──────────────────────────────────────────────────────


class TestReasoningOutput:
    def test_minimal(self) -> None:
        obj = ReasoningOutput(
            conclusion="Customer is eligible for a one-time refund.",
            evidence_cited=["billing_records", "refund_policy"],
            reasoning_type="policy_application",
            confidence=0.88,
        )
        d = json.loads(obj.model_dump_json())
        assert "refund" in d["conclusion"]
        assert d["reasoning_type"] == "policy_application"
        assert d["warnings"] == []  # default

    def test_missing_conclusion(self) -> None:
        with pytest.raises(ValidationError):
            ReasoningOutput(
                evidence_cited=[],
                reasoning_type="policy_application",
                confidence=0.88,
            )

    def test_missing_evidence_cited(self) -> None:
        with pytest.raises(ValidationError):
            ReasoningOutput(
                conclusion="test",
                reasoning_type="policy_application",
                confidence=0.88,
            )

    def test_missing_reasoning_type(self) -> None:
        with pytest.raises(ValidationError):
            ReasoningOutput(conclusion="test", evidence_cited=[], confidence=0.88)

    def test_missing_confidence(self) -> None:
        with pytest.raises(ValidationError):
            ReasoningOutput(
                conclusion="test", evidence_cited=[], reasoning_type="policy_application"
            )

    def test_with_warnings(self) -> None:
        obj = ReasoningOutput(
            conclusion="Partial refund approved.",
            evidence_cited=["billing_records"],
            reasoning_type="policy_application",
            confidence=0.75,
            warnings=["Billing records missing 2 months of data"],
        )
        d = json.loads(obj.model_dump_json())
        assert len(d["warnings"]) == 1


# ── ChatRequest ──────────────────────────────────────────────────────────


class TestChatRequest:
    def test_minimal(self) -> None:
        obj = ChatRequest(
            message="Why was I charged twice?", customer_id="mock_001"
        )
        d = json.loads(obj.model_dump_json())
        assert d["message"] == "Why was I charged twice?"
        assert d["customer_id"] == "mock_001"

    def test_missing_message(self) -> None:
        with pytest.raises(ValidationError):
            ChatRequest(customer_id="mock_001")

    def test_missing_customer_id(self) -> None:
        with pytest.raises(ValidationError):
            ChatRequest(message="hello")

    def test_empty_message(self) -> None:
        obj = ChatRequest(message="", customer_id="mock_001")
        d = json.loads(obj.model_dump_json())
        assert d["message"] == ""


# ── ChatResponse ─────────────────────────────────────────────────────────


class TestChatResponse:
    def test_minimal(self) -> None:
        obj = ChatResponse(response="Here is your billing info.")
        d = json.loads(obj.model_dump_json())
        assert d["response"] == "Here is your billing info."
        assert d["evidence"] is None
        assert d["reasoning_trace"] is None
        assert d["tool_calls_made"] == []  # default

    def test_with_evidence_and_reasoning(self) -> None:
        evidence = EvidencePackage(
            items=[
                EvidenceItem(
                    source="billing", tool_name="tool_billing", content="$49.99"
                )
            ],
            total_sources=1,
        )
        reasoning = ReasoningOutput(
            conclusion="test",
            evidence_cited=["billing"],
            reasoning_type="policy_application",
            confidence=0.9,
        )
        obj = ChatResponse(
            response="Detailed response.",
            evidence=evidence,
            reasoning_trace=reasoning,
            tool_calls_made=["tool_billing"],
        )
        d = json.loads(obj.model_dump_json())
        assert d["evidence"]["total_sources"] == 1
        assert d["reasoning_trace"]["conclusion"] == "test"
        assert d["tool_calls_made"] == ["tool_billing"]

    def test_missing_response(self) -> None:
        with pytest.raises(ValidationError):
            ChatResponse()
