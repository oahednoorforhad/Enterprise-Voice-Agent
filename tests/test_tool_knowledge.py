"""Tests for the Knowledge tool family.

Mocking
-------
``get_embedding`` is patched so no real HTTP calls to OpenRouter are made.
"""

import uuid
from unittest.mock import patch

import pytest

from app.retrieval.vector_store import VectorStore
from app.schemas.vector import VectorItem
from app.tools.knowledge.functions import search_documentation, search_policies
from app.tools.knowledge.models import KnowledgeResult

pytestmark = pytest.mark.asyncio

# A 768-dimensional dummy embedding that every patched call returns.
# Since pgvector's <=> operator computes cosine distance (1 − cosine similarity),
# comparing identical embeddings yields similarity_score ≈ 1.0.
DUMMY_EMBEDDING = [0.1] * 768


# ── helpers ─────────────────────────────────────────────────────────────


def _make_item(embedding: list[float], collection: str, **kw) -> VectorItem:
    """Build a ``VectorItem`` with a random UUID."""
    return VectorItem(
        id=str(uuid.uuid4()),
        collection=collection,
        title=kw.get("title", "test doc"),
        content=kw.get("content", "test content"),
        source_ref=kw.get("source_ref", ""),
        metadata=kw.get("metadata", {}),
        embedding=embedding,
    )


# ── TestSearchDocumentation ─────────────────────────────────────────────


class TestSearchDocumentation:
    """Tests for ``search_documentation``."""

    async def test_returns_knowledge_result_instances(self, async_session) -> None:
        """Insert a doc into ``documentation`` and verify the function
        returns a ``KnowledgeResult`` with correct fields."""
        store = VectorStore()
        item = _make_item(
            DUMMY_EMBEDDING,
            "documentation",
            content="API reference for billing endpoints",
        )
        await store.upsert([item])

        with patch("app.tools.knowledge.functions.get_embedding") as mock_embed:
            mock_embed.return_value = DUMMY_EMBEDDING
            results = await search_documentation(async_session, "billing API")

        assert len(results) >= 1
        for r in results:
            assert isinstance(r, KnowledgeResult), "Expected KnowledgeResult instances"
            assert isinstance(r.id, uuid.UUID), "id should be a UUID object"
            assert r.content == "API reference for billing endpoints"
            assert r.similarity_score > 0.99

        # Clean up
        await store.truncate("documentation")

    async def test_returns_empty_when_collection_empty(self, async_session) -> None:
        """Searching an empty collection should return an empty list."""
        store = VectorStore()
        # Insert into a different collection
        item = _make_item(DUMMY_EMBEDDING, "policies", content="Some policy")
        await store.upsert([item])

        with patch("app.tools.knowledge.functions.get_embedding") as mock_embed:
            mock_embed.return_value = DUMMY_EMBEDDING
            results = await search_documentation(async_session, "anything")

        assert results == []

        await store.truncate("policies")

    async def test_returns_multiple_results(self, async_session) -> None:
        """Insert two documents and verify both are returned."""
        store = VectorStore()
        items = [
            _make_item(DUMMY_EMBEDDING, "documentation", content="Doc A"),
            _make_item(DUMMY_EMBEDDING, "documentation", content="Doc B"),
        ]
        await store.upsert(items)

        with patch("app.tools.knowledge.functions.get_embedding") as mock_embed:
            mock_embed.return_value = DUMMY_EMBEDDING
            results = await search_documentation(async_session, "test")

        assert len(results) == 2
        contents = {r.content for r in results}
        assert "Doc A" in contents
        assert "Doc B" in contents

        await store.truncate("documentation")


# ── TestSearchPolicies ──────────────────────────────────────────────────


class TestSearchPolicies:
    """Tests for ``search_policies``."""

    async def test_returns_knowledge_result_instances(self, async_session) -> None:
        """Insert a doc into ``policies`` and verify the function
        returns a ``KnowledgeResult`` with correct fields."""
        store = VectorStore()
        item = _make_item(
            DUMMY_EMBEDDING,
            "policies",
            content="Standard return policy (30 days)",
        )
        await store.upsert([item])

        with patch("app.tools.knowledge.functions.get_embedding") as mock_embed:
            mock_embed.return_value = DUMMY_EMBEDDING
            results = await search_policies(async_session, "return policy")

        assert len(results) >= 1
        for r in results:
            assert isinstance(r, KnowledgeResult), "Expected KnowledgeResult instances"
            assert isinstance(r.id, uuid.UUID), "id should be a UUID object"
            assert r.content == "Standard return policy (30 days)"
            assert r.similarity_score > 0.99

        await store.truncate("policies")

    async def test_returns_empty_when_collection_empty(self, async_session) -> None:
        """Searching an empty collection should return an empty list."""
        store = VectorStore()
        item = _make_item(DUMMY_EMBEDDING, "documentation", content="Some docs")
        await store.upsert([item])

        with patch("app.tools.knowledge.functions.get_embedding") as mock_embed:
            mock_embed.return_value = DUMMY_EMBEDDING
            results = await search_policies(async_session, "anything")

        assert results == []

        await store.truncate("documentation")

    async def test_returns_multiple_results(self, async_session) -> None:
        """Insert two policies and verify both are returned."""
        store = VectorStore()
        items = [
            _make_item(DUMMY_EMBEDDING, "policies", content="Policy X"),
            _make_item(DUMMY_EMBEDDING, "policies", content="Policy Y"),
        ]
        await store.upsert(items)

        with patch("app.tools.knowledge.functions.get_embedding") as mock_embed:
            mock_embed.return_value = DUMMY_EMBEDDING
            results = await search_policies(async_session, "policy")

        assert len(results) == 2
        contents = {r.content for r in results}
        assert "Policy X" in contents
        assert "Policy Y" in contents

        await store.truncate("policies")
