"""Pydantic models for intent analysis, tool selection, evidence, and reasoning.

These schemas define contract shapes for the Sprint 3 reasoning engine:
intent classification → tool selection → evidence gathering → cross-source
reasoning → response generation.
"""

from pydantic import BaseModel


class IntentAnalysisResult(BaseModel):
    """Result of customer intent analysis.

    Maps a natural-language query to a structured intent label,
    candidate tools for fulfilling the intent, and the sources
    those tools should query.
    """

    intent_label: str
    confidence: float
    candidate_tools: list[str]
    candidate_sources: list[str]
    notes: str | None = None


class ToolSelectionPlan(BaseModel):
    """Plan dictating which tools to invoke for the current turn.

    Carries customer context so downstream tools can personalise
    their queries without a separate customer-lookup step.
    """

    selected_tools: list[str]
    customer_context: dict
    max_tool_calls: int


class EvidenceItem(BaseModel):
    """A single piece of evidence returned by a tool.

    ``metadata`` is an open dictionary for tool-specific details
    (e.g. record IDs, timestamps, confidence scores).
    """

    source: str
    tool_name: str
    content: str
    metadata: dict = {}
    timestamp: str | None = None


class EvidencePackage(BaseModel):
    """Collection of evidence aggregated from one or more tool calls.

    Also tracks tools that failed so the reasoning engine can decide
    whether it has enough information to proceed.
    """

    items: list[EvidenceItem]
    failed_tools: list[str] = []
    total_sources: int = 0


class ReasoningOutput(BaseModel):
    """Output of the cross-source reasoning engine.

    Represents the final conclusion drawn from the evidence package,
    along with metadata about *how* that conclusion was reached.
    """

    conclusion: str
    evidence_cited: list[str]
    reasoning_type: str
    confidence: float
    warnings: list[str] = []


class ChatRequest(BaseModel):
    """Inbound chat-turn request from the voice/chat frontend."""

    message: str
    customer_id: str


class ChatResponse(BaseModel):
    """Outbound chat-turn response sent to the frontend.

    ``evidence`` and ``reasoning_trace`` are ``None`` when the turn
    does not involve retrieval (e.g. a greeting or follow-up).
    """

    response: str
    evidence: EvidencePackage | None = None
    reasoning_trace: ReasoningOutput | None = None
    tool_calls_made: list[str] = []
