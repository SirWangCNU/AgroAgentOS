"""Alembic 迁移回归测试。"""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_upgrade_to_head_removes_trajectory_tables(tmp_path: Path):
    """若删除迁移缺失，新数据库升级到 head 后仍会保留已退役的轨迹表。"""
    db_path = tmp_path / "farm-refactor.db"
    environment = os.environ.copy()
    environment.update(
        {
            "DEBUG": "false",
            "USE_SQLITE": "true",
            "SQLITE_DB_PATH": str(db_path),
        }
    )

    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(db_path) as connection:
        tables = {
            row[0]
            for row in connection.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        history_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(history_records)")
        }
        field_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(fields)")
        }

    assert {"farms", "fields"}.issubset(tables)
    assert "user_id" in history_columns
    assert "boundary_json" in field_columns
    assert "trajectory_points" not in tables
    assert "trajectory_files" not in tables


def test_database_at_legacy_head_can_upgrade_to_current_head(tmp_path: Path):
    """保留旧版数据库修订标记，避免已部署数据库失去升级路径。"""
    db_path = tmp_path / "legacy-head.db"
    environment = os.environ.copy()
    environment.update(
        {
            "DEBUG": "false",
            "USE_SQLITE": "true",
            "SQLITE_DB_PATH": str(db_path),
        }
    )

    legacy_upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "014_retire_farm_flow"],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert legacy_upgrade.returncode == 0, legacy_upgrade.stderr

    current_upgrade = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
        capture_output=True,
        check=False,
    )
    assert current_upgrade.returncode == 0, current_upgrade.stderr

    with sqlite3.connect(db_path) as connection:
        columns = {
            row[1] for row in connection.execute("PRAGMA table_info(history_records)")
        }
        field_columns = {
            row[1] for row in connection.execute("PRAGMA table_info(fields)")
        }
    assert "user_id" in columns
    assert "boundary_json" in field_columns
