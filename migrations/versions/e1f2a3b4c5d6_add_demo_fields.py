"""add demo fields

Revision ID: e1f2a3b4c5d6
Revises: d98938d8ab78
Create Date: 2026-06-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e1f2a3b4c5d6'
down_revision: Union[str, Sequence[str], None] = 'd98938d8ab78'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('customers', sa.Column('is_demo', sa.Boolean(), server_default=sa.text('true'), nullable=False))
    op.add_column('customers', sa.Column('active_scenario', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('customers', 'active_scenario')
    op.drop_column('customers', 'is_demo')
