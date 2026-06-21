"""Chat router — single-turn text entrypoint for the Sprint 3 reasoning engine.

Mounted at ``/api/v1/chat``.  Accepts a plain-text message plus customer
identifier and returns a structured ``ChatResponse`` from the orchestrator.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_llm_client
from app.core.llm_client import LLMClient
from app.db import get_db_session, get_session_factory
from app.memory import DbConversationStore
from app.orchestrator.service import OrchestratorService
from app.schemas.reasoning import ChatRequest, ChatResponse

chat_router = APIRouter(prefix="/api/v1/chat", tags=["Chat"])

# PostgreSQL-backed conversation store — survives server restarts.
_memory = DbConversationStore()


@chat_router.post("/", response_model=ChatResponse)
async def chat(
    request: ChatRequest,
    session: AsyncSession = Depends(get_db_session),
    current_user: dict = Depends(get_current_user),
    llm: LLMClient = Depends(get_llm_client),
) -> ChatResponse:
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

    return result
