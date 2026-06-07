"""add_hnsw_index

Revision ID: c943d03cdec9
Revises: 98a66ecf9801
Create Date: 2026-06-07 01:42:15.960475

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c943d03cdec9'
down_revision: Union[str, Sequence[str], None] = '98a66ecf9801'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create HNSW index on knowledge_documents.embedding with CONCURRENTLY.

    Uses Alembic's autocommit_block() context manager to run the CREATE
    INDEX CONCURRENTLY outside the outer migration transaction.
    CONCURRENTLY cannot run inside a transaction block, and the index
    is immediately ready for concurrent INSERT/UPDATE traffic.
    """
    with op.get_context().autocommit_block():
        op.execute(
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS ix_knowledge_documents_embedding_hnsw "
            "ON knowledge_documents USING hnsw (embedding vector_cosine_ops) "
            "WITH (m = 16, ef_construction = 64)"
        )


def downgrade() -> None:
    """Drop the HNSW index. Safe to run in a transaction."""
    op.execute("DROP INDEX IF EXISTS ix_knowledge_documents_embedding_hnsw")
