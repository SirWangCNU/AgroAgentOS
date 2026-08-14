"""Add field boundary GeoJSON storage.

Revision ID: 009_add_field_boundary_json
Revises: 008_add_history_record_owner
Create Date: 2026-08-11 21:20:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "009_add_field_boundary_json"
down_revision: Union[str, Sequence[str], None] = "008_add_history_record_owner"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add the GeoJSON text column used by drawn field polygons."""
    bind = op.get_bind()
    existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("fields")}
    if "boundary_json" in existing_columns:
        return
    with op.batch_alter_table("fields") as batch_op:
        batch_op.add_column(sa.Column("boundary_json", sa.Text(), nullable=True, server_default=""))


def downgrade() -> None:
    """Remove the field boundary column."""
    bind = op.get_bind()
    existing_columns = {column["name"] for column in sa.inspect(bind).get_columns("fields")}
    if "boundary_json" not in existing_columns:
        return
    with op.batch_alter_table("fields") as batch_op:
        batch_op.drop_column("boundary_json")
