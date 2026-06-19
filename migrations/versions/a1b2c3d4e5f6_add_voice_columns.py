"""add voice columns to conversation_sessions

Revision ID: a1b2c3d4e5f6
Revises: c943d03cdec9
Create Date: 2026-06-17 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, Sequence[str], None] = "c943d03cdec9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add voice_session_id and audio_duration_seconds to conversation_sessions.

    Both columns are nullable so existing rows are unaffected.
    """
    op.add_column(
        "conversation_sessions",
        sa.Column("voice_session_id", sa.String(500), nullable=True),
    )
    op.add_column(
        "conversation_sessions",
        sa.Column("audio_duration_seconds", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    """Remove the voice columns."""
    op.drop_column("conversation_sessions", "audio_duration_seconds")
    op.drop_column("conversation_sessions", "voice_session_id")
