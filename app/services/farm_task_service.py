"""农场执行任务状态机、执行证据和复核草稿服务。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import NoReturn

from pydantic import ValidationError
from sqlalchemy import LargeBinary, cast, literal
from sqlalchemy.orm import Session
from sqlalchemy.sql.elements import ColumnElement

from app.core.sqlite import sqlite_manager
from app.exceptions import AppException, ForbiddenError, ServiceError
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmEvent, FarmTask
from app.models.trajectory import TrajectoryFile
from app.schemas.farm_agent import (
    TaskEvidenceBundle,
    TaskExecution,
    TaskExecutionAction,
    TaskExecutionAuditEntry,
    TaskStatus,
    TaskSubmissionEvidence,
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

# FarmTask.task_type → FarmEvent.event_type 映射
# 未知类型降级为 scouting（巡田），保证事件流可记录
_TASK_TYPE_TO_EVENT_TYPE: dict[str, str] = {
    "spraying": "spraying",
    "pest_control": "spraying",
    "fertilizing": "fertilizing",
    "fertilize": "fertilizing",
    "irrigating": "irrigating",
    "irrigate": "irrigating",
    "drainage": "irrigating",  # 排水归为灌溉类事件
    "scouting": "scouting",
    "harvest": "harvest",
    "seeding": "seeding",
}


def _map_task_type_to_event_type(task_type: str) -> str:
    """把 FarmTask.task_type 映射到 FarmEvent.event_type."""
    normalized = (task_type or "").strip().lower()
    return _TASK_TYPE_TO_EVENT_TYPE.get(normalized, "scouting")


def _resolve_current_season_id(
    session: Session,
    *,
    field_id: int | None,
) -> int | None:
    """读取 Field.current_season_id 指针，让事件关联当前茬次."""
    if field_id is None:
        return None
    field = session.query(Field).filter(Field.id == field_id).first()
    return field.current_season_id if field is not None else None


def _extract_inputs_from_execution(execution: TaskExecution) -> list[dict]:
    """从执行记录提取投入品清单（用于事件溯源）.

    当前 TaskExecution schema 没有专门 inputs 字段，
    暂时从 note 和 attachment_urls 推导简化结构，未来可扩展为结构化投入品表。
    """
    inputs: list[dict] = []
    if execution.note.strip():
        inputs.append({"material": "note", "detail": execution.note.strip()})
    for url in execution.attachment_urls:
        inputs.append({"material": "attachment", "url": url})
    return inputs


def _maybe_record_completion_event(
    session: Session,
    *,
    task: FarmTask,
    actor_user_id: int,
    note: str,
    execution: TaskExecution,
) -> None:
    """任务完成时自动写入 FarmEvent（source=task_completion）.

    幂等：uq_event_task_type (related_task_id, event_type) 约束保证不重复。
    无关联地块（field_id is None）的任务不写事件。
    """
    if task.field_id is None:
        return

    event_type = _map_task_type_to_event_type(task.task_type)
    related_task_id = task.task_id

    # 防御性检查：若已存在同 (related_task_id, event_type) 事件则跳过
    existing = (
        session.query(FarmEvent)
        .filter(
            FarmEvent.related_task_id == related_task_id,
            FarmEvent.event_type == event_type,
        )
        .first()
    )
    if existing is not None:
        return

    season_id = _resolve_current_season_id(session, field_id=task.field_id)
    event = FarmEvent(
        field_id=task.field_id,
        season_id=season_id,
        event_type=event_type,
        event_time=datetime.now(timezone.utc),
        operator=f"user:{actor_user_id}",
        source="task_completion",
        related_task_id=related_task_id,
        note=note or task.title,
    )
    event.set_inputs(_extract_inputs_from_execution(execution))
    session.add(event)


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


def _audit_entry(
    *,
    action: TaskExecutionAction,
    note: str,
    timestamp: datetime,
) -> TaskExecutionAuditEntry:
    return TaskExecutionAuditEntry(
        actor="human",
        action=action,
        note=note,
        timestamp=timestamp,
    )


def _load_task_execution(task: FarmTask) -> TaskExecution:
    try:
        raw_execution = task.execution_json
        return TaskExecution.model_validate_json(
            "{}" if raw_execution is None else raw_execution
        )
    except ValidationError as exc:
        raise ServiceError(
            code="INVALID_TASK_EXECUTION_DATA",
            message="任务执行数据格式无效",
        ) from exc


def _exact_verdict_snapshot_predicate(snapshot: str) -> ColumnElement[bool]:
    """用二进制 cast 绕过数据库文本 collation，比较原始 verdict 快照。"""

    return cast(FarmTask.agent_verdict_json, LargeBinary) == cast(
        literal(snapshot),
        LargeBinary,
    )


def _transition(
    session: Session,
    *,
    task: FarmTask,
    target_status: TaskStatus,
    action: TaskExecutionAction,
    note: str,
    submission: TaskSubmissionEvidence | None = None,
    completion_note: str | None = None,
    return_reason: str | None = None,
    cancellation_reason: str | None = None,
    expected_agent_verdict_json: str | None = None,
    actor_user_id: int | None = None,
) -> FarmTask:
    """用来源状态 CAS 完成人工转换并追加审计记录。

    当 target_status == "completed" 且 actor_user_id 不为空时，
    自动写入 FarmEvent（source=task_completion）形成不可变事件记忆。
    """

    source_status: TaskStatus = task.status
    _require_allowed_transition(source_status, target_status)
    now = datetime.now(timezone.utc)
    previous_execution = _load_task_execution(task)
    execution = TaskExecution(
        note=(submission.note if submission is not None else previous_execution.note),
        trajectory_file_ids=(
            list(submission.trajectory_file_ids)
            if submission is not None
            else list(previous_execution.trajectory_file_ids)
        ),
        attachment_urls=(
            list(submission.attachment_urls)
            if submission is not None
            else list(previous_execution.attachment_urls)
        ),
        audit=[
            *previous_execution.audit,
            _audit_entry(action=action, note=note, timestamp=now),
        ],
        completion_note=(
            completion_note
            if completion_note is not None
            else previous_execution.completion_note
        ),
        return_reason=(
            return_reason
            if return_reason is not None
            else previous_execution.return_reason
        ),
        cancellation_reason=(
            cancellation_reason
            if cancellation_reason is not None
            else previous_execution.cancellation_reason
        ),
    )
    execution_json = json.dumps(
        execution.model_dump(mode="json", exclude_defaults=True),
        ensure_ascii=False,
    )

    transition_query = (
        session.query(FarmTask)
        .filter(
            FarmTask.task_id == task.task_id,
            FarmTask.status == source_status,
        )
    )
    if expected_agent_verdict_json is not None:
        transition_query = transition_query.filter(
            _exact_verdict_snapshot_predicate(expected_agent_verdict_json)
        )
    affected_rows = transition_query.update(
        {
            FarmTask.status: target_status,
            FarmTask.execution_json: execution_json,
            FarmTask.updated_at: now,
        },
        synchronize_session=False,
    )
    if affected_rows != 1:
        _raise_invalid_transition()

    # 任务完成时自动写 FarmEvent，形成 AI 可引用的"记忆"
    if target_status == "completed" and actor_user_id is not None:
        _maybe_record_completion_event(
            session,
            task=task,
            actor_user_id=actor_user_id,
            note=note,
            execution=execution,
        )

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
            submission=request,
        )


def get_task_evidence(*, user_id: int, task_id: str) -> TaskEvidenceBundle:
    """返回任务目标、执行说明、同农场轨迹和附件。"""

    with sqlite_manager.session() as session:
        task = _require_owned_task(session, task_id=task_id, user_id=user_id)
        execution = _load_task_execution(task)
        trajectories = _load_task_trajectories(
            session,
            farm_id=task.farm_id,
            trajectory_file_ids=execution.trajectory_file_ids,
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
            attachment_urls=execution.attachment_urls,
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
    """人工在可接受复核草稿存在时完成 submitted 任务.

    完成时自动写入 FarmEvent（source=task_completion），让 AI 下次巡检有"记忆"。
    """

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
            completion_note=note,
            expected_agent_verdict_json=task.agent_verdict_json,
            actor_user_id=user_id,
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
            return_reason=note,
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
            cancellation_reason=note,
        )
