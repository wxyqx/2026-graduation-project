"""add user token_valid_after

Revision ID: b9f2a83c61de
Revises: e7c4d5f28a91
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'b9f2a83c61de'
down_revision: Union[str, Sequence[str], None] = 'e7c4d5f28a91'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """强制下线基准线：改密/重置后早于该时间的 token 全部失效。"""
    op.add_column('user', sa.Column('token_valid_after', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('user', 'token_valid_after')
