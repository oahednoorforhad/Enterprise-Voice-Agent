"""Intent analysis module.

Classifies customer messages into structured intents using an LLM,
producing candidate tools and sources for downstream orchestration.

Usage
-----
.. code-block:: python

    analyzer = IntentAnalyzer(llm_client=some_llm_client)
    result = await analyzer.analyze("Why was I charged twice?")
    # result.intent_label == "billing_inquiry"
"""

from __future__ import annotations

from langfuse import observe
from pydantic import BaseModel

from app.core.llm_client import LLMClient
from app.schemas.reasoning import IntentAnalysisResult

# ── Internal LLM response model ───────────────────────────────────────────


class _IntentLLMResponse(BaseModel):
    """Structured response expected from the LLM for intent classification.

    This model is kept private to the module — callers interact with the
    public :class:`IntentAnalysisResult` schema instead.
    """

    intent_label: str
    confidence: float
    candidate_tools: list[str]
    candidate_sources: list[str]
    notes: str | None = None


# ── System prompt ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = (
    "You are an intent analyzer for a customer support system. "
    "Classify the customer's message into one of the following intent categories:\n"
    "\n"
    "1. billing_inquiry: Questions about charges, invoices, payments, refunds, "
    "billing discrepancies.\n"
    "   - Tools: get_billing_history, get_support_tickets, get_ticket_status, "
    "search_policies\n"
    "   - Sources: billing_records, support_tickets, policies\n"
    "\n"
"2. support_ticket: Questions about existing tickets, creating new tickets, "
"ticket status, resolving issues, reporting issues, bugs, problems, or "
"feature requests.\n"
"   - Tools: get_support_tickets, get_ticket_status, create_support_ticket, "
"search_documentation\n"
    "   - Sources: support_tickets, documentation\n"
    "\n"
    "3. knowledge_query: Questions about how to use a feature, product "
    "documentation, policies.\n"
    "   - Tools: search_documentation, search_policies\n"
    "   - Sources: documentation, policies\n"
    "\n"
    "4. account_query: Questions about profile, subscription, account status.\n"
    "   - Tools: get_customer_profile, get_subscription_status\n"
    "   - Sources: customer_profile, subscription\n"
    "\n"
    "5. analytics_query: Questions about usage metrics, analytics data.\n"
    "   - Tools: get_usage_analytics\n"
    "   - Sources: usage_analytics\n"
    "\n"
    "6. greeting: Hello, hi, how are you, good morning, etc. Also handles "
    "Bangla greetings like \u09a8\u09ae\u09b8\u09cd\u0995\u09be\u09b0, "
    "\u09b9\u09cd\u09af\u09be\u09b2\u09cb, \u0995\u09c7\u09ae\u09a8 "
    "\u0986\u099b\u09c7\u09a8.\n"
    "   - No tools needed. Set empty candidate_tools and candidate_sources.\n"
    "   - Set confidence >= 0.9.\n"
    "\n"
    "7. other: Anything not matching the above categories.\n"
    "   - No tools needed. Set empty candidate_tools and candidate_sources.\n"
    "\n"
    "8. conversation_history_query: The customer implies shared context from a "
    "prior session that has not been established in the current conversation. "
    "Use your reasoning — do not match keywords. Ask yourself: would EVA need "
    "to know what happened in a previous session to answer this correctly? "
    "If yes, classify as conversation_history_query.\n"
    "   Trigger when: the customer refers to an issue, ticket, call, or "
    "interaction that is clearly from before this session — something EVA "
    "could not know from the current conversation alone.\n"
    "   Do NOT trigger for: fresh questions with no implied prior context, "
    "references to something said earlier in the current session, or greetings.\n"
    "   Examples that SHOULD trigger: 'Any update on that problem?', "
    "'Is my issue resolved yet?', 'We talked about this before', "
    "'You were going to look into that for me', 'That bug is still there'.\n"
    "   Examples that should NOT trigger: 'What is my current plan?', "
    "'How do I reset my password?', 'Can you explain that again?' (in-session).\n"
"   - Tools: get_session_history\n"
"   - Sources: conversation_history\n"
"\n"
"TICKET CREATION GUARDRAILS:\n"
"Use the create_support_ticket tool ONLY when:\n"
"- The issue is specific and actionable (not vague)\n"
"- The user is not being abusive or spamming\n"
"- The issue is not already answered by existing documentation\n"
"- The issue relates to the product or service\n"
"- For ambiguous cases, suggest self-service options instead of creating a "
"ticket\n"
"\n"
"When you determine a ticket should be created, first present a structured\n"
"preview to the user with the extracted title, category, priority, and\n"
"description. Ask for explicit confirmation before proceeding with creation.\n"
"\n"
"Handle Bangla (Bengali), English, and code-switched (mixed) input "
    "naturally. Bangla billing questions like "
    '"আমাকে কেন দ্বিগুণ চার্জ করা হয়েছে?" must classify as billing_inquiry.\n'
    "\n"
    "Respond with the intent_label, confidence (0.0 to 1.0), candidate_tools "
    "(list of tool name strings), candidate_sources (list of source name "
    "strings), and a brief note explaining your reasoning."
)


# ── Public API ────────────────────────────────────────────────────────────


class IntentAnalyzer:
    """Classifies customer messages into structured intents.

    Uses an LLM to determine the customer's intent and identify
    candidate tools and information sources for fulfilling that intent.

    Parameters
    ----------
    llm_client:
        An :class:`LLMClient` instance used to query the underlying LLM.
        This is intentionally injectable so it can be mocked in tests.
    """

    def __init__(self, llm_client: LLMClient) -> None:
        self._llm = llm_client

    @observe()
    async def analyze(
        self,
        message: str,
        customer_context: dict | None = None,
    ) -> IntentAnalysisResult:
        """Analyze a customer message and return structured intent data.

        Parameters
        ----------
        message:
            The customer's natural-language message. Supports English,
            Bangla (Bengali), and code-switched (mixed) input.
        customer_context:
            Optional dictionary with customer info (e.g. ``customer_id``,
            ``name``, ``email``) that can help contextualise the intent
            classification.

        Returns
        -------
        IntentAnalysisResult
            Structured intent classification with candidate tools and
            sources that downstream orchestrators can act on.

        Raises
        ------
        LLMClientError
            If the underlying LLM call fails (network, auth, rate-limit, …).
        """
        prompt = f"Customer message: {message}"
        if customer_context:
            prompt += f"\n\nCustomer context: {customer_context}"

        raw: _IntentLLMResponse = await self._llm.generate_structured(
            prompt=prompt,
            response_schema=_IntentLLMResponse,
            system_instruction=_SYSTEM_PROMPT,
        )

        return IntentAnalysisResult(
            intent_label=raw.intent_label,
            confidence=raw.confidence,
            candidate_tools=raw.candidate_tools,
            candidate_sources=raw.candidate_sources,
            notes=raw.notes,
        )
