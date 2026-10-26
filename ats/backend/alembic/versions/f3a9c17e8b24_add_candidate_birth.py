"""add candidate birth

Revision ID: f3a9c17e8b24
Revises: dd24e8f65848
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'f3a9c17e8b24'
down_revision: Union[str, Sequence[str], None] = 'dd24e8f65848'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """候选人表加「出生年月」列（可空字符串，如 1999-06）。"""
    op.add_column('candidate', sa.Column('birth', sa.String(length=20), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('candidate', 'birth')
