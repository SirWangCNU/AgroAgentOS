"""Add trajectory evidence metadata.

Revision ID: 011_trajectory_evidence
Revises: 010_add_message_metadata
Create Date: 2026-07-20 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "011_trajectory_evidence"
down_revision: Union[str, Sequence[str], None] = "010_add_message_metadata"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_column_if_missing(table_name: str, column: sa.Column) -> bool:
    inspector = sa.inspect(op.get_bind())
    columns = {item["name"] for item in inspector.get_columns(table_name)}
    if column.name in columns:
        return False
    op.add_column(table_name, column)
    return True


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    inspector = sa.inspect(op.get_bind())
    indexes = {item["name"] for item in inspector.get_indexes(table_name)}
    if index_name not in indexes:
        op.create_index(index_name, table_name, columns)


def upgrade() -> None:
    """Add metadata used to treat trajectories as farm work evidence."""
    inspector = sa.inspect(op.get_bind())
    if "trajectory_files" not in set(inspector.get_table_names()):
        return

    _add_column_if_missing(
        "trajectory_files",
        sa.Column("operation_type", sa.String(64), nullable=False, server_default="unknown"),
    )
    _add_column_if_missing(
        "trajectory_files",
        sa.Column("season_id", sa.Integer(), nullable=True),
    )
    _add_column_if_missing(
        "trajectory_files",
        sa.Column("related_task_id", sa.String(64), nullable=True),
    )
    _add_column_if_missing(
        "trajectory_files",
        sa.Column("operator", sa.String(128), nullable=False, server_default=""),
    )
    _add_column_if_missing(
        "trajectory_files",
        sa.Column("event_time", sa.DateTime(), nullable=True),
    )
    _add_column_if_missing(
        "trajectory_files",
        sa.Column("coverage_rate", sa.Float(), nullable=True),
    )
    _add_column_if_missing(
        "trajectory_files",
        sa.Column("quality_summary_json", sa.Text(), nullable=True),
    )

    _create_index_if_missing(
        "trajectory_files",
        "ix_trajectory_files_operation_type",
        ["operation_type"],
    )
    _create_index_if_missing(
        "trajectory_files",
        "ix_trajectory_files_season_id",
        ["season_id"],
    )
    _create_index_if_missing(
        "trajectory_files",
        "ix_trajectory_files_related_task_id",
        ["related_task_id"],
    )


def downgrade() -> None:
    """Remove trajectory evidence metadata columns."""
    inspector = sa.inspect(op.get_bind())
    if "trajectory_files" not in set(inspector.get_table_names()):
        return

    existing_columns = {item["name"] for item in inspector.get_columns("trajectory_files")}
    existing_indexes = {item["name"] for item in inspector.get_indexes("trajectory_files")}

    for index_name in (
        "ix_trajectory_files_related_task_id",
        "ix_trajectory_files_season_id",
        "ix_trajectory_files_operation_type",
    ):
        if index_name in existing_indexes:
            op.drop_index(index_name, table_name="trajectory_files")

    for column_name in (
        "quality_summary_json",
        "coverage_rate",
        "event_time",
        "operator",
        "related_task_id",
        "season_id",
        "operation_type",
    ):
        if column_name in existing_columns:
            op.drop_column("trajectory_files", column_name)
