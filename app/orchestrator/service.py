"""Turn orchestrator — composes intent analysis, tool selection, execution,
evidence aggregation, and reasoning into a single-turn loop with bounded
adaptive replanning.

The orchestrator uses a **Static DAG** with one deterministic replan fallback
(instead of an unbounded reasoning loop).  If the first pass of tool execution
produces insufficient evidence, exactly one replan pass is triggered to
re-run missing or alternative tools before final reasoning.

Usage
-----
.. code-block:: python

    from app.db.session import get_session_factory

    factory = get_session_factory()
    svc = OrchestratorService(
        llm_client=llm,
        session_factory=factory,
        customer_id="abc-123",
        customer_context={"name": "Alice"},
    )
    response = await svc.process_turn("Why was I charged twice?")
    # response.response        → str
    # response.evidence        → EvidencePackage | None
    # response.reasoning_trace → ReasoningOutput
    # response.tool_calls_made → list[str]
"""

from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncGenerator, Callable, Coroutine
from dataclasses import dataclass
from typing import Any, TypedDict
from uuid import UUID

from langfuse import observe
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import DomainException
from app.core.llm_client import LLMClient
from app.orchestrator.evidence_aggregator import EvidenceAggregator
from app.orchestrator.intent_analyzer import IntentAnalyzer
from app.orchestrator.tool_selector import ToolSelector
from app.reasoning.pipeline import ReasoningPipeline
from app.schemas.reasoning import ChatResponse, EvidencePackage, ToolSelectionPlan
from app.schemas.tools import ToolResult
from app.tools.analytics.functions import get_usage_analytics
from app.tools.billing.functions import get_billing_history
from app.tools.customer.functions import get_customer_profile, get_subscription_status
from app.tools.history.functions import get_session_history
from app.tools.knowledge.functions import search_documentation, search_policies
from app.tools.ticket.functions import (
    create_support_ticket,
    get_support_tickets,
    get_ticket_status,
)
from app.tools.ticket.models import TicketModel, TicketPreview

# ── Constants ──────────────────────────────────────────────────────────────

_TOOL_TIMEOUT_SECONDS = 15.0  # Increased from 3.0 — create_support_ticket calls LLM internally

# ── Typed tool registry ────────────────────────────────────────────────────
# Each entry carries the async callable AND a kwargs builder so the fragile
# if/elif chain in ``_build_tool_kwargs`` is eliminated.


@dataclass
class _ToolEntry:
    """Registry entry binding a tool function to its kwargs builder.

    Attributes
    ----------
    func:
        The async callable that implements the tool.
    kwargs_builder:
        A callable ``(session, customer_id_str, message) → dict`` that
        produces the keyword arguments expected by *func*.
    """

    func: Callable[..., Coroutine[Any, Any, Any]]
    kwargs_builder: Callable[..., dict[str, Any]]


# ── Kwargs builders ────────────────────────────────────────────────────────


def _build_standard_kwargs(
    session: AsyncSession,
    customer_id_str: str,
    message: str,  # noqa: ARG001
) -> dict[str, Any]:
    """Build kwargs for tools that need ``(session, customer_id)``."""
    return {"session": session, "customer_id": uuid.UUID(customer_id_str)}


def _build_knowledge_kwargs(
    session: AsyncSession,
    customer_id_str: str,  # noqa: ARG001
    message: str,
) -> dict[str, Any]:
    """Build kwargs for knowledge-search tools needing ``(session, query)``."""
    return {"session": session, "query": message}


def _build_ticket_status_kwargs(
    session: AsyncSession,
    customer_id_str: str,
    message: str,  # noqa: ARG001
) -> dict[str, Any]:
    """Build kwargs for ``get_ticket_status``.

    ``ticket_id`` is not available from customer_context alone — ``None``
    is passed so the function raises a ``DomainException`` that the caller
    converts to ``ToolResult.fail()``.
    """
    return {
        "session": session,
        "customer_id": uuid.UUID(customer_id_str),
        "ticket_id": None,
    }


