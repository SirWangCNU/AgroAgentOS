"""Remove retired trajectory tables.

Revision ID: 007_remove_trajectory_tables
Revises: 006_add_wx_binding
Create Date: 2026-07-29 21:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_remove_trajectory_tables"
down_revision: Union[str, Sequence[str], None] = "006_add_wx_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Drop trajectory points before their parent file table."""
    op.drop_index("ix_trajectory_points_file_id", table_name="trajectory_points")
    op.drop_table("trajectory_points")
    op.drop_index("ix_trajectory_files_field_id", table_name="trajectory_files")
    op.drop_table("trajectory_files")


def downgrade() -> None:
    """Recreate empty retired tables; deleted records cannot be recovered."""
    op.create_table(
        "trajectory_files",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("field_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(256), nullable=False),
        sa.Column("machine_id", sa.String(64), nullable=True),
        sa.Column("point_count", sa.Integer(), nullable=True),
        sa.Column("start_time", sa.DateTime(), nullable=True),
        sa.Column("end_time", sa.DateTime(), nullable=True),
        sa.Column("total_distance_m", sa.Float(), nullable=True),
        sa.Column("work_distance_m", sa.Float(), nullable=True),
        sa.Column("work_area_mu", sa.Float(), nullable=True),
        sa.Column("avg_depth", sa.Float(), nullable=True),
        sa.Column("avg_speed", sa.Float(), nullable=True),
        sa.Column("depth_std", sa.Float(), nullable=True),
        sa.Column("work_width", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trajectory_files_field_id", "trajectory_files", ["field_id"])
    op.create_table(
        "trajectory_points",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("file_id", sa.Integer(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column("gps_time", sa.DateTime(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=False),
        sa.Column("longitude", sa.Float(), nullable=False),
        sa.Column("speed", sa.Float(), nullable=True),
        sa.Column("work_status", sa.String(32), nullable=True),
        sa.Column("depth", sa.Float(), nullable=True),
        sa.Column("depth_std", sa.Float(), nullable=True),
        sa.ForeignKeyConstraint(["file_id"], ["trajectory_files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_trajectory_points_file_id", "trajectory_points", ["file_id"])
