"""Clear all data from the EVA database without re-seeding.

Truncates every table in dependency order (children first) including
knowledge_documents (vector store).  Schema and indexes are preserved.

Usage::

    uv run python -m scripts.clear_db
"""

import asyncio
from sqlalchemy import text
from app.db.session import get_session_factory

# Child tables first, then parent tables, then standalone tables.
TRUNCATE_ORDER = [
    "conversation_messages",
    "billing_records",
    "support_tickets",
    "usage_analytics",
    "crm_notes",
    "conversation_sessions",
    "subscriptions",
    "customers",
    "knowledge_documents",
]


async def main() -> None:
    factory = get_session_factory()
    async with factory() as session:
        print("Clearing EVA database...")
        for table in TRUNCATE_ORDER:
            await session.execute(text(f'TRUNCATE TABLE "{table}" CASCADE'))
            print(f"  [ok] {table}")
        await session.commit()
    print("\nDone. All synthetic data removed. Schema intact.")


if __name__ == "__main__":
    asyncio.run(main())