def _build_create_ticket_kwargs(
    session: AsyncSession,
    customer_id_str: str,
    message: str,
) -> dict[str, Any]:
    """Build kwargs for create_support_ticket.

    Passes the raw user message so the function can parse it with LLM.
    Fields like title/category/priority are set to empty by default —
    the LLM inside the function extracts them from the message.
    """
    return {
        "session": session,
        "customer_id": uuid.UUID(customer_id_str),
        "message": message,
    }


# ── Auto-create support ticket wrapper ──────────────────────────────────────
# Validates via LLM (confirmed=False), then persists if guardrails pass.


async def _auto_create_support_ticket(
    session: AsyncSession,
    customer_id: UUID,
    message: str = "",
) -> TicketModel | TicketPreview:
    """Validate via LLM, then persist ticket if guardrails pass.

    Two-step process:

    1. Call ``create_support_ticket(confirmed=False)`` for LLM validation
       (returns ``TicketPreview``, no DB write).
    2. If the preview is ``valid`` and has a non-empty ``title``, call
       ``create_support_ticket(confirmed=True)`` with the extracted fields
       to persist the ticket (returns ``TicketModel``).

    Returns
    -------
    TicketModel
        On successful creation (DB persisted).
    TicketPreview
        When validation fails, title is empty, or rate-limited.
    """
    # Step 1: LLM validation (confirmed=False, no DB write)
    preview = await create_support_ticket(
        session, customer_id, message=message, confirmed=False,
    )

    # Step 2: If valid and has a title, persist the ticket
    if isinstance(preview, TicketPreview) and preview.valid and preview.title:
        ticket = await create_support_ticket(
            session,
            customer_id,
            title=preview.title,
            description=preview.description,
            category=preview.category,
            priority=preview.priority,
            confirmed=True,
        )
        return ticket

    # Return preview as-is (validation failed or no title extracted)
    return preview


DEFAULT_TOOL_REGISTRY: dict[str, _ToolEntry] = {
    "get_customer_profile": _ToolEntry(
        func=get_customer_profile,
        kwargs_builder=_build_standard_kwargs,
    ),
    "get_subscription_status": _ToolEntry(
        func=get_subscription_status,
        kwargs_builder=_build_standard_kwargs,
    ),
    "get_billing_history": _ToolEntry(
        func=get_billing_history,
        kwargs_builder=_build_standard_kwargs,
    ),
    "get_support_tickets": _ToolEntry(
        func=get_support_tickets,
        kwargs_builder=_build_standard_kwargs,
    ),
    "get_ticket_status": _ToolEntry(
        func=get_ticket_status,
        kwargs_builder=_build_ticket_status_kwargs,
    ),
    "search_documentation": _ToolEntry(
        func=search_documentation,
        kwargs_builder=_build_knowledge_kwargs,
    ),
    "search_policies": _ToolEntry(
        func=search_policies,
        kwargs_builder=_build_knowledge_kwargs,
    ),
    "get_usage_analytics": _ToolEntry(
        func=get_usage_analytics,
        kwargs_builder=_build_standard_kwargs,
    ),
    "get_session_history": _ToolEntry(
        func=get_session_history,
        kwargs_builder=_build_standard_kwargs,
    ),
    "create_support_ticket": _ToolEntry(
        func=_auto_create_support_ticket,
        kwargs_builder=_build_create_ticket_kwargs,
    ),
}


# ── Fallback tool mappings for replan ──────────────────────────────────────
# When a tool fails in the first pass these alternatives are tried in the
# single allowed replan pass.

_FALLBACK_TOOLS: dict[str, list[str]] = {
    "get_billing_history": ["get_support_tickets", "search_policies"],
    "get_customer_profile": ["get_subscription_status"],
    "get_support_tickets": ["search_documentation"],
    "get_ticket_status": ["get_support_tickets"],
}


# ── Evidence sufficiency checker ───────────────────────────────────────────


