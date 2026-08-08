"""Add history record ownership.

Revision ID: 008_add_history_record_owner
Revises: 007_remove_trajectory_tables
Create Date: 2026-08-01 15:30:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "008_add_history_record_owner"
down_revision: Union[str, Sequence[str], None] = "007_remove_trajectory_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add owner IDs and recover ownership from existing chat sessions."""
    op.add_column("history_records", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_index("ix_history_records_user_id", "history_records", ["user_id"])

    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            """
            UPDATE history_records AS history
            JOIN chat_sessions AS session ON session.session_id = history.session_id
            SET history.user_id = CAST(session.user_id AS UNSIGNED)
            WHERE history.user_id IS NULL AND session.user_id REGEXP '^[0-9]+$'
            """
        )
    else:
        op.execute(
            """
            UPDATE history_records
            SET user_id = (
                SELECT CAST(chat_sessions.user_id AS INTEGER)
                FROM chat_sessions
                WHERE chat_sessions.session_id = history_records.session_id
            )
            WHERE user_id IS NULL
              AND session_id IS NOT NULL
              AND EXISTS (
                  SELECT 1
                  FROM chat_sessions
                  WHERE chat_sessions.session_id = history_records.session_id
                    AND chat_sessions.user_id GLOB '[0-9]*'
              )
            """
        )


def downgrade() -> None:
    """Remove the ownership column.

    This intentionally does not delete the original history rows.
    """
    op.drop_index("ix_history_records_user_id", table_name="history_records")
    with op.batch_alter_table("history_records") as batch_op:
        batch_op.drop_column("user_id")
