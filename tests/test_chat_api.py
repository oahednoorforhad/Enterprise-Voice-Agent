"""API-level tests for the ``POST /api/v1/chat`` endpoint.

Mocks the entire ``OrchestratorService`` at the API layer — the
orchestrator's internal logic is already covered by
``tests/test_orchestrator.py``.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.deps import get_current_user, get_llm_client
from app.db import get_db_session
from app.schemas.reasoning import ChatResponse, EvidencePackage, ReasoningOutput


@pytest.fixture(autouse=True)
def mock_memory() -> None:
    """Patch the module-level ``DbConversationStore`` to avoid real DB calls.

    ``app.api.chat_router._memory`` is a module-level instantiation of
    ``DbConversationStore``.  Without this patch the real ``format_prompt_context``
    and ``add_turn`` methods hit the database, which fails when the session
    dependency is an ``AsyncMock``.
    """
    with patch("app.api.chat_router._memory") as mock_mem:
        mock_mem.format_prompt_context = AsyncMock(return_value="")
        mock_mem.add_turn = AsyncMock()
        yield


@pytest.fixture
def mock_session() -> AsyncMock:
    """Return a mocked async DB session for dependency override."""
    return AsyncMock()


@pytest.fixture
def mock_current_user() -> dict:
    """Return a fake authenticated user dict."""
    return {"customer_id": "mock_001", "name": "Mock User", "email": "mock@clouddesk.com"}


@pytest.fixture
def app_with_overrides(
    mock_session: AsyncMock,
    mock_current_user: dict,
) -> FastAPI:
    """Build the FastAPI app with DB + auth dependencies overridden.

    Uses ``app.dependency_overrides`` so the chat endpoint receives
    the mocked session and user instead of the real ones.
    """
    from app.main import app

    app.dependency_overrides[get_db_session] = lambda: mock_session
    app.dependency_overrides[get_current_user] = lambda: mock_current_user
    app.dependency_overrides[get_llm_client] = lambda: AsyncMock()
    yield app
    app.dependency_overrides.clear()


@pytest.fixture
def client(app_with_overrides: FastAPI) -> TestClient:
    """Return a ``TestClient`` bound to the overridden app."""
    return TestClient(app_with_overrides)


# ── Helper to build a fake ChatResponse ─────────────────────────────────


def _make_fake_chat_response(
    response_text: str = "Test answer.",
    tool_calls: list[str] | None = None,
    with_evidence: bool = True,
) -> ChatResponse:
    """Construct a realistic ``ChatResponse`` for mocking."""
    return ChatResponse(
        response=response_text,
        evidence=(
            EvidencePackage(
                items=[],
                failed_tools=[],
                total_sources=0,
            )
            if with_evidence
            else None
        ),
        reasoning_trace=ReasoningOutput(
            conclusion=response_text,
            evidence_cited=[],
            reasoning_type="evidence_corroboration",
            confidence=0.85,
        ),
        tool_calls_made=tool_calls or [],
    )


# ── Tests ────────────────────────────────────────────────────────────────


class TestChatEndpoint:
    """Tests for ``POST /api/v1/chat``."""

    @patch("app.api.chat_router.OrchestratorService")
    def test_happy_path(
        self,
        mock_orchestrator_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """A valid billing inquiry returns 200 with a structured response."""
        fake_response = _make_fake_chat_response(
            response_text="You were charged twice because...",
            tool_calls=["get_billing_history"],
        )
        mock_instance = mock_orchestrator_cls.return_value
        mock_instance.process_turn = AsyncMock(return_value=fake_response)

        payload = {
            "message": "Why was I charged twice?",
            "customer_id": "550e8400-e29b-41d4-a716-446655440000",
        }
        response = client.post("/api/v1/chat/", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["response"] == "You were charged twice because..."
        assert body["tool_calls_made"] == ["get_billing_history"]
        assert body["evidence"] is not None
        assert body["reasoning_trace"] is not None

    @patch("app.api.chat_router.OrchestratorService")
    def test_greeting_no_tools(
        self,
        mock_orchestrator_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """A greeting returns 200 with no tools called and no evidence."""
        fake_response = _make_fake_chat_response(
            response_text="Hello! How can I help you today?",
            tool_calls=[],
            with_evidence=False,
        )
        mock_instance = mock_orchestrator_cls.return_value
        mock_instance.process_turn = AsyncMock(return_value=fake_response)

        payload = {
            "message": "Hello!",
            "customer_id": "550e8400-e29b-41d4-a716-446655440000",
        }
        response = client.post("/api/v1/chat/", json=payload)

        assert response.status_code == 200
        body = response.json()
        assert body["response"] == "Hello! How can I help you today?"
        assert body["tool_calls_made"] == []
        assert body["evidence"] is None

    @patch("app.api.chat_router.OrchestratorService")
    def test_customer_context_from_jwt(
        self,
        mock_orchestrator_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """The endpoint uses ``current_user["customer_id"]`` (from JWT), ignoring the request body."""
        mock_instance = mock_orchestrator_cls.return_value
        mock_instance.process_turn = AsyncMock(
            return_value=_make_fake_chat_response()
        )

        payload = {
            "message": "What is my balance?",
            "customer_id": "client-supplied-id",  # should be ignored
        }
        client.post("/api/v1/chat/", json=payload)

        # Verify the orchestrator was constructed with the JWT customer_id,
        # NOT the one from the request body.
        call_kwargs = mock_orchestrator_cls.call_args.kwargs
        assert call_kwargs["customer_id"] == "mock_001"
        assert "customer_context" in call_kwargs
        ctx = call_kwargs["customer_context"]
        assert ctx["customer_id"] == "mock_001"
        assert ctx["name"] == "Mock User"
        assert ctx["email"] == "mock@clouddesk.com"

    @patch("app.api.chat_router.OrchestratorService")
    def test_rejects_missing_message(
        self,
        mock_orchestrator_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """Omitting ``message`` returns 422."""
        payload = {"customer_id": "550e8400-e29b-41d4-a716-446655440000"}
        response = client.post("/api/v1/chat/", json=payload)
        assert response.status_code == 422

    @patch("app.api.chat_router.OrchestratorService")
    def test_rejects_missing_customer_id(
        self,
        mock_orchestrator_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """Omitting ``customer_id`` returns 422."""
        payload = {"message": "Hello"}
        response = client.post("/api/v1/chat/", json=payload)
        assert response.status_code == 422

    @patch("app.api.chat_router.OrchestratorService")
    def test_rejects_empty_body(
        self,
        mock_orchestrator_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """An empty JSON body returns 422."""
        response = client.post("/api/v1/chat/", json={})
        assert response.status_code == 422

    @patch("app.api.chat_router.OrchestratorService")
    def test_orchestrator_service_construction(
        self,
        mock_orchestrator_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """Verify the endpoint constructs ``OrchestratorService`` with JWT customer_id."""
        mock_instance = mock_orchestrator_cls.return_value
        mock_instance.process_turn = AsyncMock(
            return_value=_make_fake_chat_response()
        )

        payload = {
            "message": "Check my subscription",
            "customer_id": "550e8400-e29b-41d4-a716-446655440000",
        }
        response = client.post("/api/v1/chat/", json=payload)
        assert response.status_code == 200

        # OrchestratorService was constructed with the JWT user's customer_id
        # (mock_001) rather than the one from the request body.
        mock_orchestrator_cls.assert_called_once()
        call_args = mock_orchestrator_cls.call_args
        assert "customer_id" in call_args.kwargs
        assert call_args.kwargs["customer_id"] == "mock_001"

        mock_instance.process_turn.assert_awaited_once_with(
            payload["message"], conversation_history=""
        )
