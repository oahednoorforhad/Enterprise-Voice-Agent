"""Cross-source reasoning pipeline.

Takes an ``EvidencePackage`` produced by the evidence aggregator and
produces an evidence-backed ``ReasoningOutput``.  The pipeline has two
paths:

1. **Insufficient evidence** (deterministic, no LLM call) — when there
   are no evidence items and the intent is not a greeting or other.
2. **Evidence-backed reasoning** (LLM call) — uses
   ``LLMClient.generate_structured()`` to reason over the available
   evidence.

Usage
-----
.. code-block:: python

    pipeline = ReasoningPipeline(llm_client=some_llm_client)
    output = await pipeline.reason(
        evidence_package=evidence_pkg,
        customer_context={"name": "Alice"},
        intent="billing_inquiry",
    )
"""

from __future__ import annotations

from langfuse import observe
from pydantic import BaseModel

from app.core.llm_client import LLMClient
from app.schemas.reasoning import EvidencePackage, ReasoningOutput

# ── Internal LLM response model ───────────────────────────────────────────

_VALID_REASONING_TYPES = frozenset({
    "evidence_corroboration",
    "policy_application",
    "root_cause_analysis",
    "decision_support",
})


class _ReasoningLLMResponse(BaseModel):
    """Structured response expected from the LLM for evidence reasoning.

    This model is kept private to the module — callers interact with the
    public :class:`ReasoningOutput` schema instead.
    """

    conclusion: str
    evidence_cited: list[str]
    reasoning_type: str
    confidence: float
    warnings: list[str]


# ── System prompt ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are EVA, an executive-level enterprise assistant for a company's "
    "customer experience team. You speak with the authority, professionalism, "
    "and decisiveness of a company executive.\n"
    "\n"
    "Your task is to reason over the provided evidence package and produce "
    "a structured, evidence-backed conclusion — but the final response must "
    "sound like a senior executive addressing a valued customer.\n"
    "\n"
    "## VOICE & TONE\n"
    "\n"
    "- Use professional, polished language — no AI/LLM markers like "
    "\"based on the provided context\" or \"according to the evidence.\"\n"
    "- Speak directly and authoritatively. Lead with the answer, not with "
    "qualifiers.\n"
    "- Be concise. Executives don't ramble — give the customer the "
    "information they need, clearly and directly.\n"
    "- Use natural, human language — as if a senior company officer is "
    "sitting across the table.\n"
    "- When appropriate, acknowledge the customer's concern and take "
    "ownership: \"I've looked into this...\" (handled),\n"
    "\"Let me explain...\" (explaining a policy).\n"
    "\n"
    "## CRITICAL RULES\n"
    "\n"
    "1. You must ONLY use the evidence and prior conversation shown "
    "below. Do NOT use any external knowledge or training data to answer.\n"
    "2. Base conclusions ONLY on the evidence and prior conversation "
    "below — never invent facts or hallucinate.\n"
    "3. If the evidence does not contain enough information to fully answer "
    "the question, say so directly and include a warning.\n"
    "4. If evidence items are contradictory, surface the contradiction in "
    "the warnings field.\n"
    "5. If asked about something not covered in the evidence, include a "
    "warning like 'The available evidence does not directly address this "
    "question'.\n"
    "6. If the user asks you to summarise the conversation or refer back "
    "to a previous topic, prioritise the prior conversation context "
    "over tool evidence.\n"
    "\n"
    "## Reasoning Types\n"
    "\n"
    "Classify your reasoning into one of these four types:\n"
    "\n"
    "- evidence_corroboration: Multiple sources support the same conclusion.\n"
    "- policy_application: Apply company policies to customer situations.\n"
    "- root_cause_analysis: Identify likely causes of customer issues.\n"
    "- decision_support: Determine likely customer eligibility.\n"
    "\n"
    "## Confidence Calibration\n"
    "\n"
    "Set confidence (0.0 to 1.0) proportional to evidence quality and "
    "coverage:\n"
    "- 1.0: Multiple high-quality sources all agree on the conclusion.\n"
    "- 0.7-0.9: Good evidence supports the conclusion with minor gaps.\n"
    "- 0.4-0.6: Partial evidence, some gaps or indirect support.\n"
    "- 0.1-0.3: Weak or very limited evidence.\n"
    "- 0.0: No evidence (should not happen in this path).\n"
    "\n"
    "## Evidence Citation\n"
    "\n"
    "In the evidence_cited field, list the source names (e.g., "
    "[\"billing_records\", \"support_tickets\"]) that directly support "
    "your conclusion. Only include sources whose evidence you actually used.\n"
    "\n"
    "Respond with the conclusion, evidence_cited, reasoning_type, "
    "confidence, and any warnings."
)


# ── Public API ────────────────────────────────────────────────────────────


