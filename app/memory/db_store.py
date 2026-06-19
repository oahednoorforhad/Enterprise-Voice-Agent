"""PostgreSQL-backed conversation store using ORM models.

Replaces the in-memory ``ConversationMemory`` with a durable store that
persists turns to ``conversation_sessions`` and ``conversation_messages``
tables.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.models import ConversationMessage, ConversationSession


class DbConversationStore:
    """Stateless conversation store backed by PostgreSQL.

    Every method accepts an ``AsyncSession`` so the caller owns the
    transactional boundary.  No mutable state lives on the instance.
    """

    # ── Session lifecycle ──────────────────────────────────────────────

    async def get_or_create_session(
        self,
        session: AsyncSession,
        customer_id: str,
    ) -> ConversationSession:
        """Return the active session for *customer_id* or create one.

        An *active* session is one whose ``session_status == 'active'``
        and ``ended_at IS NULL``.  If none exists a new session is
        created and flushed so its PK is available to the caller.
        """
        uid = uuid.UUID(customer_id)

        stmt = (
            select(ConversationSession)
            .where(
                ConversationSession.customer_id == uid,
                ConversationSession.session_status == "active",
                ConversationSession.ended_at.is_(None),
            )
            .order_by(ConversationSession.started_at.desc())
            .limit(1)
        )
        result = await session.execute(stmt)
        existing = result.scalar_one_or_none()

        if existing is not None:
            return existing

        new_session = ConversationSession(
            customer_id=uid,
            session_status="active",
            started_at=func.now(),
            language="en",
        )
        session.add(new_session)
        await session.flush()
        return new_session

    async def _close_session(
        self,
        session: AsyncSession,
        conv_session: ConversationSession,
    ) -> None:
        """Mark *conv_session* as ended."""
        conv_session.session_status = "closed"
        conv_session.ended_at = func.now()
        await session.flush()

    # ── Turn management ────────────────────────────────────────────────

    async def add_turn(
        self,
        session: AsyncSession,
        customer_id: str,
        user_message: str,
        assistant_response: str,
        tool_calls_made: list[str] | None = None,
    ) -> None:
        """Persist one user→assistant turn.

        If the customer's active session has been idle for more than 30
        minutes the old session is closed and a new one is started before
        storing the turn.
        """
        conv_session = await self.get_or_create_session(session, customer_id)

        # ── Inactivity check ──────────────────────────────────────────
        # Look up the most recent message in this session; if it was
        # created more than 30 minutes ago, close the session and open
        # a fresh one for the new turn.
        last_msg_stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.session_id == conv_session.id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(1)
        )
        result = await session.execute(last_msg_stmt)
        last_msg = result.scalar_one_or_none()

        if last_msg is not None:
            age = datetime.now(UTC) - last_msg.created_at
            if age > timedelta(minutes=30):
                await self._close_session(session, conv_session)
                conv_session = await self.get_or_create_session(
                    session, customer_id
                )

        # ── Store user message ────────────────────────────────────────
        session.add(
            ConversationMessage(
                session_id=conv_session.id,
                role="user",
                content=user_message,
            )
        )

        # ── Store assistant message ───────────────────────────────────
        tool_calls_dict: dict | None = None
        if tool_calls_made is not None:
            tool_calls_dict = {"tools": tool_calls_made}

        session.add(
            ConversationMessage(
                session_id=conv_session.id,
                role="assistant",
                content=assistant_response,
                tool_calls=tool_calls_dict,
            )
        )

        await session.flush()

    # ── Voice session updates ──────────────────────────────────────────

    async def update_session_summary(
        self,
        session: AsyncSession,
        customer_id: str,
        summary: str,
        tools_used: list[str] | None = None,
        voice_session_id: str | None = None,
        audio_duration_seconds: int | None = None,
    ) -> bool:
        """Persist a call summary to the customer's most recent active session.

        Looks up the session by ``voice_session_id`` first; falls back to the
        active session for ``customer_id``.  Returns ``True`` if a session was
        updated, ``False`` if no matching session was found.
        """
        uid = uuid.UUID(customer_id)
        conv_session: ConversationSession | None = None

        if voice_session_id is not None:
            stmt = (
                select(ConversationSession)
                .where(
                    ConversationSession.customer_id == uid,
                    ConversationSession.voice_session_id == voice_session_id,
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            conv_session = result.scalar_one_or_none()

        if conv_session is None:
            # Fallback: use the active session
            stmt = (
                select(ConversationSession)
                .where(
                    ConversationSession.customer_id == uid,
                    ConversationSession.session_status == "active",
                    ConversationSession.ended_at.is_(None),
                )
                .order_by(ConversationSession.started_at.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            conv_session = result.scalar_one_or_none()

        if conv_session is None:
            return False

        conv_session.summary = summary
        conv_session.session_status = "closed"
        conv_session.ended_at = func.now()

        if tools_used is not None:
            conv_session.tools_used = {"tools": tools_used}
        if voice_session_id is not None:
            conv_session.voice_session_id = voice_session_id
        if audio_duration_seconds is not None:
            conv_session.audio_duration_seconds = audio_duration_seconds

        await session.flush()
        return True

    # ── Prompt assembly ────────────────────────────────────────────────

    async def format_prompt_context(
        self,
        session: AsyncSession,
        customer_id: str,
        current_session_id: uuid.UUID | None = None,
    ) -> str:
        """Build a readable prior-conversation block for LLM prompts.

        Loads up to 10 completed turns (20 messages) from the specified
        session (or the active session for *customer_id* when
        *current_session_id* is ``None``).

        Returns an empty string when there is no prior conversation.
        """
        # Resolve the target session
        if current_session_id is not None:
            stmt = select(ConversationSession).where(
                ConversationSession.id == current_session_id
            )
            result = await session.execute(stmt)
            conv_session = result.scalar_one_or_none()
            if conv_session is None:
                return ""
        else:
            conv_session = await self.get_or_create_session(session, customer_id)

        # Load the most recent messages (up to 20 = 10 full turns)
        msg_stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.session_id == conv_session.id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(20)
        )
        result = await session.execute(msg_stmt)
        messages = list(result.scalars().all())

        if not messages:
            return ""

        # Reverse to chronological order
        messages.reverse()

        lines = ["--- Prior conversation ---"]
        turn_num = 1
        idx = 0
        while idx < len(messages):
            current = messages[idx]
            if current.role == "user":
                user_content = current.content
                # Look ahead for the matching assistant message
                if (
                    idx + 1 < len(messages)
                    and messages[idx + 1].role == "assistant"
                ):
                    assistant_content = messages[idx + 1].content
                    lines.append(f"Turn {turn_num}:")
                    lines.append(f"  Customer: {user_content}")
                    lines.append(f"  EVA:      {assistant_content}")
                    idx += 2
                else:
                    # Orphan user message — include without assistant
                    lines.append(f"Turn {turn_num}:")
                    lines.append(f"  Customer: {user_content}")
                    idx += 1
                turn_num += 1
            else:
                # Standalone assistant message (shouldn't normally occur)
                lines.append(f"Turn {turn_num}:")
                lines.append("  Customer: _")
                lines.append(f"  EVA:      {current.content}")
                turn_num += 1
                idx += 1

        lines.append("--- End of prior conversation ---\n")
        return "\n".join(lines)
