"""Async query functions for the Ticket tool family."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import RateLimitError, TicketCreateError, TicketNotFoundError
from app.core.rate_limiter import rate_limiter
from app.db.models import SupportTicket
from app.tools.ticket.models import TicketModel, TicketPreview


async def get_support_tickets(
    session: AsyncSession, customer_id: UUID
) -> list[TicketModel]:
    """Get support tickets with business-aware recency.

    Rules:
    - ALL open and in_progress tickets are returned (regardless of age).
    - closed/resolved tickets are returned only if
      ``updated_at >= NOW() - 30 days``.
    """
    now = datetime.now(UTC)
    cutoff = now - timedelta(days=30)

    result = await session.execute(
        select(SupportTicket)
        .where(
            SupportTicket.customer_id == customer_id,
            or_(
                SupportTicket.status.in_(["open", "in_progress"]),
                and_(
                    SupportTicket.status.in_(["closed", "resolved"]),
                    SupportTicket.updated_at >= cutoff,
                ),
            ),
        )
        .order_by(SupportTicket.updated_at.desc())
    )
    rows = result.scalars().all()
    return [
        TicketModel(
            id=t.id,
            customer_id=t.customer_id,
            subject=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            created_at=t.created_at,
            updated_at=t.updated_at,
        )
        for t in rows
    ]


async def get_ticket_status(
    session: AsyncSession, customer_id: UUID, ticket_id: UUID
) -> TicketModel:
    """Get a single ticket by ID.  Enforces customer_id ownership.

    Raises ``TicketNotFoundError`` if the ticket does not exist **or** if it
    belongs to a different customer.
    """
    result = await session.execute(
        select(SupportTicket).where(
            SupportTicket.id == ticket_id,
            SupportTicket.customer_id == customer_id,
        )
    )
    ticket = result.scalar_one_or_none()
    if ticket is None:
        raise TicketNotFoundError(
            f"Ticket {ticket_id} not found for customer {customer_id}"
        )

    return TicketModel(
        id=ticket.id,
        customer_id=ticket.customer_id,
        subject=ticket.title,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


VALID_CATEGORIES: frozenset[str] = frozenset({
    "bug report", "feature request", "account issue",
    "billing issue", "performance issue", "integration issue", "other",
})

VALID_PRIORITIES: frozenset[str] = frozenset({
    "low", "medium", "high", "critical",
})


async def create_support_ticket(
    session: AsyncSession,
    customer_id: UUID,
    *,
    title: str = "",
    description: str | None = None,
    category: str = "",
    priority: str = "medium",
    confirmed: bool = False,
    message: str = "",
) -> TicketModel | TicketPreview:
    """Create a support ticket with AI validation and rate limiting.

    Args:
        session: DB session.
        customer_id: Owning customer.
        title: Ticket title (may be empty if LLM should parse from message).
        description: Optional description.
        category: One of VALID_CATEGORIES (case-insensitive).
        priority: One of VALID_PRIORITIES (default "medium").
        confirmed: If True, write to DB. If False, return preview only.
        message: Raw user message for LLM parsing (used when title is empty).

    Returns:
        TicketModel when confirmed=True (DB written).
        TicketPreview when confirmed=False (no DB write).

    Raises:
        RateLimitError: When confirmed=True and rate limit exceeded.
        TicketCreateError: When input validation fails.
    """
    # Step 1: Rate limit check (only on confirmed=True)
    if confirmed:
        allowed, wait = await rate_limiter.check_and_increment(str(customer_id))
        if not allowed:
            raise RateLimitError(
                f"Rate limit exceeded. Please wait {wait} seconds before creating another ticket."
            )

    # Step 2: LLM validation (only when confirmed=False and title is empty)
    if not confirmed and not title:
        if not message.strip():
            return TicketPreview(
                title="",
                description="",
                category=category or "other",
                priority=priority,
                valid=True,
                validation_message="Please describe your issue.",
            )
        try:
            from app.core.llm_client import LLMClient, LLMClientError
            from app.tools.ticket.models import TicketAnalysis

            llm = LLMClient()
            analysis = await llm.generate_structured(
                prompt=f"Analyze this support request:\n\n{message}",
                response_schema=TicketAnalysis,
                system_instruction=(
                    "You are a support ticket analyzer. Extract structured information "
                    "from the user's message and validate it against support criteria.\n\n"
                    "Extract:\n"
                    "1. title: Short descriptive summary (max 80 chars).\n"
                    "2. description: Full description of the issue.\n"
                    "3. category: One of: Bug Report, Feature Request, Account Issue, "
                    "Billing Issue, Performance Issue, Integration Issue, Other.\n"
                    "4. priority: One of: low, medium, high, critical.\n\n"
                    "Validate these guardrails (set bool fields accordingly):\n"
                    "- is_specific_and_actionable: Is the issue described specifically "
                    "enough to act on? (not vague)\n"
                    "- is_not_abusive: Is the message respectful and not spam?\n"
                    "- is_not_in_kb: Would this be answered by existing documentation?\n"
                    "- is_product_related: Does this relate to the product/service?\n\n"
                    "If ANY guardrail fails, set the corresponding bool to False and "
                    "provide a validation_message explaining why."
                ),
            )

            # Check guardrails — all must pass
            if not (
                analysis.is_specific_and_actionable
                and analysis.is_not_abusive
                and analysis.is_not_in_kb
                and analysis.is_product_related
            ):
                return TicketPreview(
                    title=analysis.title[:80] if analysis.title else "",
                    description=analysis.description or message,
                    category=analysis.category.lower() if analysis.category else "other",
                    priority=analysis.priority.lower() if analysis.priority else "medium",
                    valid=False,
                    validation_message=(
                        analysis.validation_message
                        or "Your request could not be validated. "
                        "Please provide more specific details about your issue."
                    ),
                )

            return TicketPreview(
                title=analysis.title[:80] if analysis.title else message[:80],
                description=analysis.description or message,
                category=analysis.category.lower() if analysis.category else (category or "other"),
                priority=analysis.priority.lower() if analysis.priority else priority,
                valid=True,
                validation_message=None,
            )
        except (LLMClientError, Exception):
            # If LLM is unavailable, return a safe preview
            return TicketPreview(
                title=message[:80] if len(message) > 80 else message,
                description=message,
                category=category or "other",
                priority=priority,
                valid=True,
                validation_message=(
                    "Unable to validate automatically. "
                    "Please verify the extracted details are correct."
                ),
            )

    # Step 3: Validate inputs
    # Validate category (case-insensitive)
    if category and category.lower() not in VALID_CATEGORIES:
        valid_cats = ", ".join(sorted(VALID_CATEGORIES))
        raise TicketCreateError(
            f"Invalid category '{category}'. Must be one of: {valid_cats}"
        )

    # Validate priority (case-insensitive)
    if priority and priority.lower() not in VALID_PRIORITIES:
        valid_prios = ", ".join(sorted(VALID_PRIORITIES))
        raise TicketCreateError(
            f"Invalid priority '{priority}'. Must be one of: {valid_prios}"
        )

    # Validate title when confirmed=True
    if confirmed and not title.strip():
        raise TicketCreateError("Title is required when creating a ticket.")

    # Step 4: Preview mode (confirmed=False) — no DB write
    if not confirmed:
        return TicketPreview(
            title=title,
            description=description,
            category=category,
            priority=priority,
            valid=True,
            validation_message=None,
        )

    # Step 5: DB write (confirmed=True)
    ticket = SupportTicket(
        customer_id=customer_id,
        title=title,
        description=description,
        category=category.lower() if category else category,
        priority=priority.lower() if priority else priority,
        status="open",
    )
    session.add(ticket)
    await session.flush()
    await session.refresh(ticket)

    return TicketModel(
        id=ticket.id,
        customer_id=ticket.customer_id,
        subject=ticket.title,
        description=ticket.description,
        status=ticket.status,
        priority=ticket.priority,
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )
