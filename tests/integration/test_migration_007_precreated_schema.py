"""Migration 007 must recover from tables pre-created by SQLAlchemy metadata."""

from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

from sqlalchemy import create_engine, inspect


ROOT = Path(__file__).resolve().parents[2]


def _environment(database_path: Path) -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "DEBUG": "false",
            "USE_SQLITE": "true",
            "SQLITE_DB_PATH": database_path.as_posix(),
            "PYTHONPATH": str(ROOT),
        }
    )
    return environment


def _run(command: list[str], *, environment: dict[str, str]) -> None:
    subprocess.run(
        command,
        cwd=ROOT,
        env=environment,
        check=True,
        capture_output=True,
        text=True,
    )


def test_upgrade_handles_workflow_tables_precreated_by_metadata(tmp_path: Path) -> None:
    database_path = tmp_path / "precreated.db"
    environment = _environment(database_path)
    _run([sys.executable, "-m", "alembic", "upgrade", "006_add_wx_binding"], environment=environment)
    _run(
        [
            sys.executable,
            "-c",
            "import app.models.farm_agent; from app.core.sqlite import Base; from sqlalchemy import create_engine; "
            "Base.metadata.create_all(create_engine('sqlite:///" + database_path.as_posix() + "'))",
        ],
        environment=environment,
    )
    precreated_engine = create_engine(f"sqlite:///{database_path.as_posix()}")
    with precreated_engine.begin() as connection:
        connection.exec_driver_sql("DROP INDEX ix_farm_tasks_status")

    _run([sys.executable, "-m", "alembic", "upgrade", "head"], environment=environment)

    schema = inspect(create_engine(f"sqlite:///{database_path.as_posix()}"))
    assert {"farm_action_proposals", "farm_tasks"} <= set(schema.get_table_names())
    agent_columns = {column["name"] for column in schema.get_columns("agent_runs")}
    assert {"user_id", "farm_id", "run_type", "context_snapshot_json", "outcome_json"} <= agent_columns
    task_index_columns = {
        tuple(index["column_names"])
        for index in schema.get_indexes("farm_tasks")
    }
    assert ("status",) in task_index_columns