class EvidenceSufficiencyChecker:
    """Deterministic checker that decides whether enough evidence exists.

    This is a pure function — no LLM calls, no external state.  It checks
    simple heuristics and returns a boolean decision.
    """

    # Intent-to-required-sources mapping.  When the intent is known, the
    # evidence package MUST contain at least one item from each required
    # source name listed here.
    REQUIRED_SOURCES: dict[str, set[str]] = {
        "billing_inquiry": {"billing_records"},
        "account_query": {"customer_profile", "subscription"},
        "support_ticket": {"support_tickets"},
        "knowledge_query": {"policies", "documentation"},
        "analytics_query": {"usage_analytics"},
        "conversation_history_query": {"conversation_history"},
    }

    @staticmethod
    def is_sufficient(evidence: EvidencePackage, intent: str) -> bool:
        """Return ``True`` when the evidence is sufficient for reasoning.

        Rules
        -----
        - Greeting and ``other`` intents never need evidence.
        - If the intent has required sources defined in ``REQUIRED_SOURCES``,
          all of them must be present in ``evidence.items`` (by ``.source``).
        - Fallback (unknown intent): sufficient when at least one evidence
          item exists.
        """
        if intent in ("greeting", "other"):
            return True
        if not evidence.items:
            return False

        # Intent-aware check: required sources must all be present.
        required = EvidenceSufficiencyChecker.REQUIRED_SOURCES.get(intent)
        if required:
            present_sources = {item.source for item in evidence.items}
            return required.issubset(present_sources)

        # Unknown intent: at least one item is sufficient.
        return True

    @staticmethod
    def compute_replan_tools(
        plan: ToolSelectionPlan,
        attempted: set[str],
        failed: list[str],
    ) -> list[str]:
        """Compute which tools to run in the single replan pass.

        Strategy (in order):
        1. Run any tools from the original plan that were **not** attempted
           (e.g. because ``max_tool_calls`` limited the first batch).
        2. If all planned tools were attempted and some failed, try the
           deterministic fallback alternatives defined in ``_FALLBACK_TOOLS``.
        3. Return an empty list when there is nothing useful to run.
        """
        # 1. Remaining tools from the plan.
        remaining = [t for t in plan.selected_tools if t not in attempted]
        if remaining:
            return remaining[: plan.max_tool_calls]

        # 2. Fallback alternatives for failed tools.
        if failed:
            fallbacks: list[str] = []
            for tool_name in failed:
                for alt in _FALLBACK_TOOLS.get(tool_name, []):
                    if alt not in attempted:
                        fallbacks.append(alt)
            return fallbacks[: plan.max_tool_calls]

        return []


# ── Public orchestrator service ────────────────────────────────────────────


