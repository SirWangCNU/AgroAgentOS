"""Add wx binding fields to users table

Revision ID: 006_add_wx_binding
Revises: 005_add_video_tasks
Create Date: 2026-07-10 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '006_add_wx_binding'
down_revision: Union[str, Sequence[str], None] = '005_add_video_tasks'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add wx_openid / wx_unionid / nickname / avatar_url to users."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.add_column(sa.Column('wx_openid', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('wx_unionid', sa.String(128), nullable=True))
        batch_op.add_column(sa.Column('nickname', sa.String(64), nullable=True))
        batch_op.add_column(sa.Column('avatar_url', sa.String(512), nullable=True))
        batch_op.create_unique_constraint('uq_users_wx_openid', ['wx_openid'])
    op.create_index('ix_users_wx_openid', 'users', ['wx_openid'])
    op.create_index('ix_users_wx_unionid', 'users', ['wx_unionid'])


def downgrade() -> None:
    """Drop wx binding fields."""
    op.drop_index('ix_users_wx_unionid', table_name='users')
    op.drop_index('ix_users_wx_openid', table_name='users')
    with op.batch_alter_table('users') as batch_op:
        batch_op.drop_constraint('uq_users_wx_openid', type_='unique')
        batch_op.drop_column('avatar_url')
        batch_op.drop_column('nickname')
        batch_op.drop_column('wx_unionid')
        batch_op.drop_column('wx_openid')
