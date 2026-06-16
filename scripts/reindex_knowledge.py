"""Re-embed all KnowledgeDocument rows using the OpenRouter embedding API.

Usage:
    uv run python -m scripts.reindex_knowledge

Requires OPENROUTER_API_KEY to be set in .env or environment.
Skips gracefully if the key is empty.
"""

import asyncio
import logging

import pgvector.asyncpg
from sqlalchemy import select

from app.config.settings import get_settings
from app.db.models import KnowledgeDocument
from app.db.session import get_engine, get_session_factory
from app.tools.knowledge.embedding_client import get_embedding

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
)


async def main() -> None:
    settings = get_settings()

    if not settings.openrouter_api_key:
        logger.warning("OPENROUTER_API_KEY not set, skipping re-index.")
        return

    engine = get_engine()

    # Register pgvector type codecs so the Vector column is usable
    async with engine.connect() as conn:
        await conn.run_sync(
            lambda raw_conn: pgvector.asyncpg.register_vector(raw_conn)
        )

    factory = get_session_factory()
    async with factory() as session:
        result = await session.execute(
            select(KnowledgeDocument).order_by(KnowledgeDocument.created_at)
        )
        docs = result.scalars().all()

        if not docs:
            logger.info("No knowledge documents found to re-index.")
            return

        total = len(docs)
        logger.info("Re-indexing %d knowledge documents …", total)

        for idx, doc in enumerate(docs, start=1):
            embedding = await get_embedding(doc.content)
            doc.embedding = embedding

            if idx % 10 == 0 or idx == total:
                logger.info("  Progress: %d / %d", idx, total)

        await session.commit()
        logger.info("Successfully re-indexed %d knowledge documents.", total)


if __name__ == "__main__":
    asyncio.run(main())
