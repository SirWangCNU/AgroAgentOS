"""Add Farm Agent proposal, task, and run context tables.

Revision ID: 007_add_farm_agent_workflow
Revises: 006_add_wx_binding
Create Date: 2026-07-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "007_add_farm_agent_workflow"
down_revision: Union[str, Sequence[str], None] = "006_add_wx_binding"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ensure_table_contract(
    table_name: str,
    *,
    indexes: dict[str, tuple[str, ...]],
    uniques: dict[str, tuple[str, ...]],
    foreign_keys: dict[str, tuple[tuple[str, ...], str, tuple[str, ...], str | None]],
) -> None:
    """Complete indexes and constraints after a non-transactional partial upgrade."""
    inspector = sa.inspect(op.get_bind())
    index_columns = {
        tuple(index["column_names"]) for index in inspector.get_indexes(table_name)
    }
    unique_columns = {
        tuple(constraint["column_names"])
        for constraint in inspector.get_unique_constraints(table_name)
    } | {
        tuple(index["column_names"])
        for index in inspector.get_indexes(table_name)
        if index.get("unique")
    }
    foreign_key_columns = {
        tuple(constraint["constrained_columns"])
        for constraint in inspector.get_foreign_keys(table_name)
    }

    with op.batch_alter_table(table_name) as batch_op:
        for name, columns in uniques.items():
            if columns not in unique_columns:
                batch_op.create_unique_constraint(name, list(columns))
        for name, (columns, referred_table, referred_columns, ondelete) in foreign_keys.items():
            if columns not in foreign_key_columns:
                batch_op.create_foreign_key(
                    name,
                    referred_table,
                    list(columns),
                    list(referred_columns),
                    ondelete=ondelete,
                )
        for name, columns in indexes.items():
            if columns not in index_columns and columns not in unique_columns:
                batch_op.create_index(name, list(columns))


def upgrade() -> None:
    """Add Farm Agent workflow persistence structures.

    Older deployments call ``Base.metadata.create_all`` during startup.  That can
    create the two new workflow tables before Alembic reaches this revision, while
    leaving ``agent_runs`` and the revision marker on the old schema.  Inspect each
    object so both a clean upgrade and recovery from that drift converge safely.
    """
    inspector = sa.inspect(op.get_bind())
    table_names = set(inspector.get_table_names())
    agent_columns = {
        column["name"] for column in inspector.get_columns("agent_runs")
    }
    agent_indexes = {
        index["name"] for index in inspector.get_indexes("agent_runs")
    }
    agent_foreign_key_columns = {
        tuple(foreign_key["constrained_columns"])
        for foreign_key in inspector.get_foreign_keys("agent_runs")
    }

    with op.batch_alter_table("agent_runs") as batch_op:
        if "user_id" not in agent_columns:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
        if "farm_id" not in agent_columns:
            batch_op.add_column(sa.Column("farm_id", sa.Integer(), nullable=True))
        if "run_type" not in agent_columns:
            batch_op.add_column(sa.Column("run_type", sa.String(32), nullable=True))
        if "context_snapshot_json" not in agent_columns:
            batch_op.add_column(sa.Column("context_snapshot_json", sa.Text(), nullable=True))
        if "outcome_json" not in agent_columns:
            batch_op.add_column(sa.Column("outcome_json", sa.Text(), nullable=True))
        if ("user_id",) not in agent_foreign_key_columns:
            batch_op.create_foreign_key("fk_agent_runs_user_id", "users", ["user_id"], ["id"])
        if ("farm_id",) not in agent_foreign_key_columns:
            batch_op.create_foreign_key(
                "fk_agent_runs_farm_id",
                "farms",
                ["farm_id"],
                ["id"],
                ondelete="SET NULL",
            )
        if "ix_agent_runs_user_id" not in agent_indexes:
            batch_op.create_index("ix_agent_runs_user_id", ["user_id"])
        if "ix_agent_runs_farm_id" not in agent_indexes:
            batch_op.create_index("ix_agent_runs_farm_id", ["farm_id"])
        if "ix_agent_runs_run_type" not in agent_indexes:
            batch_op.create_index("ix_agent_runs_run_type", ["run_type"])

    if "farm_action_proposals" not in table_names:
        op.create_table(
            "farm_action_proposals",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("proposal_id", sa.String(64), nullable=False),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=False),
            sa.Column("run_id", sa.String(64), nullable=False),
            sa.Column("risk_fingerprint", sa.String(64), nullable=False),
            sa.Column("title", sa.String(256), nullable=False),
            sa.Column("severity", sa.String(16), nullable=False),
            sa.Column("summary", sa.Text(), nullable=False),
            sa.Column("confidence", sa.Float(), nullable=False),
            sa.Column("evidence_json", sa.Text(), nullable=False),
            sa.Column("actions_json", sa.Text(), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("decision_note", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("decided_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["run_id"], ["agent_runs.run_id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("proposal_id", name="uq_farm_action_proposals_proposal_id"),
            sa.UniqueConstraint("run_id", "risk_fingerprint", name="uq_proposal_run_risk"),
        )
        op.create_index(
            "ix_farm_action_proposals_proposal_id",
            "farm_action_proposals",
            ["proposal_id"],
        )
        op.create_index("ix_farm_action_proposals_farm_id", "farm_action_proposals", ["farm_id"])
        op.create_index("ix_farm_action_proposals_created_by", "farm_action_proposals", ["created_by"])
        op.create_index("ix_farm_action_proposals_run_id", "farm_action_proposals", ["run_id"])
        op.create_index("ix_farm_action_proposals_status", "farm_action_proposals", ["status"])

    if "farm_tasks" not in table_names:
        op.create_table(
            "farm_tasks",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("task_id", sa.String(64), nullable=False),
            sa.Column("proposal_id", sa.String(64), nullable=True),
            sa.Column("action_key", sa.String(128), nullable=True),
            sa.Column("farm_id", sa.Integer(), nullable=False),
            sa.Column("field_id", sa.Integer(), nullable=True),
            sa.Column("assignee_name", sa.String(128), nullable=False),
            sa.Column("title", sa.String(256), nullable=False),
            sa.Column("task_type", sa.String(64), nullable=False),
            sa.Column("instructions", sa.Text(), nullable=False),
            sa.Column("acceptance_criteria_json", sa.Text(), nullable=False),
            sa.Column("priority", sa.String(16), nullable=False),
            sa.Column("status", sa.String(16), nullable=False),
            sa.Column("due_at", sa.DateTime(), nullable=True),
            sa.Column("execution_json", sa.Text(), nullable=False),
            sa.Column("agent_verdict_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["farm_id"], ["farms.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["field_id"], ["fields.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["proposal_id"], ["farm_action_proposals.proposal_id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("task_id", name="uq_farm_tasks_task_id"),
            sa.UniqueConstraint("proposal_id", "action_key", name="uq_task_proposal_action"),
        )
        op.create_index("ix_farm_tasks_task_id", "farm_tasks", ["task_id"])
        op.create_index("ix_farm_tasks_proposal_id", "farm_tasks", ["proposal_id"])
        op.create_index("ix_farm_tasks_farm_id", "farm_tasks", ["farm_id"])
        op.create_index("ix_farm_tasks_field_id", "farm_tasks", ["field_id"])
        op.create_index("ix_farm_tasks_task_type", "farm_tasks", ["task_type"])
        op.create_index("ix_farm_tasks_status", "farm_tasks", ["status"])

    _ensure_table_contract(
        "farm_action_proposals",
        indexes={
            "ix_farm_action_proposals_proposal_id": ("proposal_id",),
            "ix_farm_action_proposals_farm_id": ("farm_id",),
            "ix_farm_action_proposals_created_by": ("created_by",),
            "ix_farm_action_proposals_run_id": ("run_id",),
            "ix_farm_action_proposals_status": ("status",),
        },
        uniques={
            "uq_farm_action_proposals_proposal_id": ("proposal_id",),
            "uq_proposal_run_risk": ("run_id", "risk_fingerprint"),
        },
        foreign_keys={
            "fk_farm_action_proposals_farm_id": (("farm_id",), "farms", ("id",), "CASCADE"),
            "fk_farm_action_proposals_created_by": (("created_by",), "users", ("id",), None),
            "fk_farm_action_proposals_run_id": (("run_id",), "agent_runs", ("run_id",), None),
        },
    )
    _ensure_table_contract(
        "farm_tasks",
        indexes={
            "ix_farm_tasks_task_id": ("task_id",),
            "ix_farm_tasks_proposal_id": ("proposal_id",),
            "ix_farm_tasks_farm_id": ("farm_id",),
            "ix_farm_tasks_field_id": ("field_id",),
            "ix_farm_tasks_task_type": ("task_type",),
            "ix_farm_tasks_status": ("status",),
        },
        uniques={
            "uq_farm_tasks_task_id": ("task_id",),
            "uq_task_proposal_action": ("proposal_id", "action_key"),
        },
        foreign_keys={
            "fk_farm_tasks_proposal_id": (
                ("proposal_id",),
                "farm_action_proposals",
                ("proposal_id",),
                None,
            ),
            "fk_farm_tasks_farm_id": (("farm_id",), "farms", ("id",), "CASCADE"),
            "fk_farm_tasks_field_id": (("field_id",), "fields", ("id",), "SET NULL"),
        },
    )


def downgrade() -> None:
    """Remove Farm Agent workflow persistence structures."""
    op.drop_table("farm_tasks")
    op.drop_table("farm_action_proposals")

    with op.batch_alter_table("agent_runs") as batch_op:
        batch_op.drop_index("ix_agent_runs_run_type")
        batch_op.drop_index("ix_agent_runs_farm_id")
        batch_op.drop_index("ix_agent_runs_user_id")
        batch_op.drop_constraint("fk_agent_runs_farm_id", type_="foreignkey")
        batch_op.drop_constraint("fk_agent_runs_user_id", type_="foreignkey")
        batch_op.drop_column("outcome_json")
        batch_op.drop_column("context_snapshot_json")
        batch_op.drop_column("run_type")
        batch_op.drop_column("farm_id")
        batch_op.drop_column("user_id")
