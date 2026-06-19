"""Voice WebSocket router and call-summary REST endpoint.

Mounted at ``/api/v1/voice``.

Endpoints
---------
WS  /api/v1/voice/stream
    Bidirectional audio bridge to Gemini Native Audio.
    Auth: ``?token=<token>`` query param (mock mode accepts any value).
    Additional query param: ``?customer_id=<uuid>`` (required in mock mode).

GET /api/v1/voice/summary/{session_id}
    Return the post-session call summary generated after the voice call.
    Responds with ``CallSummaryResult`` or 404 if not yet available.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.websockets import WebSocketDisconnect
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.core.llm_client import LLMClient
from app.db import get_db_session, get_session_factory
from app.db.models import ConversationSession
from app.memory.db_store import DbConversationStore
from app.schemas.voice import CallSummaryResult
from app.tools.history.functions import format_summaries_for_prompt, get_session_history
from app.voice.session import GeminiLiveSession
from app.voice.summary import generate_call_summary

logger = logging.getLogger(__name__)

voice_router = APIRouter(prefix="/api/v1/voice", tags=["Voice"])
_store = DbConversationStore()


# ── WebSocket stream ─────────────────────────────────────────────────────────

@voice_router.websocket("/stream")
async def voice_stream(
    websocket: WebSocket,
    token: str | None = None,
    customer_id: str | None = None,
) -> None:
    """Bidirectional audio bridge to Gemini Native Audio.

    The browser connects with ``?token=<auth_token>&customer_id=<uuid>``.
    In mock-auth mode (development) any token value is accepted and the
    ``customer_id`` query parameter is used directly.

    The session lifecycle:
      1. Accept WebSocket connection.
      2. Validate auth — close with 4001 on failure.
      3. Run ``GeminiLiveSession`` (blocks until browser disconnects).
      4. On disconnect: generate call summary and persist to the DB.
    """
    await websocket.accept()
    settings = get_settings()

    # ── Auth ──────────────────────────────────────────────────────────────
    if not settings.mock_auth_enabled and not token:
        await websocket.close(code=4001, reason="Authentication required")
        return

    if not customer_id:
        # Fallback to the mock test customer so the UI works out of the box
        customer_id = "c63d2f89-9aa3-4157-8205-a7d6cfc23207"
        logger.debug("voice_stream: no customer_id supplied, using default")

    customer_context = {
        "customer_id": customer_id,
        "name": "Valued Customer",
        "email": "customer@clouddesk.com",
        "company": "CloudDesk",
        "plan_tier": "enterprise",
    }

    # ── Session ───────────────────────────────────────────────────────────
    session_factory = get_session_factory()

    # Passively inject prior session summaries into the system prompt BEFORE
    # connecting to Gemini — zero dead-air latency vs. a tool call at session start.
    try:
        import uuid as _uuid
        async with session_factory() as db:
            history = await get_session_history(
                db, _uuid.UUID(customer_id), limit=3
            )
        customer_context["recent_sessions"] = format_summaries_for_prompt(history)
        logger.debug(
            "voice_stream: injected %d prior session(s) into system prompt for %s",
            history.total, customer_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning("voice_stream: could not load session history: %s", exc)
        customer_context["recent_sessions"] = "No prior sessions on record."

    live = GeminiLiveSession(
        customer_id=customer_id,
        customer_context=customer_context,
        session_factory=session_factory,
    )

    try:
        session_id, tools_called = await live.run(websocket)
    except WebSocketDisconnect:
        session_id = live.session_id
        tools_called = live.tools_called
        logger.debug("voice_stream: WS disconnected — session %s", session_id)
    except Exception as exc:  # noqa: BLE001
        logger.error("voice_stream: unexpected error — %s", exc, exc_info=True)
        session_id = live.session_id
        tools_called = live.tools_called

    # ── Post-session: generate and persist summary ────────────────────────
    transcript = live.transcript
    logger.info(
        "voice_stream: session %s ended — transcript_turns=%d tools=%s",
        session_id, len(transcript), tools_called,
    )
    # Always generate a summary; generate_call_summary handles empty transcripts
    # gracefully with a "(no transcript available)" fallback.
    await _persist_summary(
        session_factory=session_factory,
        customer_id=customer_id,
        session_id=session_id,
        transcript=transcript,
        tools_called=tools_called,
        customer_context=customer_context,
    )


async def _persist_summary(
    session_factory,
    customer_id: str,
    session_id: str,
    transcript: list[dict],
    tools_called: list[str],
    customer_context: dict,
) -> None:
    """Generate a call summary via LLM and write it to the DB."""
    try:
        llm_client = LLMClient()
        summary_result = await generate_call_summary(
            llm_client=llm_client,
            session_id=session_id,
            transcript=transcript,
            tools_called=tools_called,
            customer_context=customer_context,
        )
        summary_json = summary_result.model_dump_json()

        logger.info(
            "Persisting summary for session %s — transcript_turns=%d tools=%s",
            session_id, len(transcript), tools_called,
        )

        async with session_factory() as db_session:
            # Voice calls don't create a ConversationSession row up-front, so
            # we ensure one exists before update_session_summary tries to find it.
            conv_sess = await _store.get_or_create_session(db_session, customer_id)
            conv_sess.voice_session_id = session_id
            await db_session.flush()

            updated = await _store.update_session_summary(
                session=db_session,
                customer_id=customer_id,
                summary=summary_json,
                tools_used=tools_called,
                voice_session_id=session_id,
            )
            await db_session.commit()
            if updated:
                logger.info("Call summary persisted for session %s", session_id)
            else:
                logger.warning("No DB session found for voice session %s", session_id)

    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to persist call summary for %s: %s", session_id, exc)


# ── Summary REST endpoint ────────────────────────────────────────────────────

@voice_router.get("/summary/{session_id}", response_model=CallSummaryResult)
async def get_call_summary(
    session_id: str,
    db: AsyncSession = Depends(get_db_session),
) -> CallSummaryResult:
    """Return the call summary for a completed voice session.

    The ``session_id`` matches the ``voice_session_id`` stored on the
    ``ConversationSession`` row after the call ends.

    Raises 404 if the session does not exist or its summary has not yet
    been generated.
    """
    try:
        stmt = (
            select(ConversationSession)
            .where(ConversationSession.voice_session_id == session_id)
            .limit(1)
        )
        result = await db.execute(stmt)
        conv_session = result.scalar_one_or_none()
    except SQLAlchemyError as exc:
        logger.error("DB error fetching summary for %s: %s", session_id, exc)
        raise HTTPException(status_code=500, detail="Database error fetching summary.") from exc

    if conv_session is None or conv_session.summary is None:
        raise HTTPException(
            status_code=404,
            detail=f"Call summary for session '{session_id}' not found.",
        )

    try:
        return CallSummaryResult.model_validate_json(conv_session.summary)
    except Exception as exc:
        raise HTTPException(status_code=500, detail="Stored summary is malformed.") from exc
