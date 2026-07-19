"""Add CropSeason and FarmEvent tables, and Field.current_season_id pointer.

Revision ID: 008_crop_season_event
Revises: 007_add_farm_agent_workflow
Create Date: 2026-07-19 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "008_crop_season_event"
down_revision: Union[str, Sequence[str], None] = "007_add_farm_agent_workflow"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create crop_seasons + farm_events tables and add fields.current_season_id.

    老部署可能已经通过 Base.metadata.create_all 提前建表，用 inspector 检测后跳过。
    """
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())

    # 1) crop_seasons 表
    if "crop_seasons" not in table_names:
        op.create_table(
            "crop_seasons",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("field_id", sa.Integer(), nullable=False),
            sa.Column("crop_name", sa.String(64), nullable=False),
            sa.Column("variety", sa.String(128), nullable=False),
            sa.Column("season_code", sa.String(32), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("expected_harvest", sa.Date(), nullable=True),
            sa.Column("current_stage", sa.String(64), nullable=False),
            sa.Column("area_mu", sa.Float(), nullable=False),
            sa.Column("target_yield", sa.String(64), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_crop_seasons_field_id", "crop_seasons", ["field_id"])
        op.create_index("ix_crop_seasons_status", "crop_seasons", ["status"])

    # 2) farm_events 表
    if "farm_events" not in table_names:
        op.create_table(
            "farm_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("field_id", sa.Integer(), nullable=False),
            sa.Column("season_id", sa.Integer(), nullable=True),
            sa.Column("event_type", sa.String(32), nullable=False),
            sa.Column("event_time", sa.DateTime(), nullable=False),
            sa.Column("operator", sa.String(128), nullable=False),
            sa.Column("inputs_json", sa.Text(), nullable=False),
            sa.Column("geo_payload_json", sa.Text(), nullable=False),
            sa.Column("source", sa.String(32), nullable=False),
            sa.Column("related_task_id", sa.String(64), nullable=True),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("note", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["season_id"], ["crop_seasons.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "related_task_id",
                "event_type",
                name="uq_event_task_type",
            ),
        )
        op.create_index("ix_farm_events_field_id", "farm_events", ["field_id"])
        op.create_index("ix_farm_events_season_id", "farm_events", ["season_id"])
        op.create_index("ix_farm_events_event_type", "farm_events", ["event_type"])
        op.create_index("ix_farm_events_event_time", "farm_events", ["event_time"])
        op.create_index("ix_farm_events_source", "farm_events", ["source"])
        op.create_index("ix_farm_events_related_task_id", "farm_events", ["related_task_id"])

    # 3) fields.current_season_id 指针（指向当前茬次）
    field_columns = {column["name"] for column in inspector.get_columns("fields")}
    field_indexes = {index["name"] for index in inspector.get_indexes("fields")}
    field_foreign_key_columns = {
        tuple(foreign_key["constrained_columns"])
        for foreign_key in inspector.get_foreign_keys("fields")
    }

    with op.batch_alter_table("fields") as batch_op:
        if "current_season_id" not in field_columns:
            batch_op.add_column(sa.Column("current_season_id", sa.Integer(), nullable=True))
        if ("current_season_id",) not in field_foreign_key_columns:
            batch_op.create_foreign_key(
                "fk_fields_current_season_id",
                "crop_seasons",
                ["current_season_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "ix_fields_current_season_id" not in field_indexes:
            batch_op.create_index("ix_fields_current_season_id", ["current_season_id"])


def downgrade() -> None:
    """Drop farm_events + crop_seasons tables and remove fields.current_season_id."""
    with op.batch_alter_table("fields") as batch_op:
        batch_op.drop_index("ix_fields_current_season_id")
        batch_op.drop_constraint("fk_fields_current_season_id", type_="foreignkey")
        batch_op.drop_column("current_season_id")

    op.drop_table("farm_events")
    op.drop_table("crop_seasons")