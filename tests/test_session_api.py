"""Integration tests for session management endpoints.

Covers listing sessions, fetching session messages, creating sessions,
and streaming chat with ``session_id`` resolution.

Uses a real PostgreSQL database (via ``setup_db`` session-scoped fixture)
and does **not** mock ``DbConversationStore`` — every test exercises the
real ``_memory`` methods against the test container.

Mock auth is active by default (``MOCK_AUTH_ENABLED=true`` in settings),
so no auth header is required — the hard-coded mock user
``{"customer_id": "mock_001", …}`` is used automatically.
"""

import asyncio
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_current_user, get_llm_client
from app.schemas.reasoning import ChatResponse, EvidencePackage, ReasoningOutput

# ── Helpers ───────────────────────────────────────────────────────────────


def _parse_sse_events(response_text: str) -> list[dict]:
    """Parse SSE ``text/event-stream`` into a list of JSON dicts."""
    events: list[dict] = []
    for block in response_text.strip().split("\n\n"):
        block = block.strip()
        if not block:
            continue
        for line in block.split("\n"):
            if line.startswith("data: "):
                events.append(json.loads(line[6:]))
    return events


# ── Fixtures ──────────────────────────────────────────────────────────────


MOCK_CUSTOMER_UUID = "00000000-0000-0000-0000-000000000001"
OTHER_CUSTOMER_UUID = "00000000-0000-0000-0000-000000000002"
EMPTY_CUSTOMER_UUID = "00000000-0000-0000-0000-ffffffffffff"


@pytest.fixture(autouse=True)
def _seed_test_customers(setup_db):
    """Insert the mock customers that session tests depend on.

    The ``conversation_sessions`` table has a foreign key to ``customers``,
    so a matching row must exist before any session can be created.
    Runs once before each test and cleans up after.
    """
    from app.db.models import Customer
    from app.db.session import get_session_factory

    async def _seed():
        factory = get_session_factory()
        async with factory() as session:
            for cid, name in [
                (MOCK_CUSTOMER_UUID, "Mock User"),
                (OTHER_CUSTOMER_UUID, "Other User"),
                (EMPTY_CUSTOMER_UUID, "Empty User"),
            ]:
                stmt = select(Customer).where(Customer.id == uuid.UUID(cid))
                result = await session.execute(stmt)
                if result.scalar_one_or_none() is None:
                    session.add(
                        Customer(
                            id=uuid.UUID(cid),
                            name=name,
                            email=f"{name.lower().replace(' ', '_')}@test.com",
                        )
                    )
            await session.commit()

    asyncio.run(_seed())
    yield
    # No explicit cleanup — the testcontainer is throw-away per session.



def _fake_chat_response() -> ChatResponse:
    """Construct a ``ChatResponse`` for mocking the orchestrator.

    Matches the shape used in ``test_chat_api.py`` so the chat endpoint
    can serialise the result and ``_memory.add_turn`` receives a real
    assistant response string.
    """
    return ChatResponse(
        response="Test answer from session test.",
        evidence=EvidencePackage(items=[], failed_tools=[], total_sources=0),
        reasoning_trace=ReasoningOutput(
            conclusion="Test answer from session test.",
            evidence_cited=[],
            reasoning_type="evidence_corroboration",
            confidence=0.85,
        ),
        tool_calls_made=[],
    )


async def _mock_stream_events(*_args: object, **_kwargs: object):
    """Minimal async generator that simulates ``process_turn_streaming``."""
    yield {"stage": "thinking", "label": "Thinking\u2026"}
    yield {"stage": "intent", "label": "Processing\u2026", "intent": "greeting"}
    yield {"stage": "reasoning"}
    yield {
        "stage": "done",
        "response": "Mock stream answer.",
        "tool_calls_made": [],
        "evidence": None,
        "reasoning_trace": None,
    }


@pytest.fixture
def client(setup_db) -> TestClient:
    """Return a ``TestClient`` wired to the real test database.

    The ``setup_db`` session-scoped fixture (defined in ``conftest.py``)
    has already overridden ``DATABASE_URL`` to point at the testcontainer
    Postgres and run Alembic migrations, so the real ``get_db_session``
    dependency connects to the test DB.

    ``get_llm_client`` is overridden with an ``AsyncMock`` so endpoints
    that depend on it (``/chat/`` and ``/chat/stream``) don't require a
    real Google API key.

    ``get_current_user`` is overridden with the standard mock user
    so tests don't depend on ``MOCK_AUTH_ENABLED`` being ``true``.
    """
    from app.main import app

    app.dependency_overrides[get_llm_client] = lambda: AsyncMock()
    app.dependency_overrides[get_current_user] = lambda: {
        "customer_id": "00000000-0000-0000-0000-000000000001",
        "name": "Mock User",
        "email": "mock@clouddesk.com",
    }
    yield TestClient(app)
    app.dependency_overrides.clear()


