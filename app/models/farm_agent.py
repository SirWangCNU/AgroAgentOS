"""Farm Agent 提案和任务 ORM 模型."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)

from app.core.sqlite import Base


def _load_json_list(value: str | None, *, field_name: str) -> list[Any]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, list):
            raise ValueError("JSON value is not a list")
        return parsed
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("解析 {} 失败，返回空列表: {}", field_name, exc)
        return []


def _load_json_dict(value: str | None, *, field_name: str) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("JSON value is not an object")
        return parsed
    except (TypeError, ValueError, json.JSONDecodeError) as exc:
        logger.warning("解析 {} 失败，返回空对象: {}", field_name, exc)
        return {}


class FarmActionProposal(Base):
    """Agent 生成、等待人工决策的农场行动提案."""

    __tablename__ = "farm_action_proposals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    proposal_id = Column(String(64), unique=True, nullable=False, index=True)
    farm_id = Column(
        Integer,
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    run_id = Column(
        String(64),
        ForeignKey("agent_runs.run_id"),
        nullable=False,
        index=True,
    )
    risk_fingerprint = Column(String(64), nullable=False)
    title = Column(String(256), nullable=False)
    severity = Column(String(16), nullable=False)
    summary = Column(Text, nullable=False)
    confidence = Column(Float, nullable=False, default=0.0)
    evidence_json = Column(Text, nullable=False, default="[]")
    actions_json = Column(Text, nullable=False, default="[]")
    status = Column(String(16), nullable=False, default="pending", index=True)
    decision_note = Column(Text, nullable=False, default="")
    created_at = Column(DateTime, nullable=False, default=func.now())
    decided_at = Column(DateTime, nullable=True)

    __table_args__ = (
        UniqueConstraint("run_id", "risk_fingerprint", name="uq_proposal_run_risk"),
    )

    @property
    def evidence(self) -> list[dict[str, Any]]:
        return _load_json_list(self.evidence_json, field_name="evidence_json")

    def set_evidence(self, data: list[dict[str, Any]]) -> None:
        self.evidence_json = json.dumps(data, ensure_ascii=False, default=str)

    @property
    def actions(self) -> list[dict[str, Any]]:
        return _load_json_list(self.actions_json, field_name="actions_json")

    def set_actions(self, data: list[dict[str, Any]]) -> None:
        self.actions_json = json.dumps(data, ensure_ascii=False, default=str)


class FarmTask(Base):
    """人工批准后创建的农场执行任务."""

    __tablename__ = "farm_tasks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    task_id = Column(String(64), unique=True, nullable=False, index=True)
    proposal_id = Column(
        String(64),
        ForeignKey("farm_action_proposals.proposal_id"),
        nullable=True,
        index=True,
    )
    action_key = Column(String(128), nullable=True)
    farm_id = Column(
        Integer,
        ForeignKey("farms.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    field_id = Column(
        Integer,
        ForeignKey("fields.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignee_name = Column(String(128), nullable=False, default="")
    title = Column(String(256), nullable=False)
    task_type = Column(String(64), nullable=False, index=True)
    instructions = Column(Text, nullable=False)
    acceptance_criteria_json = Column(Text, nullable=False, default="[]")
    priority = Column(String(16), nullable=False, default="normal")
    status = Column(String(16), nullable=False, default="pending", index=True)
    due_at = Column(DateTime, nullable=True)
    execution_json = Column(Text, nullable=False, default="{}")
    agent_verdict_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, nullable=False, default=func.now())
    updated_at = Column(DateTime, nullable=False, default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint("proposal_id", "action_key", name="uq_task_proposal_action"),
    )

    @property
    def acceptance_criteria(self) -> list[str]:
        return _load_json_list(
            self.acceptance_criteria_json,
            field_name="acceptance_criteria_json",
        )

    def set_acceptance_criteria(self, data: list[str]) -> None:
        self.acceptance_criteria_json = json.dumps(data, ensure_ascii=False, default=str)

    @property
    def execution(self) -> dict[str, Any]:
        return _load_json_dict(self.execution_json, field_name="execution_json")

    def set_execution(self, data: dict[str, Any]) -> None:
        self.execution_json = json.dumps(data, ensure_ascii=False, default=str)

    @property
    def agent_verdict(self) -> dict[str, Any]:
        return _load_json_dict(self.agent_verdict_json, field_name="agent_verdict_json")

    def set_agent_verdict(self, data: dict[str, Any]) -> None:
        self.agent_verdict_json = json.dumps(data, ensure_ascii=False, default=str)
