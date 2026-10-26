"""add position stage owner

Revision ID: c58d2e91a7f0
Revises: f3a9c17e8b24
Create Date: 2026-10-26

"""
from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c58d2e91a7f0'
down_revision: Union[str, Sequence[str], None] = 'f3a9c17e8b24'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """岗位级的阶段负责人表：岗位 × 关卡 → HR，对该岗位全部候选人生效。"""
    op.create_table(
        'position_stage_owner',
        sa.Column('ID', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('pos_id', sa.Integer(), nullable=False),
        sa.Column('stage', sa.String(length=20), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.Column('update_time', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['pos_id'], ['position.ID'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['user.ID'], ondelete='SET NULL'),
        sa.PrimaryKeyConstraint('ID'),
        sa.UniqueConstraint('pos_id', 'stage', name='UK_Pos_Stage'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('position_stage_owner')
