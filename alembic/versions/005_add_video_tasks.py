"""Add video_tasks table

Revision ID: 005_add_video_tasks
Revises: 004_add_trajectory
Create Date: 2026-06-20 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '005_add_video_tasks'
down_revision: Union[str, Sequence[str], None] = '004_add_trajectory'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create video_tasks table."""
    op.create_table(
        'video_tasks',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('task_id', sa.String(128), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('image_url', sa.String(512), nullable=True),
        sa.Column('model', sa.String(128), nullable=True),
        sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
        sa.Column('video_url', sa.String(1024), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('duration', sa.Float(), nullable=True),
        sa.Column('extra_json', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_video_tasks_task_id', 'video_tasks', ['task_id'], unique=True)
    op.create_index('ix_video_tasks_user_id', 'video_tasks', ['user_id'])


def downgrade() -> None:
    """Drop video_tasks table."""
    op.drop_index('ix_video_tasks_user_id', table_name='video_tasks')
    op.drop_index('ix_video_tasks_task_id', table_name='video_tasks')
    op.drop_table('video_tasks')
