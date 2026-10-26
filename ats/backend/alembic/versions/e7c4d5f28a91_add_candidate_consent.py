"""add candidate consent

Revision ID: e7c4d5f28a91
Revises: c58d2e91a7f0
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'e7c4d5f28a91'
down_revision: Union[str, Sequence[str], None] = 'c58d2e91a7f0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """候选人表加隐私政策同意记录（PIPL 告知-同意环节）。"""
    op.add_column('candidate', sa.Column('consent_time', sa.DateTime(), nullable=True))
    op.add_column('candidate', sa.Column('consent_version', sa.String(length=50), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('candidate', 'consent_version')
    op.drop_column('candidate', 'consent_time')
