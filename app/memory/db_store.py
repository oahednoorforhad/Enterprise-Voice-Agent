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

    # ── Session queries ────────────────────────────────────────────────

    async def list_sessions(
        self,
        session: AsyncSession,
        customer_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict]:
        """Return paginated sessions for *customer_id* with message stats.

        Each dict contains:
          - id, title, started_at, ended_at
          - message_count (number of messages in the session)
          - last_message_preview (content of the most recent message, if any)

        Results are ordered by ``started_at DESC``.
        """
        uid = uuid.UUID(customer_id)

        # Correlated subquery for message count per session
        count_subq = (
            select(func.count(ConversationMessage.id))
            .where(ConversationMessage.session_id == ConversationSession.id)
            .correlate(ConversationSession)
            .scalar_subquery()
        ).label("message_count")

        # Correlated subquery for the most recent message content
        last_msg_subq = (
            select(ConversationMessage.content)
            .where(ConversationMessage.session_id == ConversationSession.id)
            .order_by(ConversationMessage.created_at.desc())
            .limit(1)
            .correlate(ConversationSession)
            .scalar_subquery()
        ).label("last_message_preview")

        stmt = (
            select(ConversationSession, count_subq, last_msg_subq)
            .where(ConversationSession.customer_id == uid)
            .order_by(ConversationSession.started_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await session.execute(stmt)
        rows = result.all()

        output: list[dict] = []
        for row in rows:
            conv_session: ConversationSession = row[0]
            output.append(
                {
                    "id": str(conv_session.id),
                    "title": conv_session.title,
                    "started_at": (
                        conv_session.started_at.isoformat()
                        if conv_session.started_at
                        else None
                    ),
                    "ended_at": (
                        conv_session.ended_at.isoformat()
                        if conv_session.ended_at
                        else None
                    ),
                    "message_count": row.message_count,
                    "last_message_preview": row.last_message_preview,
                }
            )
        return output

    async def get_session_by_id(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
        customer_id: str,
    ) -> ConversationSession | None:
        """Return a single session by ID, verifying customer ownership.

        Returns ``None`` if the session does not exist or does not belong to
        *customer_id*.
        """
        uid = uuid.UUID(customer_id)
        stmt = select(ConversationSession).where(
            ConversationSession.id == session_id,
            ConversationSession.customer_id == uid,
        )
        result = await session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_session_messages(
        self,
        session: AsyncSession,
        session_id: uuid.UUID,
        customer_id: str,
    ) -> list[ConversationMessage]:
        """Return all messages for a session ordered chronologically.

        Verifies session ownership via :meth:`get_session_by_id`.  Returns
        an empty list if the session is not found or does not belong to the
        customer.
        """
        conv_session = await self.get_session_by_id(
            session, session_id, customer_id
        )
        if conv_session is None:
            return []

        stmt = (
            select(ConversationMessage)
            .where(ConversationMessage.session_id == conv_session.id)
            .order_by(ConversationMessage.created_at.asc())
        )
        result = await session.execute(stmt)
        return list(result.scalars().all())

    async def create_new_session(
        self,
        session: AsyncSession,
        customer_id: str,
    ) -> ConversationSession:
        """Close any active session for *customer_id* and create a new one.

        Any session with ``session_status == 'active'`` and ``ended_at IS NULL``
        is marked as ``closed``.  A fresh session with ``session_status='active'``
        is then created and returned.

        Wraps both steps in a transaction (caller owns the outer transaction).
        """
        uid = uuid.UUID(customer_id)

        # Close any currently active session(s)
        close_stmt = select(ConversationSession).where(
            ConversationSession.customer_id == uid,
            ConversationSession.session_status == "active",
            ConversationSession.ended_at.is_(None),
        )
        result = await session.execute(close_stmt)
        active_sessions = result.scalars().all()
        for s in active_sessions:
            s.session_status = "closed"
            s.ended_at = func.now()
        await session.flush()

        # Create the new active session
        new_session = ConversationSession(
            customer_id=uid,
            session_status="active",
            started_at=datetime.now(UTC),
            language="en",
        )
        session.add(new_session)
        await session.flush()
        return new_session

    # ── Turn management ────────────────────────────────────────────────

    async def add_turn(
        self,
        session: AsyncSession,
        customer_id: str,
        user_message: str,
        assistant_response: str,
        tool_calls_made: list[str] | None = None,
        session_id: uuid.UUID | None = None,
    ) -> None:
        """Persist one user→assistant turn.

        When *session_id* is provided the turn is stored in that specific
        session (ownership verified).  When *session_id* is ``None`` the
        customer's active session is used, with a 30‑minute inactivity
        timeout that starts a fresh session if exceeded.

        If the session has no title yet and this is its first message, a
        title is auto‑generated from the first ~100 characters of the user
        message (or a date‑based fallback for very short messages).
        """
        uid = uuid.UUID(customer_id)

        # ── Resolve session ───────────────────────────────────────────
        if session_id is not None:
            conv_session = await self.get_session_by_id(
                session, session_id, customer_id
            )
            # If session is closed, auto-create a new session
            if conv_session is not None and conv_session.session_status == "closed":
                conv_session = await self.create_new_session(session, customer_id)
            if conv_session is None:
                raise ValueError(
                    f"Session {session_id} not found or does not belong "
                    f"to customer {customer_id}"
                )
        else:
            conv_session = await self.get_or_create_session(
                session, customer_id
            )

            # ── Inactivity check ──────────────────────────────────────
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

        # ── Check existing message count (for title gen) ──────────────
        count_stmt = select(func.count(ConversationMessage.id)).where(
            ConversationMessage.session_id == conv_session.id
        )
        result = await session.execute(count_stmt)
        existing_msg_count = result.scalar()
        is_first_message = existing_msg_count == 0

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

        # ── Auto‑generate title on first message ──────────────────────
        if is_first_message and conv_session.title is None:
            if len(user_message) >= 10:
                conv_session.title = user_message[:100]
            else:
                conv_session.title = (
                    f"Chat from "
                    f"{conv_session.started_at.strftime('%B %d, %Y')}"
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
