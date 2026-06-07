"""Tests for the PGVector-backed VectorStore (``app.retrieval.vector_store``).

Covers upsert+search roundtrip, cosine-distance rank ordering, deletion,
and per-collection counting.
"""

import math
import uuid

from app.retrieval.vector_store import VectorStore
from app.schemas.vector import VectorItem

# ── Helpers ─────────────────────────────────────────────────────────────


def _normalized(values: list[float]) -> list[float]:
    """Return a unit vector of length 768 whose first *len(values)* entries
    are filled with *values* and the rest are zero."""
    vec = [0.0] * 768
    for i, v in enumerate(values):
        if i < 768:
            vec[i] = v
    norm = math.sqrt(sum(v * v for v in vec))
    return [v / norm for v in vec]


def _make_item(embedding: list[float], collection: str, **kw) -> VectorItem:
    """Convenience factory for a ``VectorItem`` with a random UUID."""
    return VectorItem(
        id=str(uuid.uuid4()),
        collection=collection,
        title=kw.get("title", "test doc"),
        content=kw.get("content", "test content"),
        source_ref=kw.get("source_ref", "test_source"),
        metadata=kw.get("metadata", {}),
        embedding=embedding,
    )


async def _count(store: VectorStore, collection: str) -> int:
    """Shortcut to count documents in *collection*."""
    return await store.count(collection)


# ── Tests ───────────────────────────────────────────────────────────────


async def test_upsert_and_search_roundtrip(async_session) -> None:
    """Insert a 768-dim vector, then search for it — expect score > 0.99."""
    store = VectorStore()
    emb = _normalized([0.42, 0.73, 0.91])
    item = _make_item(emb, "documentation")
    await store.upsert([item])

    results = await store.search("documentation", emb, top_k=5)
    assert len(results) >= 1
    assert results[0].score > 0.99, (
        f"Expected score > 0.99, got {results[0].score:.6f}"
    )


async def test_cosine_distance_monotonicity(async_session) -> None:
    """Insert 3 items with increasing cosine distance from a query vector
    and verify they are returned in the correct rank order."""
    store = VectorStore()

    # Query vector (normalised)
    query = _normalized([1.0, 0.0, 0.0])

    # Three items at increasing angular distance from *query*
    items = [
        _make_item(_normalized([1.0, 0.0, 0.0]), "policies", title="exact"),
        _make_item(_normalized([0.9, 0.1, 0.0]), "policies", title="close"),
        _make_item(_normalized([0.5, 0.5, 0.0]), "policies", title="far"),
    ]
    await store.upsert(items)

    results = await store.search("policies", query, top_k=3)
    assert len(results) == 3

    titles = [r.title for r in results]
    assert titles == ["exact", "close", "far"], (
        f"Expected rank ['exact', 'close', 'far'], got {titles}"
    )
    # Sanity: scores strictly decreasing
    for i in range(len(results) - 1):
        assert results[i].score > results[i + 1].score, (
            f"Score not monotonic at index {i}: "
            f"{results[i].score:.6f} <= {results[i + 1].score:.6f}"
        )


async def test_delete_removes_item(async_session) -> None:
    """Upsert an item, confirm it counted, delete it, confirm count drops."""
    store = VectorStore()
    collection = "knowledge_articles"

    before = await _count(store, collection)
    item = _make_item(_normalized([1.0, 0.0]), collection)
    await store.upsert([item])

    after_upsert = await _count(store, collection)
    assert after_upsert == before + 1

    deleted = await store.delete(collection, [item.id])
    assert deleted == 1

    after_delete = await _count(store, collection)
    assert after_delete == before


async def test_count_by_collection(async_session) -> None:
    """Upsert into two collections and verify each has the expected count."""
    store = VectorStore()

    # Use valid collection names from the CHECK constraint
    c_a_before = await _count(store, "troubleshooting_guides")
    c_b_before = await _count(store, "knowledge_articles")

    items_a = [
        _make_item(_normalized([1.0, 0.0]), "troubleshooting_guides")
        for _ in range(3)
    ]
    items_b = [
        _make_item(_normalized([1.0, 0.0]), "knowledge_articles")
        for _ in range(5)
    ]
    await store.upsert(items_a + items_b)

    assert await _count(store, "troubleshooting_guides") == c_a_before + 3
    assert await _count(store, "knowledge_articles") == c_b_before + 5
