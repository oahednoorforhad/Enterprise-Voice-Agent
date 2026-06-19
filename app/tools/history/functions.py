"""History tool — get_session_history.

Retrieves the last N completed conversation sessions for a customer where a
summary exists.  Used both as a Gemini Live tool (mid-call) and as a passive
injector in the voice router (zero-latency session-start context).
"""

from __future__ import annotations

import json
import logging
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationSession
from app.tools.history.models import SessionHistoryItem, SessionHistoryResult

logger = logging.getLogger(__name__)


async def get_session_history(
    session: AsyncSession,
    customer_id: UUID,
    limit: int = 3,
) -> SessionHistoryResult:
    """Return the customer's most recent completed sessions with summaries.

    Only sessions with a non-null ``summary`` field and a terminal status
    (``completed`` or ``closed``) are returned, ordered newest first.

    Parameters
    ----------
    session:
        Open SQLAlchemy async session.
    customer_id:
        Authenticated customer UUID — never taken from user input.
    limit:
        Maximum number of sessions to return (default 3).

    Returns
    -------
    SessionHistoryResult
        List of ``SessionHistoryItem`` objects with conversation summaries.
    """
    stmt = (
        select(ConversationSession)
        .where(
            ConversationSession.customer_id == customer_id,
            ConversationSession.summary.isnot(None),
            ConversationSession.session_status.in_(["completed", "closed"]),
        )
        .order_by(ConversationSession.started_at.desc())
        .limit(limit)
    )

    result = await session.execute(stmt)
    rows = result.scalars().all()

    items: list[SessionHistoryItem] = []
    for row in rows:
        items.append(_parse_session(row))

    return SessionHistoryResult(sessions=items, total=len(items))


def _parse_session(row: ConversationSession) -> SessionHistoryItem:
    """Convert one ConversationSession ORM row into a SessionHistoryItem.

    The ``summary`` column stores either:
    - A JSON string (from voice CallSummaryResult or chat summary)
    - A plain text string (legacy / fallback)

    Both cases are handled gracefully.
    """
    date_str = row.started_at.date().isoformat() if row.started_at else "unknown"

    summary_raw = row.summary or ""
    conversation_summary = summary_raw
    sources_used: list[str] = []
    next_actions: list[str] = []

    try:
        parsed = json.loads(summary_raw)
        if isinstance(parsed, dict):
            conversation_summary = parsed.get("conversation_summary", summary_raw)
            sources_used = parsed.get("sources_used", [])
            next_actions = parsed.get("recommended_next_actions", [])
    except (json.JSONDecodeError, TypeError):
        # Plain text summary — use as-is
        pass

    return SessionHistoryItem(
        session_id=str(row.id),
        date=date_str,
        conversation_summary=conversation_summary,
        sources_used=sources_used,
        recommended_next_actions=next_actions,
    )


def format_summaries_for_prompt(result: SessionHistoryResult) -> str:
    """Format SessionHistoryResult as natural-language bullet points for a system prompt.

    Returns a string like:
        - Jun 12 2026: Customer asked about API rate limits. EVA recommended /bulk-import.
        - May 08 2026: SSO failure after Azure AD update. Resolved — callback URL fix.
        - Mar 20 2026: Duplicate $299 charge in March. Credit applied to April invoice.

    Returns 'No prior sessions on record.' if the list is empty.
    """
    if not result.sessions:
        return "No prior sessions on record."

    lines = []
    for item in result.sessions:
        # Parse date for friendly display
        try:
            from datetime import date as _date
            d = _date.fromisoformat(item.date)
            friendly_date = d.strftime("%b %d %Y")
        except ValueError:
            friendly_date = item.date

        # Truncate long summaries to keep system prompt compact
        summary = item.conversation_summary
        if len(summary) > 200:
            summary = summary[:197] + "..."

        line = f"- {friendly_date}: {summary}"
        if item.recommended_next_actions:
            line += f" Next: {item.recommended_next_actions[0]}"
        lines.append(line)

    return "\n".join(lines)