# ── Test: GET /api/v1/chat/sessions ──────────────────────────────────────


class TestListSessions:
    """``GET /api/v1/chat/sessions`` — list sessions for the customer."""

    @patch("app.api.chat_router.OrchestratorService")
    def test_list_sessions_success(
        self,
        mock_orch_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """POST a chat message, GET sessions — session appears in the list."""
        mock_instance = mock_orch_cls.return_value
        mock_instance.process_turn = AsyncMock(
            return_value=_fake_chat_response()
        )

        # Create a session + messages via the normal chat endpoint
        client.post(
            "/api/v1/chat/",
            json={
                "message": "Hello",
                "customer_id": "00000000-0000-0000-0000-000000000001",
            },
        )

        # ── List sessions ────────────────────────────────────────────
        response = client.get("/api/v1/chat/sessions")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        data = body["data"]
        assert data["total"] >= 1
        assert len(data["sessions"]) == data["total"]

        # At least one session has a title (set by _memory.add_turn)
        titled = [s for s in data["sessions"] if s["title"] is not None]
        assert len(titled) >= 1

    def test_list_sessions_empty(self, client: TestClient) -> None:
        """Customer with **no** sessions returns ``sessions: [], total: 0``."""
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: {
            "customer_id": "00000000-0000-0000-0000-ffffffffffff",
            "name": "Empty User",
            "email": "empty@test.com",
        }

        response = client.get("/api/v1/chat/sessions")
        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True

        data = body["data"]
        assert data["sessions"] == []
        assert data["total"] == 0


# ── Test: GET /api/v1/chat/sessions/{id}/messages ────────────────────────


class TestGetSessionMessages:
    """``GET /api/v1/chat/sessions/{id}/messages``."""

    @patch("app.api.chat_router.OrchestratorService")
    def test_get_session_messages_success(
        self,
        mock_orch_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """POST a chat message, then GET messages — both turns are returned."""
        mock_instance = mock_orch_cls.return_value
        mock_instance.process_turn = AsyncMock(
            return_value=_fake_chat_response()
        )

        # Create a session + messages
        client.post(
            "/api/v1/chat/",
            json={
                "message": "Hello",
                "customer_id": "00000000-0000-0000-0000-000000000001",
            },
        )

        # Discover the session_id from the listing
        list_resp = client.get("/api/v1/chat/sessions")
        sessions = list_resp.json()["data"]["sessions"]
        assert len(sessions) >= 1
        session_id: str = sessions[0]["session_id"]

        # ── Fetch messages ───────────────────────────────────────────
        msg_resp = client.get(
            f"/api/v1/chat/sessions/{session_id}/messages"
        )
        assert msg_resp.status_code == 200
        body = msg_resp.json()
        assert body["success"] is True

        data = body["data"]
        assert data["session_id"] == session_id
        assert len(data["messages"]) >= 2  # user + assistant

        roles = [m["role"] for m in data["messages"]]
        assert "user" in roles
        assert "assistant" in roles

    @patch("app.api.chat_router.OrchestratorService")
    def test_get_session_messages_404_wrong_customer(
        self,
        mock_orch_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """Trying to fetch another customer's session returns 404."""
        mock_instance = mock_orch_cls.return_value
        mock_instance.process_turn = AsyncMock(
            return_value=_fake_chat_response()
        )

        # Create a session as mock_001
        client.post(
            "/api/v1/chat/",
            json={
                "message": "Hello",
                "customer_id": "00000000-0000-0000-0000-000000000001",
            },
        )
        list_resp = client.get("/api/v1/chat/sessions")
        session_id: str = list_resp.json()["data"]["sessions"][0][
            "session_id"
        ]

        # ── Switch to a different customer ───────────────────────────
        from app.main import app

        app.dependency_overrides[get_current_user] = lambda: {
            "customer_id": "00000000-0000-0000-0000-000000000002",
            "name": "Other User",
            "email": "other@test.com",
        }

        msg_resp = client.get(
            f"/api/v1/chat/sessions/{session_id}/messages"
        )
        assert msg_resp.status_code == 404
        body = msg_resp.json()
        assert body["success"] is False
        assert body["error"] == "Session not found"

    def test_get_session_messages_404_nonexistent(
        self,
        client: TestClient,
    ) -> None:
        """GET messages with a random UUID returns 404."""
        fake_id = "00000000-0000-0000-0000-000000000999"
        msg_resp = client.get(
            f"/api/v1/chat/sessions/{fake_id}/messages"
        )
        assert msg_resp.status_code == 404
        body = msg_resp.json()
        assert body["success"] is False
        assert body["error"] == "Session not found"


# ── Test: POST /api/v1/chat/sessions ─────────────────────────────────────


class TestCreateSession:
    """``POST /api/v1/chat/sessions`` — create a new session."""

    def test_create_session_201(self, client: TestClient) -> None:
        """POST /sessions returns 201 with a valid UUID and a started_at."""
        response = client.post("/api/v1/chat/sessions")
        assert response.status_code == 201
        body = response.json()
        assert body["success"] is True

        data = body["data"]
        assert "session_id" in data
        # Validate that session_id is a well-formed UUID
        parsed = uuid.UUID(data["session_id"])
        assert str(parsed) == data["session_id"]
        assert data["title"] is None
        assert data["started_at"] != ""

    def test_create_session_closes_old(self, client: TestClient) -> None:
        """POST /sessions twice — the first session is closed."""
        # ── First session ────────────────────────────────────────────
        resp1 = client.post("/api/v1/chat/sessions")
        assert resp1.status_code == 201
        session_id_1: str = resp1.json()["data"]["session_id"]

        # ── Second session (closes the first) ────────────────────────
        resp2 = client.post("/api/v1/chat/sessions")
        assert resp2.status_code == 201
        session_id_2: str = resp2.json()["data"]["session_id"]
        assert session_id_2 != session_id_1

        # ── Both sessions appear in the listing ──────────────────────
        list_resp = client.get("/api/v1/chat/sessions")
        sessions = list_resp.json()["data"]["sessions"]
        session_ids = [s["session_id"] for s in sessions]

        assert session_id_1 in session_ids
        assert session_id_2 in session_ids

        # First session is closed (ended_at is set)
        s1 = next(s for s in sessions if s["session_id"] == session_id_1)
        assert s1["ended_at"] is not None

        # Second session is still active (ended_at is None)
        s2 = next(s for s in sessions if s["session_id"] == session_id_2)
        assert s2["ended_at"] is None


# ── Test: POST /api/v1/chat/stream with session_id ───────────────────────


class TestChatStreamWithSession:
    """``POST /api/v1/chat/stream`` — session resolution behaviour."""

    @patch("app.api.chat_router.OrchestratorService")
    def test_chat_stream_with_session_id(
        self,
        mock_orch_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """Stream with a valid ``session_id`` — first SSE event contains it."""
        mock_instance = mock_orch_cls.return_value
        mock_instance.process_turn_streaming = _mock_stream_events

        # Create a session first
        create_resp = client.post("/api/v1/chat/sessions")
        session_id: str = create_resp.json()["data"]["session_id"]

        # ── Stream with that session_id ──────────────────────────────
        stream_resp = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Hello",
                "customer_id": "00000000-0000-0000-0000-000000000001",
                "session_id": session_id,
            },
        )
        assert stream_resp.status_code == 200

        events = _parse_sse_events(stream_resp.text)
        assert len(events) >= 1

        # The very first SSE event is the session event
        assert events[0]["stage"] == "session"
        assert events[0]["session_id"] == session_id

    @patch("app.api.chat_router.OrchestratorService")
    def test_chat_stream_without_session_id_backward_compat(
        self,
        mock_orch_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """Stream **without** ``session_id`` — works and gets an auto-created session."""
        mock_instance = mock_orch_cls.return_value
        mock_instance.process_turn_streaming = _mock_stream_events

        # ── Stream without session_id ────────────────────────────────
        stream_resp = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Hello",
                "customer_id": "00000000-0000-0000-0000-000000000001",
            },
        )
        assert stream_resp.status_code == 200

        events = _parse_sse_events(stream_resp.text)
        assert len(events) >= 1
        assert events[0]["stage"] == "session"
        assert "session_id" in events[0]

    @patch("app.api.chat_router.OrchestratorService")
    def test_chat_stream_invalid_session_id(
        self,
        mock_orch_cls: MagicMock,
        client: TestClient,
    ) -> None:
        """Stream with a nonexistent UUID — first SSE event is an error."""
        mock_instance = mock_orch_cls.return_value
        mock_instance.process_turn_streaming = _mock_stream_events

        fake_id = "00000000-0000-0000-0000-000000000999"

        # ── Stream with invalid session_id ───────────────────────────
        stream_resp = client.post(
            "/api/v1/chat/stream",
            json={
                "message": "Hello",
                "customer_id": "00000000-0000-0000-0000-000000000001",
                "session_id": fake_id,
            },
        )
        assert stream_resp.status_code == 200

        events = _parse_sse_events(stream_resp.text)
        assert len(events) >= 1
        assert events[0]["stage"] == "error"
        assert events[0]["message"] == "Session not found"
