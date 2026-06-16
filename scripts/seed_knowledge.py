"""Seed the ``knowledge_documents`` table from markdown files on disk.

Reads every ``.md`` file under ``data/synthetic/docs/{collection}/``,
generates embeddings via the Gemini embedding API, and inserts rows
into the ``knowledge_documents`` table using raw SQL with
``CAST(:embedding AS vector)`` (ORM session.add + pgvector 0.4.2
bind_processor is incompatible with asyncpg's binary codec).

Idempotent — deletes all existing rows in each collection, then re-inserts.
Safe to run repeatedly.

Usage::

    uv run python -m scripts.seed_knowledge
"""

import asyncio
import json
import logging
import re
import uuid
from pathlib import Path

from sqlalchemy import text

from app.db.session import get_session_factory
from app.tools.knowledge.embedding_client import get_embedding

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)s  %(name)s  %(message)s",
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DOCS_ROOT = Path(__file__).resolve().parent.parent / "data" / "synthetic" / "docs"

COLLECTIONS = [
    "documentation",
    "policies",
    "knowledge_articles",
    "troubleshooting_guides",
]

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _parse_title(content: str) -> str:
    """Extract the H1 title from a markdown document.

    Returns the text after the first ``# `` heading, or a fallback if none is found.
    """
    match = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if match:
        return match.group(1).strip()
    return "Untitled Document"


def _discover_docs() -> list[dict]:
    """Walk ``data/synthetic/docs/{collection}/*.md`` and return metadata.

    Returns a list of dicts with keys:
        - collection
        - title
        - content
        - source_ref (relative path from docs root)
    """
    docs: list[dict] = []

    for collection in COLLECTIONS:
        col_dir = DOCS_ROOT / collection
        if not col_dir.is_dir():
            logger.warning("Collection directory not found: %s", col_dir)
            continue

        md_files = sorted(col_dir.glob("*.md"))
        if not md_files:
            logger.warning("No markdown files found in %s", col_dir)
            continue

        for md_path in md_files:
            content = md_path.read_text(encoding="utf-8").strip()
            if not content:
                logger.warning("Skipping empty file: %s", md_path)
                continue

            title = _parse_title(content)
            source_ref = str(md_path.relative_to(DOCS_ROOT).as_posix())

            docs.append({
                "collection": collection,
                "title": title,
                "content": content,
                "source_ref": source_ref,
            })

    return docs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


async def _seed() -> None:
    """Run the seed logic."""
    # -- Discover documents ------------------------------------------------
    docs = _discover_docs()
    if not docs:
        logger.warning("No markdown documents found under %s. Nothing to seed.", DOCS_ROOT)
        return

    logger.info("Discovered %d markdown documents across %d collections.",
                len(docs), len(set(d["collection"] for d in docs)))

    # -- Prepare DB --------------------------------------------------------
    factory = get_session_factory()

    INSERT_SQL = text("""
        INSERT INTO knowledge_documents
            (id, collection, title, content, source_ref, metadata, embedding)
        VALUES
            (:id, :collection, :title, :content, :source_ref,
             CAST(:metadata AS jsonb), CAST(:embedding AS vector))
    """)

    DELETE_SQL = text(
        "DELETE FROM knowledge_documents WHERE collection = :collection"
    )

    COUNT_SQL = text(
        "SELECT COUNT(*) FROM knowledge_documents WHERE collection = :collection"
    )

    async with factory() as session:
        # -- Idempotency: delete existing rows per collection ---------------
        collections_seen = set()
        for doc in docs:
            col = doc["collection"]
            if col not in collections_seen:
                collections_seen.add(col)
                result = await session.execute(DELETE_SQL, {"collection": col})
                logger.info("Deleted %d existing row(s) in collection '%s'.",
                            result.rowcount, col)

        # -- Generate embeddings and insert ---------------------------------
        total = len(docs)
        logger.info("Generating embeddings and inserting %d documents …", total)

        for idx, doc in enumerate(docs, start=1):
            content = doc["content"]
            title = doc["title"]
            collection = doc["collection"]

            # Generate embedding
            embedding = await get_embedding(content)

            await session.execute(
                INSERT_SQL,
                {
                    "id": uuid.uuid4(),
                    "collection": collection,
                    "title": title,
                    "content": content,
                    "source_ref": doc["source_ref"],
                    "metadata": json.dumps({"source": "synthetic"}),
                    "embedding": embedding,      # plain list — CAST handles it
                },
            )

            if idx % 10 == 0 or idx == total:
                logger.info("  Progress: %d / %d  (collection=%s, title=%s)",
                            idx, total, collection, title[:60])

        # -- Commit ---------------------------------------------------------
        await session.commit()
        logger.info("Successfully seeded %d knowledge documents.", total)

        # -- Verify row counts ----------------------------------------------
        logger.info("Final row counts per collection:")
        for col in sorted(COLLECTIONS):
            cnt = (
                await session.execute(COUNT_SQL, {"collection": col})
            ).scalar() or 0
            logger.info("  %s: %d", col, cnt)


def main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(_seed())
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
