"""Evidence aggregation module — merges tool outputs into a normalised EvidencePackage.

The ``EvidenceAggregator`` is a stateless converter that receives raw
``ToolResult`` instances (one per tool that was called) and produces a single
:class:`EvidencePackage` containing normalised :class:`EvidenceItem` entries
plus a list of tools that failed.

Usage::

    aggregator = EvidenceAggregator()
    package = await aggregator.aggregate({
        "get_customer_profile": ToolResult.ok(profile),
        "get_billing_history":  ToolResult.ok(records),
        "get_usage_analytics":  ToolResult.fail("service unavailable"),
    })
    # package.items         → [EvidenceItem, ...]
    # package.failed_tools  → ["get_usage_analytics"]
    # package.total_sources → len(items)
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from app.schemas.reasoning import EvidenceItem, EvidencePackage
from app.schemas.tools import ToolResult


def _now_iso() -> str:
    """RFC 3339 / ISO 8601 timestamp string at the moment of aggregation."""
    return datetime.now(UTC).isoformat()


class EvidenceAggregator:
    """Stateless converter that merges tool results into an EvidencePackage.

    No constructor arguments are needed — the aggregator is a pure function
    object that can be shared across turns.
    """

    async def aggregate(
        self,
        tool_results: dict[str, ToolResult],
    ) -> EvidencePackage:
        """Convert tool results into a normalised evidence package.

        Parameters
        ----------
        tool_results:
            Mapping of tool name → ``ToolResult``.  Keys are the canonical
            tool function names (e.g. ``"get_customer_profile"``).

        Returns
        -------
        EvidencePackage
            Normalised evidence items plus a list of tools that failed.
            ``total_sources`` is always set to ``len(items)``.
        """
        items: list[EvidenceItem] = []
        failed_tools: list[str] = []
        now = _now_iso()

        for tool_name, result in tool_results.items():
            if not result.success:
                failed_tools.append(tool_name)
                continue

            data = result.data
            if data is None:
                # success=True but no data — skip silently, not a failure.
                continue

            # Branch: list data → one EvidenceItem per element;
            #          scalar   → single item.
            if isinstance(data, list):
                if not data:
                    continue  # empty list → no items to create
                records = data
            else:
                records = [data]

            for record in records:
                item = self._build_item(tool_name, record, now)
                items.append(item)

        return EvidencePackage(
            items=items,
            failed_tools=failed_tools,
            total_sources=len(items),
        )

    # ── Per-tool item builders ─────────────────────────────────────────────

    def _build_item(
        self,
        tool_name: str,
        data: Any,
        timestamp: str,
    ) -> EvidenceItem:
        """Dispatch to the correct builder based on *tool_name*.

        For unrecognised tool names a generic ``EvidenceItem`` is returned
        with ``source`` and ``tool_name`` both set to the unknown name.
        """
        builder = _TOOL_BUILDERS.get(tool_name)
        if builder is not None:
            return builder(data, timestamp)
        return self._build_generic(tool_name, data, timestamp)

    # ── Generic fallback ───────────────────────────────────────────────────

    @staticmethod
    def _build_generic(
        tool_name: str,
        data: Any,
        timestamp: str,
    ) -> EvidenceItem:
        return EvidenceItem(
            source=tool_name,
            tool_name=tool_name,
            content=str(data),
            metadata={},
            timestamp=timestamp,
        )


# ── Tool-specific builder registry ─────────────────────────────────────────
# Each builder receives a single record (never a list) and a timestamp string,
# and returns an EvidenceItem.

_TOOL_BUILDERS: dict[str, Callable[[Any, str], EvidenceItem]] = {}


# ── Customer tools ─────────────────────────────────────────────────────────


def _build_customer_profile(data: Any, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source="customer_profile",
        tool_name="get_customer_profile",
        content=data.model_dump_json(),
        metadata={
            "customer_id": str(data.id),
            "is_active": data.is_active,
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["get_customer_profile"] = _build_customer_profile


def _build_subscription_status(data: Any, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source="subscription",
        tool_name="get_subscription_status",
        content=data.model_dump_json(),
        metadata={
            "plan": data.plan,
            "status": data.status,
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["get_subscription_status"] = _build_subscription_status


# ── Billing tools ──────────────────────────────────────────────────────────


def _build_billing_record(data: Any, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source="billing_records",
        tool_name="get_billing_history",
        content=data.model_dump_json(),
        metadata={
            "record_id": str(data.id),
            "status": data.status,
            "amount": str(data.amount),
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["get_billing_history"] = _build_billing_record


# ── Ticket tools ───────────────────────────────────────────────────────────


def _build_support_ticket(data: Any, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source="support_tickets",
        tool_name="get_support_tickets",
        content=data.model_dump_json(),
        metadata={
            "ticket_id": str(data.id),
            "status": data.status,
            "priority": data.priority,
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["get_support_tickets"] = _build_support_ticket


def _build_created_ticket(data: Any, timestamp: str) -> EvidenceItem:
    """Build evidence item from a created ticket."""
    return EvidenceItem(
        source="support_tickets",
        tool_name="create_support_ticket",
        content=data.model_dump_json(),
        metadata={
            "ticket_id": str(data.id),
            "status": data.status,
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["create_support_ticket"] = _build_created_ticket


def _build_ticket_status(data: Any, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source="support_tickets",
        tool_name="get_ticket_status",
        content=data.model_dump_json(),
        metadata={
            "ticket_id": str(data.id),
            "status": data.status,
            "priority": data.priority,
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["get_ticket_status"] = _build_ticket_status


# ── Knowledge tools ────────────────────────────────────────────────────────


def _build_knowledge_doc(data: Any, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source="documentation",
        tool_name="search_documentation",
        content=data.content,
        metadata={
            "doc_id": str(data.id),
            "score": data.similarity_score,
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["search_documentation"] = _build_knowledge_doc


def _build_knowledge_policy(data: Any, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source="policies",
        tool_name="search_policies",
        content=data.content,
        metadata={
            "doc_id": str(data.id),
            "score": data.similarity_score,
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["search_policies"] = _build_knowledge_policy


# ── Analytics tools ────────────────────────────────────────────────────────


def _build_usage_analytic(data: Any, timestamp: str) -> EvidenceItem:
    return EvidenceItem(
        source="usage_analytics",
        tool_name="get_usage_analytics",
        content=data.model_dump_json(),
        metadata={
            "record_id": str(data.id),
            "metric": data.metric_name,
            "value": data.metric_value,
        },
        timestamp=timestamp,
    )


_TOOL_BUILDERS["get_usage_analytics"] = _build_usage_analytic
