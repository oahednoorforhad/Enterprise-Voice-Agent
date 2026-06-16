"""Integration tests for the Knowledge API endpoints.

These tests verify that the HTTP layer correctly invokes the underlying
``search_documentation`` / ``search_policies`` functions and returns a
well-formed ``ToolResult`` JSON body.

Mocking
-------
Both knowledge functions are patched with ``AsyncMock`` so that no real
OpenRouter embedding calls or vector-store queries are made during tests.
"""

import uuid
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.tools.knowledge.models import KnowledgeResult

# ── Helpers ─────────────────────────────────────────────────────────────

KNOWLEDGE_BASE = "/api/v1/tools/knowledge"


def _make_dummy_result(
    content: str = "test content",
    score: float = 0.95,
    result_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001"),
) -> KnowledgeResult:
    """Build a ``KnowledgeResult`` with deterministic fields."""
    return KnowledgeResult(
        id=result_id,
        content=content,
        metadata={"source": "test"},
        similarity_score=score,
    )


# ── Tests ───────────────────────────────────────────────────────────────


class TestSearchDocumentationEndpoint:
    """POST /knowledge/documentation"""

    def test_returns_200_with_toolresult(self) -> None:
        """Happy path — returns success=True with result data."""
        dummy = [_make_dummy_result(content="API reference for billing")]

        with patch(
            "app.api.tools_knowledge.search_documentation",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = dummy
            client = TestClient(app)
            response = client.post(
                f"{KNOWLEDGE_BASE}/documentation",
                json={"query": "billing API"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["error"] is None
        assert body["data"] is not None
        assert len(body["data"]) == 1
        assert body["data"][0]["content"] == "API reference for billing"
        assert body["data"][0]["id"] == "00000000-0000-0000-0000-000000000001"

        mock_search.assert_awaited_once()

    def test_returns_empty_list_when_no_results(self) -> None:
        """Empty search results yield success=True with empty data array."""
        with patch(
            "app.api.tools_knowledge.search_documentation",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = []
            client = TestClient(app)
            response = client.post(
                f"{KNOWLEDGE_BASE}/documentation",
                json={"query": "nothing"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == []
        assert body["error"] is None

        mock_search.assert_awaited_once()

    def test_multiple_results(self) -> None:
        """Multiple results are all returned in the data array."""
        dummy = [
            _make_dummy_result(content="Doc A", score=0.95),
            _make_dummy_result(
                result_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                content="Doc B",
                score=0.90,
            ),
        ]

        with patch(
            "app.api.tools_knowledge.search_documentation",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = dummy
            client = TestClient(app)
            response = client.post(
                f"{KNOWLEDGE_BASE}/documentation",
                json={"query": "multiple docs"},
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 2
        contents = {item["content"] for item in body["data"]}
        assert "Doc A" in contents
        assert "Doc B" in contents


class TestSearchPoliciesEndpoint:
    """POST /knowledge/policies"""

    def test_returns_200_with_toolresult(self) -> None:
        """Happy path — returns success=True with result data."""
        dummy = [_make_dummy_result(content="Standard return policy (30 days)")]

        with patch(
            "app.api.tools_knowledge.search_policies",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = dummy
            client = TestClient(app)
            response = client.post(
                f"{KNOWLEDGE_BASE}/policies",
                json={"query": "return policy"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["error"] is None
        assert body["data"] is not None
        assert len(body["data"]) == 1
        assert body["data"][0]["content"] == "Standard return policy (30 days)"
        assert body["data"][0]["id"] == "00000000-0000-0000-0000-000000000001"

        mock_search.assert_awaited_once()

    def test_returns_empty_list_when_no_results(self) -> None:
        """Empty search results yield success=True with empty data array."""
        with patch(
            "app.api.tools_knowledge.search_policies",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = []
            client = TestClient(app)
            response = client.post(
                f"{KNOWLEDGE_BASE}/policies",
                json={"query": "unknown policy"},
            )

        assert response.status_code == 200
        body = response.json()
        assert body["success"] is True
        assert body["data"] == []
        assert body["error"] is None

        mock_search.assert_awaited_once()

    def test_multiple_results(self) -> None:
        """Multiple results are all returned in the data array."""
        dummy = [
            _make_dummy_result(content="Policy X", score=0.95),
            _make_dummy_result(
                result_id=uuid.UUID("00000000-0000-0000-0000-000000000002"),
                content="Policy Y",
                score=0.90,
            ),
        ]

        with patch(
            "app.api.tools_knowledge.search_policies",
            new_callable=AsyncMock,
        ) as mock_search:
            mock_search.return_value = dummy
            client = TestClient(app)
            response = client.post(
                f"{KNOWLEDGE_BASE}/policies",
                json={"query": "policy list"},
            )

        assert response.status_code == 200
        body = response.json()
        assert len(body["data"]) == 2
        contents = {item["content"] for item in body["data"]}
        assert "Policy X" in contents
        assert "Policy Y" in contents
