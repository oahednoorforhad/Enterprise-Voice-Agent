"""Async query functions for the Knowledge tool family.

These functions search the vector-store-backed ``documentation`` and
``policies`` collections and return typed ``KnowledgeResult`` lists.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.retrieval.vector_store import VectorStore
from app.tools.knowledge.embedding_client import get_embedding
from app.tools.knowledge.models import KnowledgeResult


async def search_documentation(session: AsyncSession, query: str) -> list[KnowledgeResult]:
    """Search the ``documentation`` collection using vector similarity.

    Parameters
    ----------
    session:
        An active async database session.
    query:
        Natural-language query string to embed and search with.

    Returns
    -------
    list[KnowledgeResult]
        Up to 5 top-ranked results from the documentation collection.
    """
    query_embedding = await get_embedding(query)
    store = VectorStore()
    results = await store.search(
        collection="documentation",
        query_embedding=query_embedding,
        top_k=5,
    )
    return [
        KnowledgeResult(
            id=UUID(r.id),
            content=r.content,
            metadata=r.metadata,
            similarity_score=r.score,
        )
        for r in results
    ]


async def search_policies(session: AsyncSession, query: str) -> list[KnowledgeResult]:
    """Search the ``policies`` collection using vector similarity.

    Parameters
    ----------
    session:
        An active async database session.
    query:
        Natural-language query string to embed and search with.

    Returns
    -------
    list[KnowledgeResult]
        Up to 5 top-ranked results from the policies collection.
    """
    query_embedding = await get_embedding(query)
    store = VectorStore()
    results = await store.search(
        collection="policies",
        query_embedding=query_embedding,
        top_k=5,
    )
    return [
        KnowledgeResult(
            id=UUID(r.id),
            content=r.content,
            metadata=r.metadata,
            similarity_score=r.score,
        )
        for r in results
    ]
