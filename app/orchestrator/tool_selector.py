"""Tool selection module — deterministic policy for choosing minimal tool sets.

The ``ToolSelector`` receives an :class:`IntentAnalysisResult` from the
intent analyzer and applies a deterministic, rule-based policy to produce
a :class:`ToolSelectionPlan` with the smallest useful tool set for the
current turn.  No LLM calls are made at this stage — the selector is a
pure policy function.
"""

from __future__ import annotations

from app.config.settings import get_settings
from app.schemas.reasoning import IntentAnalysisResult, ToolSelectionPlan

# ── Known tool names (must match app/api/tools_router.py tool families) ──

KNOWN_TOOLS: frozenset[str] = frozenset({
    "get_customer_profile",
    "get_subscription_status",
    "get_billing_history",
    "get_support_tickets",
    "get_ticket_status",
    "search_documentation",
    "search_policies",
    "get_usage_analytics",
})

# ── Intent-specific ordering rules ────────────────────────────────────────

_INTENT_TOOL_ORDER: dict[str, list[str]] = {
    "billing_inquiry": [
        "get_billing_history",
        "get_support_tickets",
        "get_ticket_status",
        "search_policies",
        "search_documentation",
    ],
    "support_ticket": [
        "get_support_tickets",
        "get_ticket_status",
        "search_documentation",
        "search_policies",
    ],
    "knowledge_query": [
        "search_documentation",
        "search_policies",
    ],
    "account_query": [
        "get_customer_profile",
        "get_subscription_status",
    ],
    "analytics_query": [
        "get_usage_analytics",
    ],
}

# Per-intent tool caps (stricter than the global max_tool_calls_per_turn).
_INTENT_MAX_TOOLS: dict[str, int] = {
    "billing_inquiry": 4,
    "support_ticket": 3,
    "knowledge_query": 2,
    "account_query": 2,
    "analytics_query": 1,
}

_LOW_CONFIDENCE_THRESHOLD: float = 0.3


class ToolSelector:
    """Deterministic policy for choosing the minimal tool set per turn.

    The selector does **not** invoke an LLM.  It applies ordering,
    deduplication, validation, and capping rules to the candidate tools
    proposed by the intent analyzer.

    Parameters
    ----------
    max_calls:
        Maximum number of tools to select per turn.  When ``None``
        the value is pulled from ``settings.max_tool_calls_per_turn``
        (defaults to 6).
    """

    def __init__(self, max_calls: int | None = None) -> None:
        if max_calls is not None:
            self._max_calls = max_calls
        else:
            self._max_calls = get_settings().max_tool_calls_per_turn

    async def select(
        self,
        intent: IntentAnalysisResult,
        customer_context: dict | None = None,
    ) -> ToolSelectionPlan:
        """Produce a ``ToolSelectionPlan`` with the minimal useful tool set.

        Parameters
        ----------
        intent:
            The structured intent result from ``IntentAnalyzer.analyze()``.
        customer_context:
            Optional customer information dictionary.  Defaults to ``{}``
            when ``None`` is passed.

        Returns
        -------
        ToolSelectionPlan
            A plan with the ``selected_tools``, a copy of the customer
            context, and the effective ``max_tool_calls`` for this turn.
        """
        # Normalise missing customer context to empty dict.
        ctx: dict = customer_context if customer_context is not None else {}

        # ── Greeting and other intents always return an empty list ──────
        if intent.intent_label in ("greeting", "other"):
            return ToolSelectionPlan(
                selected_tools=[],
                customer_context=ctx,
                max_tool_calls=self._max_calls,
            )

        # ── Empty candidate list shortcut ───────────────────────────────
        if not intent.candidate_tools:
            return ToolSelectionPlan(
                selected_tools=[],
                customer_context=ctx,
                max_tool_calls=self._max_calls,
            )

        # ── Order, validate, deduplicate, and cap ───────────────────────
        ordered = self._apply_ordering(intent.candidate_tools, intent.intent_label)
        deduped = list(dict.fromkeys(ordered))  # preserve order, remove dupes

        # Determine the effective cap.
        cap = self._max_calls

        intent_max = _INTENT_MAX_TOOLS.get(intent.intent_label)
        if intent_max is not None:
            cap = min(cap, intent_max)

        if intent.confidence < _LOW_CONFIDENCE_THRESHOLD:
            cap = min(cap, 1)

        selected = deduped[:cap]

        return ToolSelectionPlan(
            selected_tools=selected,
            customer_context=ctx,
            max_tool_calls=self._max_calls,
        )

    # ── Private helpers ──────────────────────────────────────────────────

    @staticmethod
    def _apply_ordering(tools: list[str], intent_label: str) -> list[str]:
        """Filter *tools* to the intent's priority list and sort by priority.

        Tools that do not appear in the intent's ordered list or are not
        in the global ``KNOWN_TOOLS`` set are silently dropped.
        """
        priority = _INTENT_TOOL_ORDER.get(intent_label, [])
        position = {name: idx for idx, name in enumerate(priority)}
        # Keep only tools that are in the priority list AND globally known.
        valid = [t for t in tools if t in position and t in KNOWN_TOOLS]
        valid.sort(key=lambda t: position[t])
        return valid
