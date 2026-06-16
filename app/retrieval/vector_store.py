"""PGVector-based vector store backed by the ``knowledge_documents`` table.

All queries use raw ``sqlalchemy.text()`` — no ORM query API.
"""

import json

from sqlalchemy import text

from app.db.session import get_session_factory
from app.schemas.vector import SearchResult, VectorItem


class VectorStore:
    """Async vector store for upserting and searching knowledge document embeddings."""

    def __init__(self, session_factory=None):
        self._session_factory = session_factory or get_session_factory()

    async def upsert(self, items: list[VectorItem]) -> int:
        """Bulk insert or update documents. Returns number of rows affected."""
        if not items:
            return 0

        # Build a single multi-row INSERT with parameterised values
        value_rows: list[str] = []
        params: dict = {}
        for i, item in enumerate(items):
            value_rows.append(
                f"(CAST(:id_{i} AS uuid), :collection_{i}, :title_{i}, "
                f":content_{i}, CAST(:source_ref_{i} AS text), "
                f"CAST(:metadata_{i} AS jsonb), CAST(:embedding_{i} AS vector))"
            )
            params[f"id_{i}"] = item.id
            params[f"collection_{i}"] = item.collection
            params[f"title_{i}"] = item.title
            params[f"content_{i}"] = item.content
            params[f"source_ref_{i}"] = item.source_ref
            params[f"metadata_{i}"] = json.dumps(item.metadata)
            params[f"embedding_{i}"] = item.embedding

        sql = f"""
            INSERT INTO knowledge_documents
                (id, collection, title, content, source_ref, metadata, embedding)
            VALUES
                {', '.join(value_rows)}
            ON CONFLICT (id) DO UPDATE SET
                title      = EXCLUDED.title,
                content    = EXCLUDED.content,
                source_ref = EXCLUDED.source_ref,
                metadata   = EXCLUDED.metadata,
                embedding  = EXCLUDED.embedding,
                updated_at = now()
        """

        async with self._session_factory() as session:
            result = await session.execute(text(sql), params)
            await session.commit()
        return result.rowcount

    async def search(
        self,
        collection: str,
        query_embedding: list[float],
        top_k: int = 5,
    ) -> list[SearchResult]:
        """Cosine-similarity search over ``collection``.

        Returns *top_k* results ranked by ``1 - cosine_distance``.
        """
        sql = text("""
            SELECT
                id,
                collection,
                title,
                content,
                COALESCE(source_ref, '')  AS source_ref,
                COALESCE(metadata, '{}')  AS metadata,
                1 - (embedding <=> CAST(:q AS vector)) AS score
            FROM knowledge_documents
            WHERE collection = :collection
            ORDER BY embedding <=> CAST(:q AS vector)
            LIMIT :k
        """)

        async with self._session_factory() as session:
            rows = await session.execute(
                sql,
                {
                    "q": query_embedding,
                    "collection": collection,
                    "k": top_k,
                },
            )
            raw = rows.fetchall()

        return [
            SearchResult(
                id=str(r.id),
                collection=r.collection,
                title=r.title,
                content=r.content,
                source_ref=r.source_ref if r.source_ref is not None else "",
                metadata=r.metadata if r.metadata is not None else {},
                score=float(r.score),
            )
            for r in raw
        ]

    async def delete(self, collection: str, ids: list[str]) -> int:
        """Delete documents by id within *collection*. Returns rows deleted."""
        if not ids:
            return 0

        placeholders = ", ".join([f":id_{i}" for i in range(len(ids))])
        params: dict = {f"id_{i}": id_ for i, id_ in enumerate(ids)}
        params["collection"] = collection

        sql = text(
            f"DELETE FROM knowledge_documents "
            f"WHERE id IN ({placeholders}) AND collection = :collection"
        )

        async with self._session_factory() as session:
            result = await session.execute(sql, params)
            await session.commit()
        return result.rowcount

    async def count(self, collection: str) -> int:
        """Return the number of documents in *collection*."""
        sql = text("SELECT COUNT(*) FROM knowledge_documents WHERE collection = :c")

        async with self._session_factory() as session:
            result = await session.execute(sql, {"c": collection})
        return result.scalar_one()

    async def truncate(self, collection: str) -> None:
        """Delete **all** documents in *collection* (not a DROP TABLE)."""
        sql = text("DELETE FROM knowledge_documents WHERE collection = :c")

        async with self._session_factory() as session:
            await session.execute(sql, {"c": collection})
            await session.commit()
