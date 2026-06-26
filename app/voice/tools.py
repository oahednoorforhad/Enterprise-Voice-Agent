"""Gemini Live function declarations and server-side tool dispatcher.

``GEMINI_TOOL_DECLARATIONS`` is passed directly to
``types.Tool(function_declarations=...)`` inside ``GeminiLiveSession``.

Security contract
-----------------
``customer_id`` is NEVER a declared parameter — it is always injected
server-side from the authenticated WebSocket session context.  Any tool
that is scoped to a customer receives the ID silently; the model never
has the ability to supply or override it.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.core.exceptions import RateLimitError, TicketCreateError
from app.tools.analytics.functions import get_usage_analytics
from app.tools.billing.functions import get_billing_history
from app.tools.customer.functions import get_customer_profile, get_subscription_status
from app.tools.history.functions import get_session_history
from app.tools.knowledge.functions import search_documentation, search_policies
from app.tools.ticket.functions import create_support_ticket, get_support_tickets, get_ticket_status

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Gemini function declarations
# Each entry is a dict understood by google.genai's LiveConnectConfig.
# customer_id intentionally absent from every declaration.
# ---------------------------------------------------------------------------

GEMINI_TOOL_DECLARATIONS: list[dict] = [
    {
        "name": "create_support_ticket",
        "description": (
            "Create a support ticket for the customer's issue. "
            "The customer must confirm before creation. "
            "Use confirmed=false first to return a preview, then call again with confirmed=true "
            "after the customer approves."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Short summary of the issue",
                },
                "description": {
                    "type": "string",
                    "description": "Detailed description of the issue",
                },
                "category": {
                    "type": "string",
                    "enum": [
                        "Bug Report",
                        "Feature Request",
                        "Account Issue",
                        "Billing Issue",
                        "Performance Issue",
                        "Integration Issue",
                        "Other",
                    ],
                    "description": "Category of the issue",
                },
                "priority": {
                    "type": "string",
                    "enum": ["low", "medium", "high", "critical"],
                    "description": "Priority of the ticket",
                },
                "confirmed": {
                    "type": "boolean",
                    "description": (
                        "Set to true only after the customer has explicitly confirmed "
                        "they want to create the ticket"
                    ),
                },
            },
            "required": ["title", "confirmed"],
        },
    },
    {
        "name": "get_customer_profile",
        "description": (
            "Retrieve the authenticated customer's profile including name, "
            "email, company, plan tier, and active status.  Call this first "
            "when the conversation needs account context."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_subscription_status",
        "description": (
            "Get the customer's current subscription details including plan "
            "name, status (active/cancelled/past_due), billing dates, and "
            "monthly amount."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_billing_history",
        "description": (
            "Retrieve the customer's recent billing records from the last "
            "90 days, including invoices, payment status, amounts, and dates. "
            "Use this for billing disputes, charge inquiries, or payment history."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_support_tickets",
        "description": (
            "List the customer's open and recently closed support tickets "
            "from the past 30 days.  Returns title, status, priority, "
            "category, and assigned agent."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
        },
    },
    {
        "name": "get_ticket_status",
        "description": (
            "Get detailed status and history for a specific support ticket "
            "by its ID.  Use when the customer asks about a particular ticket "
            "or provides a ticket reference."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "ticket_id": {
                    "type": "string",
                    "description": (
                        "UUID of the support ticket to look up, e.g. "
                        "'a1b2c3d4-e5f6-7890-abcd-ef1234567890'."
                    ),
                },
            },
            "required": ["ticket_id"],
        },
    },
    {
        "name": "get_usage_analytics",
        "description": (
            "Retrieve usage metrics for the customer over the past 90 days. "
            "Optionally filter by a specific metric name such as 'api_calls', "
            "'storage_gb', or 'active_users'.  Returns time-series data with "
            "period start/end and metric values."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "metric_name": {
                    "type": "string",
                    "description": (
                        "Optional metric name to filter by, e.g. 'api_calls'. "
                        "Omit to retrieve all metrics."
                    ),
                },
            },
        },
    },
    {
        "name": "search_documentation",
        "description": (
            "Search the product documentation knowledge base using semantic "
            "similarity.  Use for how-to questions, feature explanations, "
            "troubleshooting guides, or integration help."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural-language question or topic to search for "
                        "in the documentation, e.g. 'how to set up SSO'."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_policies",
        "description": (
            "Search the company policy and compliance knowledge base.  Use "
            "for questions about refund policy, SLA guarantees, data retention, "
            "acceptable use, GDPR, or contractual terms."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Natural-language question or topic to search for "
                        "in the policy documents, e.g. 'refund eligibility'."
                    ),
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_session_history",
        "description": (
            "Retrieve the customer's recent conversation history — summaries of "
            "prior calls and chats, including issues discussed, tools used, and "
            "recommended next actions.  Call this whenever the customer references "
            "a previous interaction, an unresolved issue, or uses phrases like "
            "'still', 'again', 'last time', 'same problem', or 'not fixed yet'."
        ),
        "parameters": {
            "type": "object",
            "properties": {},   # customer_id always injected server-side
        },
    },
]


# ---------------------------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------------------------

async def dispatch_tool(
    tool_name: str,
    args: dict,
    session_factory: async_sessionmaker[AsyncSession],
    customer_id: UUID,
) -> dict:
    """Execute a Gemini-requested tool and return a JSON-serialisable result.

    ``customer_id`` is always injected server-side; it is never taken from
    ``args`` even if Gemini were to supply it.

    Parameters
    ----------
    tool_name:
        Name from the Gemini ``FunctionCall`` message.
    args:
        Arguments dict from the Gemini ``FunctionCall`` message.
    session_factory:
        Async session maker from the application DB engine.
    customer_id:
        Authenticated customer UUID, injected from WS session context.

    Returns
    -------
    dict
        JSON-serialisable result to send back as a ``FunctionResponse``.
        On known errors an ``{"error": "..."}`` dict is returned so Gemini
        can give a helpful reply instead of seeing a tool timeout.
    """
    logger.debug("dispatch_tool: %s args=%s customer=%s", tool_name, args, customer_id)

    try:
        async with session_factory() as session:
            return await _run_tool(tool_name, args, session, customer_id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("dispatch_tool %s failed: %s", tool_name, exc)
        return {"error": str(exc)}


async def _run_tool(
    tool_name: str,
    args: dict,
    session: AsyncSession,
    customer_id: UUID,
) -> dict:
    """Inner dispatch — runs inside an open DB session."""

    if tool_name == "get_customer_profile":
        result = await get_customer_profile(session, customer_id)
        return result.model_dump(mode="json")

    if tool_name == "get_subscription_status":
        result = await get_subscription_status(session, customer_id)
        return result.model_dump(mode="json")

    if tool_name == "get_billing_history":
        records = await get_billing_history(session, customer_id)
        return {"records": [r.model_dump(mode="json") for r in records]}

    if tool_name == "get_support_tickets":
        tickets = await get_support_tickets(session, customer_id)
        return {"tickets": [t.model_dump(mode="json") for t in tickets]}

    if tool_name == "get_ticket_status":
        ticket_id = UUID(args["ticket_id"])
        result = await get_ticket_status(session, customer_id, ticket_id)
        return result.model_dump(mode="json")

    if tool_name == "get_usage_analytics":
        metric_name: str | None = args.get("metric_name")
        analytics = await get_usage_analytics(session, customer_id, metric_name)
        return {"analytics": [a.model_dump(mode="json") for a in analytics]}

    if tool_name == "search_documentation":
        results = await search_documentation(session, args["query"])
        return {"results": [r.model_dump(mode="json") for r in results]}

    if tool_name == "search_policies":
        results = await search_policies(session, args["query"])
        return {"results": [r.model_dump(mode="json") for r in results]}

    if tool_name == "get_session_history":
        result = await get_session_history(session, customer_id)
        return result.model_dump(mode="json")

    if tool_name == "create_support_ticket":
        try:
            ticket = await create_support_ticket(
                session,
                customer_id,
                title=args.get("title", ""),
                description=args.get("description"),
                category=args.get("category", ""),
                priority=args.get("priority", "medium"),
                confirmed=args.get("confirmed", False),
            )
            return ticket.model_dump(mode="json")
        except (RateLimitError, TicketCreateError) as e:
            return {"error": str(e)}

    raise ValueError(f"Unknown tool name: {tool_name!r}")