class ReasoningPipeline:
    """Reason over an evidence package to produce evidence-backed conclusions.

    Parameters
    ----------
    llm_client:
        An :class:`LLMClient` instance used for evidence-backed reasoning.
        This is intentionally injectable so it can be mocked in tests.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    @observe()
    async def reason(
        self,
        evidence_package: EvidencePackage,
        customer_context: dict | None = None,
        intent: str | None = None,
        *,
        user_message: str | None = None,
        conversation_history: str | None = None,
    ) -> ReasoningOutput:
        """Reason over the evidence package and return a conclusion.

        Parameters
        ----------
        evidence_package:
            The aggregated evidence from one or more tool calls.
        customer_context:
            Optional dictionary with customer info (e.g. ``customer_id``,
            ``name``, ``email``) that can help personalise the response.
        intent:
            The customer's intent label (e.g. ``"billing_inquiry"``,
            ``"greeting"``).  Used to select the reasoning path.

        Returns
        -------
        ReasoningOutput
            The evidence-backed conclusion with reasoning metadata.

        Raises
        ------
        LLMClientError
            If the underlying LLM call fails (network, auth, rate-limit, …).
        """
        # ── Path 1: Insufficient evidence (deterministic, no LLM call) ────
        if not evidence_package.items:
            if conversation_history:
                prompt = self._build_prompt(
                    evidence_package=evidence_package,
                    customer_context=customer_context,
                    intent=intent,
                    user_message=user_message,
                    conversation_history=conversation_history,
                )
            else:
                return self._handle_insufficient_evidence(
                    customer_context=customer_context,
                    intent=intent,
                )
        else:
            # ── Path 2: Evidence-backed reasoning (LLM call) ──────────────
            prompt = self._build_prompt(
                evidence_package=evidence_package,
                customer_context=customer_context,
                intent=intent,
                user_message=user_message,
                conversation_history=conversation_history,
            )

        raw: _ReasoningLLMResponse = await self._llm.generate_structured(
            prompt=prompt,
            response_schema=_ReasoningLLMResponse,
            system_instruction=_SYSTEM_PROMPT,
        )

        # Validate reasoning_type
        if raw.reasoning_type not in _VALID_REASONING_TYPES:
            raw.reasoning_type = "evidence_corroboration"

        # Clamp confidence to [0.0, 1.0]
        confidence = max(0.0, min(1.0, raw.confidence))

        return ReasoningOutput(
            conclusion=raw.conclusion,
            evidence_cited=raw.evidence_cited,
            reasoning_type=raw.reasoning_type,
            confidence=confidence,
            warnings=raw.warnings,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _handle_insufficient_evidence(
        customer_context: dict | None,
        intent: str | None,
    ) -> ReasoningOutput:
        """Deterministic fallback when there is no evidence to reason over.

        This path NEVER calls the LLM — it is a hallucination prevention
        measure.
        """
        is_greeting_or_other = intent in ("greeting", "other")

        if is_greeting_or_other:
            name = ""
            if customer_context and "name" in customer_context:
                name = customer_context["name"]

            if name:
                conclusion = (
                    f"Good day, {name}. This is EVA from the executive "
                    f"support desk. I'm here to assist you personally with "
                    f"any billing, ticket, account, or policy concerns you "
                    f"may have. How can I help?"
                )
            else:
                conclusion = (
                    "Good day. This is EVA from the executive support desk. "
                    "I'm here to assist you personally with any billing, "
                    "ticket, account, or policy concerns you may have. "
                    "How can I help?"
                )

            return ReasoningOutput(
                conclusion=conclusion,
                evidence_cited=[],
                reasoning_type="greeting",
                confidence=1.0,
                warnings=[],
            )

        return ReasoningOutput(
            conclusion=(
                "I do not have enough information to answer your question. "
                "Please provide more details or contact support for assistance."
            ),
            evidence_cited=[],
            reasoning_type="insufficient_evidence",
            confidence=0.0,
            warnings=["No evidence was retrieved to support this turn"],
        )

    @staticmethod
    def _build_prompt(
        evidence_package: EvidencePackage,
        customer_context: dict | None,
        intent: str | None,
        *,
        user_message: str | None = None,
        conversation_history: str | None = None,
    ) -> str:
        """Build the prompt for the LLM including all evidence items."""
        parts: list[str] = []

        # Inject prior conversation as the first evidence item so the
        # "ONLY use the evidence below" system rule covers it.
        if conversation_history:
            parts.append("--- Evidence items ---")
            parts.append(
                "[Prior conversation]\n"
                "  Source: conversation_memory\n"
                "  Tool: memory\n"
                f"  Content:\n{conversation_history}"
            )

        if user_message:
            parts.append(f"Customer message: {user_message}\n")

        if intent:
            parts.append(f"Customer intent: {intent}\n")

        if customer_context:
            parts.append(f"Customer context: {customer_context}\n")

        if evidence_package.items:
            if not conversation_history:
                parts.append("--- Evidence items ---")
            for i, item in enumerate(evidence_package.items, start=1):
                parts.append(
                    f"[Item {i}]\n"
                    f"  Source: {item.source}\n"
                    f"  Tool: {item.tool_name}\n"
                    f"  Content: {item.content}"
                )

        if evidence_package.failed_tools:
            parts.append("--- Failed tools ---")
            for tool in evidence_package.failed_tools:
                parts.append(f"  - {tool} (data could not be retrieved)")

        parts.append(
            "\nBased on the evidence above, provide a conclusion, "
            "list the sources you cited, classify the reasoning type, "
            "set a confidence score, and list any warnings."
        )

        return "\n\n".join(parts)
