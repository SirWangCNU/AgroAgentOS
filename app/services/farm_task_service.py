"""农场执行任务状态机、执行证据和复核草稿服务。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, NoReturn

from sqlalchemy.orm import Session

from app.core.sqlite import sqlite_manager
from app.exceptions import AppException, ForbiddenError
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmTask
from app.models.trajectory import TrajectoryFile
from app.schemas.farm_agent import (
    TaskEvidenceBundle,
    TaskStatus,
    TaskSubmitRequest,
    TaskVerificationDraft,
)
from app.schemas.trajectory import TrajectoryFileInfo


ALLOWED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    "pending": {"in_progress", "cancelled"},
    "in_progress": {"submitted", "cancelled"},
    "submitted": {"completed", "returned"},
    "returned": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


def _raise_forbidden() -> NoReturn:
    raise ForbiddenError(message="无权访问目标资源")


def _raise_invalid_transition() -> NoReturn:
    raise AppException(
        status_code=409,
        code="INVALID_TASK_TRANSITION",
        message="当前任务状态不允许该操作",
    )


def _require_allowed_transition(
    source: TaskStatus,
    target: TaskStatus,
) -> None:
    if target not in ALLOWED_TRANSITIONS[source]:
        _raise_invalid_transition()


def _require_owned_farm(
    session: Session,
    *,
    farm_id: int,
    user_id: int,
) -> Farm:
    farm = (
        session.query(Farm)
        .filter(Farm.id == farm_id, Farm.user_id == user_id)
        .first()
    )
    if farm is None:
        _raise_forbidden()
    return farm


def _require_owned_task(
    session: Session,
    *,
    task_id: str,
    user_id: int,
) -> FarmTask:
    task = (
        session.query(FarmTask)
        .join(Farm, Farm.id == FarmTask.farm_id)
        .filter(FarmTask.task_id == task_id, Farm.user_id == user_id)
        .first()
    )
    if task is None:
        _raise_forbidden()
    return task


def _load_task_trajectories(
    session: Session,
    *,
    farm_id: int,
    trajectory_file_ids: list[int],
) -> list[TrajectoryFile]:
    if not trajectory_file_ids:
        return []
    requested_ids = set(trajectory_file_ids)
    trajectories = (
        session.query(TrajectoryFile)
        .join(Field, Field.id == TrajectoryFile.field_id)
        .filter(
            TrajectoryFile.id.in_(requested_ids),
            Field.farm_id == farm_id,
        )
        .all()
    )
    trajectories_by_id = {trajectory.id: trajectory for trajectory in trajectories}
    if set(trajectories_by_id) != requested_ids:
        _raise_forbidden()
    return [trajectories_by_id[file_id] for file_id in trajectory_file_ids]


def _detach_task(session: Session, task: FarmTask) -> FarmTask:
    session.expunge(task)
    return task


def _audit_entry(*, action: str, note: str, timestamp: datetime) -> dict[str, str]:
    return {
        "actor": "human",
        "action": action,
        "note": note,
        "timestamp": timestamp.isoformat(),
    }


def _transition(
    session: Session,
    *,
    task: FarmTask,
    target_status: TaskStatus,
    action: str,
    note: str,
    execution_changes: dict[str, Any] | None = None,
) -> FarmTask:
    """用来源状态 CAS 完成人工转换并追加审计记录。"""

    source_status: TaskStatus = task.status
    _require_allowed_transition(source_status, target_status)
    now = datetime.now(timezone.utc)
    execution = dict(task.execution)
    if execution_changes:
        execution.update(execution_changes)
    existing_audit = execution.get("audit")
    audit = list(existing_audit) if isinstance(existing_audit, list) else []
    audit.append(_audit_entry(action=action, note=note, timestamp=now))
    execution["audit"] = audit
    execution_json = json.dumps(execution, ensure_ascii=False)

    affected_rows = (
        session.query(FarmTask)
        .filter(
            FarmTask.task_id == task.task_id,
            FarmTask.status == source_status,
        )
        .update(
            {
                FarmTask.status: target_status,
                FarmTask.execution_json: execution_json,
                FarmTask.updated_at: now,
            },
            synchronize_session=False,
        )
    )
    if affected_rows != 1:
        _raise_invalid_transition()

    session.expire(task)
    session.refresh(task)
    return _detach_task(session, task)


def list_tasks(
    *,
    user_id: int,
    farm_id: int | None,
    status: TaskStatus | None,
) -> list[FarmTask]:
    """列出当前用户农场内的任务。"""

    with sqlite_manager.session() as session:
        if farm_id is not None:
            _require_owned_farm(session, farm_id=farm_id, user_id=user_id)
        query = (
            session.query(FarmTask)
            .join(Farm, Farm.id == FarmTask.farm_id)
            .filter(Farm.user_id == user_id)
        )
        if farm_id is not None:
            query = query.filter(FarmTask.farm_id == farm_id)
        if status is not None:
            query = query.filter(FarmTask.status == status)
        tasks = query.order_by(FarmTask.created_at.desc(), FarmTask.id.desc()).all()
        for task in tasks:
            session.expunge(task)
        return tasks


def start(*, user_id: int, task_id: str) -> FarmTask:
    """人工开始 pending 或 returned 任务。"""

    with sqlite_manager.session() as session:
        task = _require_owned_task(session, task_id=task_id, user_id=user_id)
        return _transition(
            session,
            task=task,
            target_status="in_progress",
            action="start",
            note="",
        )


def submit(
    *,
    user_id: int,
    task_id: str,
    request: TaskSubmitRequest,
) -> FarmTask:
    """人工提交至少一种执行证据。"""

    with sqlite_manager.session() as session:
        task = _require_owned_task(session, task_id=task_id, user_id=user_id)
        _require_allowed_transition(task.status, "submitted")
        if (
            not request.note.strip()
            and not request.trajectory_file_ids
            and not request.attachment_urls
        ):
            raise AppException(
                status_code=400,
                code="TASK_EVIDENCE_REQUIRED",
                message="提交任务时至少需要说明、轨迹或附件之一",
            )
        _load_task_trajectories(
            session,
            farm_id=task.farm_id,
            trajectory_file_ids=request.trajectory_file_ids,
        )
        return _transition(
            session,
            task=task,
            target_status="submitted",
            action="submit",
            note=request.note,
            execution_changes={
                "note": request.note,
                "trajectory_file_ids": list(request.trajectory_file_ids),
                "attachment_urls": list(request.attachment_urls),
            },
        )


def get_task_evidence(*, user_id: int, task_id: str) -> TaskEvidenceBundle:
    """返回任务目标、执行说明、同农场轨迹和附件。"""

    with sqlite_manager.session() as session:
        task = _require_owned_task(session, task_id=task_id, user_id=user_id)
        execution = dict(task.execution)
        raw_trajectory_ids = execution.get("trajectory_file_ids", [])
        trajectory_file_ids = (
            [item for item in raw_trajectory_ids if isinstance(item, int)]
            if isinstance(raw_trajectory_ids, list)
            else []
        )
        trajectories = _load_task_trajectories(
            session,
            farm_id=task.farm_id,
            trajectory_file_ids=trajectory_file_ids,
        )
        raw_attachment_urls = execution.get("attachment_urls", [])
        attachment_urls = (
            [item for item in raw_attachment_urls if isinstance(item, str)]
            if isinstance(raw_attachment_urls, list)
            else []
        )
        return TaskEvidenceBundle(
            task_id=task.task_id,
            farm_id=task.farm_id,
            field_id=task.field_id,
            title=task.title,
            instructions=task.instructions,
            acceptance_criteria=task.acceptance_criteria,
            status=task.status,
            execution=execution,
            trajectory_files=[
                TrajectoryFileInfo.model_validate(trajectory)
                for trajectory in trajectories
            ],
            attachment_urls=attachment_urls,
        )


def save_verification_draft(
    *,
    user_id: int,
    task_id: str,
    verdict: TaskVerificationDraft,
) -> FarmTask:
    """AI 仅保存 submitted 任务的复核草稿，不改变最终状态。"""

    with sqlite_manager.session() as session:
        task = _require_owned_task(session, task_id=task_id, user_id=user_id)
        if task.status != "submitted":
            _raise_invalid_transition()
        now = datetime.now(timezone.utc)
        verdict_json = json.dumps(
            verdict.model_dump(mode="json"),
            ensure_ascii=False,
        )
        affected_rows = (
            session.query(FarmTask)
            .filter(
                FarmTask.task_id == task.task_id,
                FarmTask.status == "submitted",
            )
            .update(
                {
                    FarmTask.agent_verdict_json: verdict_json,
                    FarmTask.updated_at: now,
                },
                synchronize_session=False,
            )
        )
        if affected_rows != 1:
            _raise_invalid_transition()
        session.expire(task)
        session.refresh(task)
        return _detach_task(session, task)


def complete(*, user_id: int, task_id: str, note: str) -> FarmTask:
    """人工在可接受复核草稿存在时完成 submitted 任务。"""

    with sqlite_manager.session() as session:
        task = _require_owned_task(session, task_id=task_id, user_id=user_id)
        _require_allowed_transition(task.status, "completed")
        if task.agent_verdict.get("verdict") not in {"pass", "manual_review"}:
            raise AppException(
                status_code=409,
                code="TASK_VERIFICATION_REQUIRED",
                message="任务缺少可完成的复核草稿",
            )
        return _transition(
            session,
            task=task,
            target_status="completed",
            action="complete",
            note=note,
            execution_changes={"completion_note": note},
        )


def return_task(*, user_id: int, task_id: str, note: str) -> FarmTask:
    """人工退回 submitted 任务并记录原因。"""

    with sqlite_manager.session() as session:
        task = _require_owned_task(session, task_id=task_id, user_id=user_id)
        if not note.strip():
            raise AppException(
                status_code=400,
                code="TASK_DECISION_NOTE_REQUIRED",
                message="退回任务必须填写原因",
            )
        return _transition(
            session,
            task=task,
            target_status="returned",
            action="return",
            note=note,
            execution_changes={"return_reason": note},
        )


def cancel(*, user_id: int, task_id: str, note: str) -> FarmTask:
    """人工取消仍可取消的任务并记录原因。"""

    with sqlite_manager.session() as session:
        task = _require_owned_task(session, task_id=task_id, user_id=user_id)
        return _transition(
            session,
            task=task,
            target_status="cancelled",
            action="cancel",
            note=note,
            execution_changes={"cancellation_reason": note},
        )
