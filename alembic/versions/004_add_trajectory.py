"""Add trajectory tables and boundary_json field

Revision ID: 004_add_trajectory
Revises: 003_add_farms_fields
Create Date: 2026-06-01 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '004_add_trajectory'
down_revision: Union[str, Sequence[str], None] = '003_add_farms_fields'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create trajectory tables and add boundary_json to fields."""
    # 创建 trajectory_files 表
    op.create_table(
        'trajectory_files',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('field_id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(256), nullable=False),
        sa.Column('machine_id', sa.String(64), nullable=True),
        sa.Column('point_count', sa.Integer(), nullable=True),
        sa.Column('start_time', sa.DateTime(), nullable=True),
        sa.Column('end_time', sa.DateTime(), nullable=True),
        sa.Column('total_distance_m', sa.Float(), nullable=True),
        sa.Column('work_distance_m', sa.Float(), nullable=True),
        sa.Column('work_area_mu', sa.Float(), nullable=True),
        sa.Column('avg_depth', sa.Float(), nullable=True),
        sa.Column('avg_speed', sa.Float(), nullable=True),
        sa.Column('depth_std', sa.Float(), nullable=True),
        sa.Column('work_width', sa.Float(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['field_id'], ['fields.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_trajectory_files_field_id', 'trajectory_files', ['field_id'])

    # 创建 trajectory_points 表
    op.create_table(
        'trajectory_points',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('file_id', sa.Integer(), nullable=False),
        sa.Column('seq', sa.Integer(), nullable=False),
        sa.Column('gps_time', sa.DateTime(), nullable=True),
        sa.Column('latitude', sa.Float(), nullable=False),
        sa.Column('longitude', sa.Float(), nullable=False),
        sa.Column('speed', sa.Float(), nullable=True),
        sa.Column('work_status', sa.String(32), nullable=True),
        sa.Column('depth', sa.Float(), nullable=True),
        sa.Column('depth_std', sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['file_id'], ['trajectory_files.id'], ondelete='CASCADE'),
    )
    op.create_index('ix_trajectory_points_file_id', 'trajectory_points', ['file_id'])

    # fields 表添加 boundary_json 列
    op.add_column('fields', sa.Column('boundary_json', sa.Text(), nullable=True))


def downgrade() -> None:
    """Drop trajectory tables and remove boundary_json."""
    op.drop_column('fields', 'boundary_json')
    op.drop_table('trajectory_points')
    op.drop_table('trajectory_files')
