"""Chat router — single-turn text entrypoint for the Sprint 3 reasoning engine.

Mounted at ``/api/v1/chat``.  Accepts a plain-text message plus customer
identifier and returns a structured ``ChatResponse`` from the orchestrator.
"""

import asyncio
import json
import uuid

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse, StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_llm_client
from app.core.llm_client import LLMClient
from app.db import get_db_session, get_session_factory
from app.memory import DbConversationStore
from app.orchestrator.service import OrchestratorService
from app.schemas.reasoning import ChatRequest, ChatResponse
from app.schemas.session import (
    CreateSessionResponse,
    MessageItem,
    SessionListResponse,
    SessionMessagesResponse,
    SessionSummary,
)

chat_router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# PostgreSQL-backed conversation store — survives server restarts.
_memory = DbConversationStore()


@chat_router.post("/")
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
    llm: LLMClient = Depends(get_llm_client),
) -> dict:
    """Process a single chat turn through the reasoning engine.

    Accepts a ``ChatRequest`` with ``message`` and ``customer_id``, runs
    the full orchestrator loop (intent analysis → tool selection → tool
    execution → evidence aggregation → reasoning), and returns a
    ``ChatResponse``.

    Conversation history is loaded from PostgreSQL before the turn and
    saved after the turn so the LLM is aware of prior discussion.
    """
    # The ``customer_id`` is taken from the JWT (via ``get_current_user``)
    # rather than from the request body — the server is the authority for
    # which customer is making the call, not the client.
    customer_id = current_user["customer_id"]
    customer_context = {**current_user, "customer_id": customer_id}

    history_context = await _memory.format_prompt_context(
        session, customer_id
    )

    factory = get_session_factory()
    orchestrator = OrchestratorService(
        llm_client=llm,
        session_factory=factory,
        customer_id=customer_id,
        customer_context=customer_context,
    )
    result = await orchestrator.process_turn(
        request.message,
        conversation_history=history_context,
    )

    await _memory.add_turn(
        session=session,
        customer_id=customer_id,
        user_message=request.message,
        assistant_response=result.response,
    )

    return {
        "success": True,
        "data": result.model_dump(),
        "error": None,
    }


@chat_router.post("/stream")
async def chat_stream(
    request: ChatRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
    llm: LLMClient = Depends(get_llm_client),
) -> StreamingResponse:
    customer_id = current_user["customer_id"]
    customer_context = {**current_user, "customer_id": customer_id}

    # ── Session resolution ───────────────────────────────────────────────
    session_error: str | None = None
    if request.session_id is not None:
        conv_session = await _memory.get_session_by_id(
            session, uuid.UUID(request.session_id), customer_id
        )
        if conv_session is None:
            session_error = "Session not found"
    else:
        conv_session = await _memory.get_or_create_session(session, customer_id)

    if session_error is None:
        history_context = await _memory.format_prompt_context(
            session, customer_id, current_session_id=conv_session.id
        )
    else:
        history_context = ""

    factory = get_session_factory()
    orchestrator = OrchestratorService(
        llm_client=llm,
        session_factory=factory,
        customer_id=customer_id,
        customer_context=customer_context,
    )

    user_message = request.message

    async def event_generator():
        # ── Error on invalid session ─────────────────────────────────
        if session_error is not None:
            yield f"data: {json.dumps({'stage': 'error', 'message': session_error})}\n\n"
            return

        # ── Session event must be first ──────────────────────────────
        yield f"data: {json.dumps({'stage': 'session', 'session_id': str(conv_session.id)})}\n\n"

        final_response: str | None = None
        tool_calls_made: list[str] = []

        async for event in orchestrator.process_turn_streaming(
            user_message, conversation_history=history_context
        ):
            data = json.dumps(event)
            yield f"data: {data}\n\n"
            await asyncio.sleep(0)

            if event.get("stage") == "done":
                final_response = event.get("response", "")
                tool_calls_made = event.get("tool_calls_made", [])

        if final_response is not None:
            await _memory.add_turn(
                session=session,
                customer_id=customer_id,
                user_message=user_message,
                assistant_response=final_response,
                session_id=conv_session.id,
            )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


# ── Session management endpoints ─────────────────────────────────────


@chat_router.get("/sessions")
async def list_sessions(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """List all sessions for the authenticated customer.

    Returns a ``SessionListResponse`` with session summaries ordered by
    ``started_at DESC``.
    """
    customer_id = current_user["customer_id"]
    sessions = await _memory.list_sessions(session, customer_id)

    return {
        "success": True,
        "data": SessionListResponse(
            sessions=[
                SessionSummary(
                    session_id=s["id"],
                    title=s["title"],
                    started_at=s["started_at"],
                    ended_at=s["ended_at"],
                    message_count=s["message_count"],
                    last_message_preview=s["last_message_preview"],
                )
                for s in sessions
            ],
            total=len(sessions),
        ).model_dump(),
        "error": None,
    }


@chat_router.get("/sessions/{session_id}/messages")
async def get_session_messages(
    session_id: str,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Get all messages for a specific session.

    Verifies session ownership via ``get_session_by_id()``.  Returns 404
    if the session does not exist or does not belong to the authenticated
    customer.
    """
    customer_id = current_user["customer_id"]
    session_id_uuid = uuid.UUID(session_id)

    conv_session = await _memory.get_session_by_id(
        session, session_id_uuid, customer_id
    )
    if conv_session is None:
        return JSONResponse(
            status_code=404,
            content={
                "success": False,
                "data": None,
                "error": "Session not found",
            },
        )

    messages = await _memory.get_session_messages(
        session, session_id_uuid, customer_id
    )

    return {
        "success": True,
        "data": SessionMessagesResponse(
            session_id=str(conv_session.id),
            title=conv_session.title,
            messages=[
                MessageItem(
                    id=str(msg.id),
                    role=msg.role,
                    content=msg.content,
                    created_at=(
                        msg.created_at.isoformat() if msg.created_at else ""
                    ),
                    tool_calls=msg.tool_calls,
                )
                for msg in messages
            ],
        ).model_dump(),
        "error": None,
    }


@chat_router.post("/sessions", status_code=status.HTTP_201_CREATED)
async def create_session(
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
) -> dict:
    """Create a new active session for the authenticated customer.

    Any currently active session is automatically closed before the new
    session is created.  The ``customer_id`` is derived from the JWT, not
    from the request body.
    """
    customer_id = current_user["customer_id"]
    new_session = await _memory.create_new_session(session, customer_id)

    return {
        "success": True,
        "data": CreateSessionResponse(
            session_id=str(new_session.id),
            title=new_session.title,
            started_at=(
                new_session.started_at.isoformat()
                if new_session.started_at
                else ""
            ),
        ).model_dump(),
        "error": None,
    }
