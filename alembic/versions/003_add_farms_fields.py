"""Add farms and fields tables

Revision ID: 003_add_farms_fields
Revises: 002_add_users
Create Date: 2026-05-30 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '003_add_farms_fields'
down_revision: Union[str, Sequence[str], None] = '002_add_users'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create farms and fields tables."""
    # 创建 farms 表
    op.create_table(
        'farms',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('location', sa.String(256), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('area_mu', sa.Float(), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )
    op.create_index('ix_farms_user_id', 'farms', ['user_id'])

    # 创建 fields 表
    op.create_table(
        'fields',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('farm_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(128), nullable=False),
        sa.Column('area_mu', sa.Float(), nullable=True),
        sa.Column('soil_type', sa.String(64), nullable=True),
        sa.Column('current_crop', sa.String(64), nullable=True),
        sa.Column('planting_date', sa.Date(), nullable=True),
        sa.Column('expected_harvest', sa.Date(), nullable=True),
        sa.Column('growth_stage', sa.String(64), nullable=True),
        sa.Column('status', sa.String(32), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=True),
        sa.Column('longitude', sa.Float(), nullable=True),
        sa.Column('notes', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['farm_id'], ['farms.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_fields_farm_id', 'fields', ['farm_id'])


def downgrade() -> None:
    """Drop fields and farms tables."""
    op.drop_table('fields')
    op.drop_table('farms')
