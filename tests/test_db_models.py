"""Tests for the Sprint-1 database schema.

Verifies that all 9 tables exist, the ``knowledge_documents.embedding``
column is typed ``vector(768)``, and the ``TimestampMixin`` columns are
present on a representative model.
"""

import pytest
from sqlalchemy import text

# ── 9 tables defined by the Sprint-1 migration ──────────────────────────
TABLE_NAMES = [
    "customers",
    "subscriptions",
    "billing_records",
    "support_tickets",
    "usage_analytics",
    "crm_notes",
    "conversation_sessions",
    "conversation_messages",
    "knowledge_documents",
]


@pytest.mark.parametrize("table_name", TABLE_NAMES)
async def test_all_9_tables_exist(table_name: str, async_session) -> None:
    """Verify that *table_name* exists in ``information_schema.tables``."""
    result = await async_session.execute(
        text(
            "SELECT EXISTS ("
            "  SELECT 1 FROM information_schema.tables"
            "  WHERE table_name = :t"
            ")"
        ),
        {"t": table_name},
    )
    assert result.scalar() is True, f"Table '{table_name}' does not exist"


async def test_knowledge_document_embedding_column_type(async_session) -> None:
    """Verify ``knowledge_documents.embedding`` is ``vector(768)``.

    pgvector does NOT populate ``character_maximum_length`` in
    ``information_schema.columns``.  The dimension is stored directly in
    ``pg_attribute.atttypmod``.
    """
    result = await async_session.execute(
        text(
            "SELECT a.atttypmod "
            "FROM pg_attribute a "
            "JOIN pg_class c ON c.oid = a.attrelid "
            "WHERE c.relname = 'knowledge_documents' "
            "  AND a.attname = 'embedding'"
        ),
    )
    row = result.fetchone()
    assert row is not None, "embedding column not found in pg_attribute"
    dim = row.atttypmod
    assert dim == 768, f"Expected vector(768), got vector({dim})"


async def test_timestamp_mixin_columns(async_session) -> None:
    """Verify that ``created_at`` and ``updated_at`` exist on ``customers``."""
    result = await async_session.execute(
        text(
            "SELECT column_name, data_type "
            "FROM information_schema.columns "
            "WHERE table_name = 'customers' "
            "  AND column_name IN ('created_at', 'updated_at') "
            "ORDER BY column_name"
        ),
    )
    rows = result.fetchall()
    assert len(rows) == 2, f"Expected 2 timestamp columns, found {len(rows)}"
    assert rows[0].column_name == "created_at"
    assert rows[1].column_name == "updated_at"
    for row in rows:
        assert "timestamp" in row.data_type.lower() or "time zone" in row.data_type.lower(), (
            f"Column '{row.column_name}' has unexpected type '{row.data_type}'"
        )