class OrchestratorService:
    """Single-turn orchestrator with bounded adaptive replanning.

    The orchestrator owns the per-turn lifecycle:

    1. **Intent analysis** — classify the customer message via LLM.
    2. **Tool selection** — deterministic policy for choosing tool set.
    3. **Tool execution** — call each selected tool **in parallel** via
       ``asyncio.gather``.  Each tool call opens a **fresh DB session**
       from *session_factory* to prevent concurrent transaction errors.
    4. **Sufficiency check** — deterministic ``EvidenceSufficiencyChecker``
       decides whether to proceed or replan.
    5. **Replan** (at most **one** pass) — if evidence is insufficient,
       re-run missing or alternative tools.
    6. **Evidence aggregation** — normalise tool outputs into evidence items.
    7. **Reasoning** — evidence-backed conclusion via LLM (or deterministic
       fallback for greetings and insufficient evidence).

    Parameters
    ----------
    llm_client:
        An :class:`LLMClient` instance used by the intent analyzer and
        reasoning pipeline.  Injectable for testability.
    session_factory:
        An ``async_sessionmaker[AsyncSession]`` that produces a new
        :class:`AsyncSession` for **each** tool call.  Using a factory
        (not a shared session) prevents ``concurrent transaction`` errors
        when multiple tools run in parallel via ``asyncio.gather``.
    customer_id:
        The customer's unique identifier as a string.  Converted to
        ``uuid.UUID`` internally when calling tool functions.
    customer_context:
        Optional dictionary with customer metadata (name, email, etc.)
        forwarded to the analyzer, selector, and pipeline.
    max_tool_calls:
        Maximum number of tools to select per turn.  When ``None`` the
        value is pulled from ``settings.max_tool_calls_per_turn``.
    tool_registry:
        Overridable tool registry.  Defaults to ``DEFAULT_TOOL_REGISTRY``.
        Intended for dependency injection in tests.
    analyzer:
        Injected intent analyzer.  Created from *llm_client* when omitted.
    selector:
        Injected tool selector.  Created with *max_tool_calls* when omitted.
    aggregator:
        Injected evidence aggregator.  A fresh instance when omitted.
    pipeline:
        Injected reasoning pipeline.  Created from *llm_client* when omitted.
    """

    def __init__(
        self,
        llm_client: LLMClient,
        session_factory: async_sessionmaker[AsyncSession],
        customer_id: str,
        customer_context: dict | None = None,
        max_tool_calls: int | None = None,
        *,
        tool_registry: dict[str, _ToolEntry] | None = None,
        analyzer: IntentAnalyzer | None = None,
        selector: ToolSelector | None = None,
        aggregator: EvidenceAggregator | None = None,
        pipeline: ReasoningPipeline | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._customer_id = customer_id
        self._context = customer_context or {}
        self._tool_registry = (
            tool_registry if tool_registry is not None else DEFAULT_TOOL_REGISTRY
        )

        self._analyzer = analyzer or IntentAnalyzer(llm_client=llm_client)
        self._selector = selector or ToolSelector(max_calls=max_tool_calls)
        self._aggregator = aggregator or EvidenceAggregator()
        self._pipeline = pipeline or ReasoningPipeline(llm_client=llm_client)
        self._sufficiency_checker = EvidenceSufficiencyChecker()

    @observe()
    async def process_turn(
        self,
        message: str,
        conversation_history: str | None = None,
    ) -> ChatResponse:
        """Run the full turn loop and return a ``ChatResponse``.

        This is a **Static DAG with one adaptive fallback loop**:

        Intent -> Select -> Execute (parallel) -> Check -> (Replan 0..1)
        -> Aggregate -> Reason.

        Parameters
        ----------
        message:
            The customer's natural-language message (English, Bangla, or
            code-switched).
        conversation_history:
            Optional prior conversation context forwarded to the reasoning
            pipeline.

        Returns
        -------
        ChatResponse
            The turn result with a response string, optional evidence,
            reasoning trace, and list of tools that were called.

        Raises
        ------
        LLMClientError
            If the underlying LLM call fails in the intent analysis or
            evidence-backed reasoning step.
        """
        # ── 1. Intent Analysis ───────────────────────────────────────────
        intent_result = await self._analyzer.analyze(message, self._context)

        # ── 2. Tool Selection ────────────────────────────────────────────
        plan = await self._selector.select(intent_result, self._context)

        # ── 3. Tool Execution (parallel) ─────────────────────────────────
        tool_results: dict[str, ToolResult] = {}
        tool_calls_made: list[str] = []
        attempted: set[str] = set()

        is_greeting_or_other = intent_result.intent_label in ("greeting", "other")

        if not is_greeting_or_other and plan.selected_tools:
            tools_to_run = plan.selected_tools[: plan.max_tool_calls]

            # Round 1 — execute all planned tools in parallel.
            round1 = await self._execute_tools(tools_to_run, message)
            tool_results.update(round1)
            tool_calls_made.extend(round1.keys())
            attempted.update(round1.keys())

            # ── 4. Evidence Aggregation (interim) ────────────────────────
            evidence_package = await self._aggregator.aggregate(tool_results)

            # ── 5. Sufficiency Check & Replan (at most one pass) ─────────
            if not self._sufficiency_checker.is_sufficient(
                evidence_package, intent_result.intent_label
            ):
                replan_tools = self._sufficiency_checker.compute_replan_tools(
                    plan=plan,
                    attempted=attempted,
                    failed=evidence_package.failed_tools,
                )
                if replan_tools:
                    round2 = await self._execute_tools(replan_tools, message)
                    # Merge round-2 results (preserve existing, add new).
                    for tname, tresult in round2.items():
                        if tname not in tool_results:
                            tool_results[tname] = tresult
                    tool_calls_made.extend(
                        t for t in replan_tools if t not in attempted
                    )
                    attempted.update(t for t in replan_tools)

                    # Re-aggregate with merged results.
                    evidence_package = await self._aggregator.aggregate(
                        tool_results
                    )
        else:
            evidence_package = EvidencePackage(items=[])

        # ── 6. Final Reasoning ───────────────────────────────────────────
        reasoning_output = await self._pipeline.reason(
            evidence_package=evidence_package,
            customer_context=self._context,
            intent=intent_result.intent_label,
            user_message=message,
            conversation_history=conversation_history,
        )

        # ── 7. Compose ChatResponse ──────────────────────────────────────
        return ChatResponse(
            response=reasoning_output.conclusion,
            evidence=evidence_package if tool_results else None,
            reasoning_trace=reasoning_output,
            tool_calls_made=tool_calls_made,
        )

    # ── Parallel tool execution helper ──────────────────────────────────────

    async def _execute_tools(
        self,
        tool_names: list[str],
        message: str,
    ) -> dict[str, ToolResult]:
        """Execute the named tools **in parallel** via ``asyncio.gather``.

        Each tool call opens a **fresh async database session** from
        ``self._session_factory`` to prevent concurrent transaction errors
        when multiple tools run simultaneously.

        Each tool execution is subject to ``_TOOL_TIMEOUT_SECONDS`` timeout —
        if a tool exceeds the limit a ``ToolResult.fail("Tool timed out")``
        is returned instead of hanging the entire turn.

        Parameters
        ----------
        tool_names:
            Canonical tool function names to execute.
        message:
            The customer's original message (used as ``query`` for
            knowledge-search tools).

        Returns
        -------
        dict[str, ToolResult]
            Mapping of tool name → ``ToolResult``.  Every tool in
            *tool_names* has an entry — errors never propagate beyond
            a ``ToolResult.fail()`` wrapper.
        """

        async def _run_single(tool_name: str) -> tuple[str, ToolResult]:
            entry = self._tool_registry.get(tool_name)
            if entry is None:
                return (tool_name, ToolResult.fail(f"Unknown tool: {tool_name}"))

            async with self._session_factory() as session:
                kwargs = entry.kwargs_builder(
                    session=session,
                    customer_id_str=self._customer_id,
                    message=message,
                )
                try:
                    result = await asyncio.wait_for(
                        entry.func(**kwargs),
                        timeout=_TOOL_TIMEOUT_SECONDS,
                    )
                    await session.commit()
                    return (tool_name, ToolResult.ok(result))
                except TimeoutError:
                    await session.rollback()
                    return (tool_name, ToolResult.fail("Tool timed out"))
                except DomainException as e:
                    await session.rollback()
                    return (tool_name, ToolResult.fail(str(e)))
                except Exception as e:
                    await session.rollback()
                    return (tool_name, ToolResult.fail(f"Unexpected error: {e}"))

        tasks = [_run_single(name) for name in tool_names]
        results = await asyncio.gather(*tasks)
        return dict(results)

    # ── Streaming tool execution (emits per-tool events) ───────────────────

    async def _execute_tools_streaming(
        self,
        tool_names: list[str],
        message: str,
    ) -> AsyncGenerator[tuple[str, ToolResult], None]:

        async def _run_single(tool_name: str) -> tuple[str, ToolResult]:
            entry = self._tool_registry.get(tool_name)
            if entry is None:
                return (tool_name, ToolResult.fail(f"Unknown tool: {tool_name}"))

            async with self._session_factory() as session:
                kwargs = entry.kwargs_builder(
                    session=session,
                    customer_id_str=self._customer_id,
                    message=message,
                )
                try:
                    result = await asyncio.wait_for(
                        entry.func(**kwargs),
                        timeout=_TOOL_TIMEOUT_SECONDS,
                    )
                    await session.commit()
                    return (tool_name, ToolResult.ok(result))
                except TimeoutError:
                    await session.rollback()
                    return (tool_name, ToolResult.fail("Tool timed out"))
                except DomainException as e:
                    await session.rollback()
                    return (tool_name, ToolResult.fail(str(e)))
                except Exception as e:
                    await session.rollback()
                    return (tool_name, ToolResult.fail(f"Unexpected error: {e}"))

        coros = [_run_single(name) for name in tool_names]
        for future in asyncio.as_completed(coros):
            yield await future

    # ── Public streaming turn loop ─────────────────────────────────────────

    async def process_turn_streaming(
        self,
        message: str,
        conversation_history: str | None = None,
    ) -> AsyncGenerator[StageEvent, None]:
        try:
            yield {"stage": "thinking", "label": "Thinking…"}
            await asyncio.sleep(0)

            # ── 1. Intent Analysis ───────────────────────────────────────
            intent_result = await self._analyzer.analyze(message, self._context)
            yield {
                "stage": "intent",
                "label": _INTENT_LABELS.get(intent_result.intent_label, "Analyzing your request…"),
                "intent": intent_result.intent_label,
            }

            # ── 2. Tool Selection ────────────────────────────────────────
            plan = await self._selector.select(intent_result, self._context)
            is_greeting_or_other = intent_result.intent_label in ("greeting", "other")

            tool_calls_made: list[str] = []
            tool_results: dict[str, ToolResult] = {}
            attempted: set[str] = set()

            if not is_greeting_or_other and plan.selected_tools:
                tools_to_run = plan.selected_tools[: plan.max_tool_calls]
                yield {"stage": "tools_selected", "tools": tools_to_run}

                # ── 3. Tool Execution (streaming, parallel) ──────────────
                async for tool_name, result in self._execute_tools_streaming(
                    tools_to_run, message
                ):
                    tool_results[tool_name] = result
                    tool_calls_made.append(tool_name)
                    attempted.add(tool_name)
                    yield {
                        "stage": "tool_done",
                        "tool": tool_name,
                        "ok": result.success,
                    }

                # ── 4. Evidence Aggregation (interim) ────────────────────
                evidence_package = await self._aggregator.aggregate(tool_results)

                # ── 5. Sufficiency Check & Replan (at most one pass) ─────
                if not self._sufficiency_checker.is_sufficient(
                    evidence_package, intent_result.intent_label
                ):
                    replan_tools = self._sufficiency_checker.compute_replan_tools(
                        plan=plan,
                        attempted=attempted,
                        failed=evidence_package.failed_tools,
                    )
                    if replan_tools:
                        yield {"stage": "tools_selected", "tools": replan_tools, "replan": True}
                        async for tool_name, result in self._execute_tools_streaming(
                            replan_tools, message
                        ):
                            if tool_name not in tool_results:
                                tool_results[tool_name] = result
                            if tool_name not in attempted:
                                tool_calls_made.append(tool_name)
                            attempted.add(tool_name)
                            yield {
                                "stage": "tool_done",
                                "tool": tool_name,
                                "ok": result.success,
                            }

                        evidence_package = await self._aggregator.aggregate(tool_results)
            else:
                evidence_package = EvidencePackage(items=[])

            # ── 6. Final Reasoning ───────────────────────────────────────
            yield {"stage": "reasoning"}
            reasoning_output = await self._pipeline.reason(
                evidence_package=evidence_package,
                customer_context=self._context,
                intent=intent_result.intent_label,
                user_message=message,
                conversation_history=conversation_history,
            )

            # ── 7. Done ──────────────────────────────────────────────────
            yield {
                "stage": "done",
                "response": reasoning_output.conclusion,
                "tool_calls_made": tool_calls_made,
                "evidence": (evidence_package.model_dump() if tool_results else None),
                "reasoning_trace": reasoning_output.model_dump(),
            }

        except Exception as e:
            yield {"stage": "error", "message": str(e)}


# ── Stage display labels ────────────────────────────────────────────────────

_INTENT_LABELS: dict[str, str] = {
    "billing_inquiry": "Analyzing billing inquiry…",
    "account_query": "Looking up your account…",
    "support_ticket": "Checking support tickets…",
    "knowledge_query": "Searching policy documents…",
    "analytics_query": "Retrieving usage analytics…",
    "conversation_history_query": "Looking up conversation history…",
    "greeting": "Processing greeting…",
    "other": "Analyzing your request…",
}


# ── Stage event type ────────────────────────────────────────────────────────

class StageEvent(TypedDict, total=False):
    stage: str
    label: str
    intent: str
    tools: list[str]
    replan: bool
    tool: str
    ok: bool
    response: str
    tool_calls_made: list[str]
    evidence: Any
    reasoning_trace: Any
    message: str
