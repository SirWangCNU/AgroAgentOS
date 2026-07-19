"""Add SensorReading table for multi-source perception data.

Revision ID: 009_add_sensor_reading
Revises: 008_crop_season_event
Create Date: 2026-07-19 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "009_add_sensor_reading"
down_revision: Union[str, Sequence[str], None] = "008_crop_season_event"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create sensor_readings table.

    老部署可能已经通过 Base.metadata.create_all 提前建表，用 inspector 检测后跳过。
    """
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())

    if "sensor_readings" not in table_names:
        op.create_table(
            "sensor_readings",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("field_id", sa.Integer(), nullable=False),
            sa.Column("sensor_type", sa.String(32), nullable=False),
            sa.Column("value_float", sa.Float(), nullable=True),
            sa.Column("value_json", sa.Text(), nullable=False),
            sa.Column("unit", sa.String(32), nullable=False),
            sa.Column("observed_at", sa.DateTime(), nullable=False),
            sa.Column("source", sa.String(32), nullable=False),
            sa.Column("scenario_id", sa.String(64), nullable=True),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "field_id",
                "sensor_type",
                "observed_at",
                "scenario_id",
                name="uq_sensor_reading_dedup",
            ),
        )
        op.create_index("ix_sensor_readings_field_id", "sensor_readings", ["field_id"])
        op.create_index("ix_sensor_readings_sensor_type", "sensor_readings", ["sensor_type"])
        op.create_index("ix_sensor_readings_observed_at", "sensor_readings", ["observed_at"])
        op.create_index("ix_sensor_readings_source", "sensor_readings", ["source"])
        op.create_index("ix_sensor_readings_scenario_id", "sensor_readings", ["scenario_id"])


def downgrade() -> None:
    """Drop sensor_readings table."""
    op.drop_table("sensor_readings")
