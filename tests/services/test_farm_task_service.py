from __future__ import annotations

import json
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Query, Session, sessionmaker

from app.core.sqlite import Base, sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmTask
from app.models.trajectory import TrajectoryFile
from app.models.user import User
from app.schemas.farm_agent import (
    TaskEvidenceBundle,
    TaskStatus,
    TaskSubmitRequest,
    TaskVerificationDraft,
)
from app.services import farm_task_service


ALL_STATUSES: tuple[TaskStatus, ...] = (
    "pending",
    "in_progress",
    "submitted",
    "returned",
    "completed",
    "cancelled",
)
EXPECTED_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    "pending": {"in_progress", "cancelled"},
    "in_progress": {"submitted", "cancelled"},
    "submitted": {"completed", "returned"},
    "returned": {"in_progress", "cancelled"},
    "completed": set(),
    "cancelled": set(),
}


@pytest.fixture
def task_database(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[sessionmaker[Session]]:
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(sqlite_manager, "session", test_session)
    yield session_factory
    engine.dispose()


@pytest.fixture
def task_file_database(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'farm-task-cas.db'}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_session() -> Iterator[Session]:
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(sqlite_manager, "session", test_session)
    yield session_factory
    engine.dispose()


def _seed_tasks(session_factory: sessionmaker[Session]) -> dict[str, int | str]:
    with session_factory() as session:
        owner = User(
            username="task-owner",
            email="task-owner@example.com",
            hashed_password="hash",
        )
        other = User(
            username="task-other",
            email="task-other@example.com",
            hashed_password="hash",
        )
        session.add_all([owner, other])
        session.flush()
        farm = Farm(user_id=owner.id, name="自有农场")
        other_owner_farm = Farm(user_id=owner.id, name="自有另一农场")
        foreign_farm = Farm(user_id=other.id, name="他人农场")
        session.add_all([farm, other_owner_farm, foreign_farm])
        session.flush()
        field = Field(farm_id=farm.id, name="A1")
        other_owner_field = Field(farm_id=other_owner_farm.id, name="B1")
        foreign_field = Field(farm_id=foreign_farm.id, name="X1")
        session.add_all([field, other_owner_field, foreign_field])
        session.flush()
        trajectory = TrajectoryFile(field_id=field.id, filename="owned.xlsx")
        other_farm_trajectory = TrajectoryFile(
            field_id=other_owner_field.id,
            filename="wrong-farm.xlsx",
        )
        foreign_trajectory = TrajectoryFile(
            field_id=foreign_field.id,
            filename="foreign.xlsx",
        )
        owner_task = FarmTask(
            task_id="task-owned",
            farm_id=farm.id,
            field_id=field.id,
            title="检查排水沟",
            task_type="drainage",
            instructions="清理堵塞点并提交证据",
            status="pending",
        )
        owner_task.set_acceptance_criteria(["排水畅通", "提交执行证据"])
        foreign_task = FarmTask(
            task_id="task-foreign",
            farm_id=foreign_farm.id,
            field_id=foreign_field.id,
            title="他人任务",
            task_type="inspection",
            instructions="不可披露",
            status="submitted",
        )
        session.add_all(
            [
                trajectory,
                other_farm_trajectory,
                foreign_trajectory,
                owner_task,
                foreign_task,
            ]
        )
        session.commit()
        return {
            "owner_id": owner.id,
            "other_id": other.id,
            "farm_id": farm.id,
            "other_owner_farm_id": other_owner_farm.id,
            "foreign_farm_id": foreign_farm.id,
            "trajectory_id": trajectory.id,
            "other_farm_trajectory_id": other_farm_trajectory.id,
            "foreign_trajectory_id": foreign_trajectory.id,
            "task_id": owner_task.task_id,
            "foreign_task_id": foreign_task.task_id,
        }


def _set_task_state(
    session_factory: sessionmaker[Session],
    *,
    task_id: str,
    status: TaskStatus,
    execution: dict[str, object] | None = None,
    verdict: dict[str, object] | None = None,
) -> None:
    with session_factory() as session:
        task = session.query(FarmTask).filter(FarmTask.task_id == task_id).one()
        task.status = status
        task.set_execution(execution or {})
        task.set_agent_verdict(verdict or {})
        session.commit()


TRANSITION_CASES = [
    (source, target, target in EXPECTED_TRANSITIONS[source])
    for source in ALL_STATUSES
    for target in ALL_STATUSES
]


@pytest.mark.parametrize(
    ("source", "target", "allowed"),
    TRANSITION_CASES,
)
def test_transition_matrix_has_exact_allowed_edges_and_409_complement(
    task_database: sessionmaker[Session],
    source: TaskStatus,
    target: TaskStatus,
    allowed: bool,
) -> None:
    seeded = _seed_tasks(task_database)
    task_id = str(seeded["task_id"])
    _set_task_state(task_database, task_id=task_id, status=source)

    if allowed:
        with sqlite_manager.session() as session:
            task = session.query(FarmTask).filter(FarmTask.task_id == task_id).one()
            transitioned = farm_task_service._transition(
                session,
                task=task,
                target_status=target,
                action=f"matrix:{source}->{target}",
                note="矩阵验证",
            )
        assert transitioned.status == target
        assert transitioned.execution["audit"][-1]["actor"] == "human"
        assert target in farm_task_service.ALLOWED_TRANSITIONS[source]
        return

    with pytest.raises(AppException) as exc_info:
        with sqlite_manager.session() as session:
            task = session.query(FarmTask).filter(FarmTask.task_id == task_id).one()
            farm_task_service._transition(
                session,
                task=task,
                target_status=target,
                action=f"matrix:{source}->{target}",
                note="矩阵验证",
            )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TASK_TRANSITION"
    with task_database() as session:
        persisted = session.query(FarmTask).filter(FarmTask.task_id == task_id).one()
        assert persisted.status == source
        assert persisted.execution == {}


def test_start_submit_complete_preserves_evidence_and_appends_human_audit(
    task_database: sessionmaker[Session],
) -> None:
    seeded = _seed_tasks(task_database)
    user_id = int(seeded["owner_id"])
    task_id = str(seeded["task_id"])

    started = farm_task_service.start(user_id=user_id, task_id=task_id)
    submitted = farm_task_service.submit(
        user_id=user_id,
        task_id=task_id,
        request=TaskSubmitRequest(
            note="已完成清沟",
            trajectory_file_ids=[int(seeded["trajectory_id"])],
            attachment_urls=["https://example.com/evidence/drain.jpg"],
        ),
    )
    drafted = farm_task_service.save_verification_draft(
        user_id=user_id,
        task_id=task_id,
        verdict=TaskVerificationDraft(verdict="pass", note="证据满足验收条件"),
    )
    completed = farm_task_service.complete(
        user_id=user_id,
        task_id=task_id,
        note="人工确认完成",
    )

    assert started.status == "in_progress"
    assert submitted.status == "submitted"
    assert drafted.status == "submitted"
    assert completed.status == "completed"
    assert completed.execution["note"] == "已完成清沟"
    assert completed.execution["trajectory_file_ids"] == [seeded["trajectory_id"]]
    assert completed.execution["attachment_urls"] == [
        "https://example.com/evidence/drain.jpg"
    ]
    audit = completed.execution["audit"]
    assert [entry["action"] for entry in audit] == ["start", "submit", "complete"]
    assert all(entry["actor"] == "human" for entry in audit)
    assert all(datetime.fromisoformat(entry["timestamp"]) for entry in audit)
    assert completed.agent_verdict == {
        "verdict": "pass",
        "note": "证据满足验收条件",
        "evidence_refs": [],
    }


def test_return_restart_and_cancel_keep_submission_and_record_reasons(
    task_database: sessionmaker[Session],
) -> None:
    seeded = _seed_tasks(task_database)
    user_id = int(seeded["owner_id"])
    task_id = str(seeded["task_id"])
    evidence = {
        "note": "初次提交",
        "trajectory_file_ids": [int(seeded["trajectory_id"])],
        "attachment_urls": [],
        "audit": [],
    }
    _set_task_state(
        task_database,
        task_id=task_id,
        status="submitted",
        execution=evidence,
    )

    returned = farm_task_service.return_task(
        user_id=user_id,
        task_id=task_id,
        note="照片角度不足",
    )
    restarted = farm_task_service.start(user_id=user_id, task_id=task_id)
    cancelled = farm_task_service.cancel(
        user_id=user_id,
        task_id=task_id,
        note="天气变化取消作业",
    )

    assert returned.execution["return_reason"] == "照片角度不足"
    assert restarted.execution["trajectory_file_ids"] == [seeded["trajectory_id"]]
    assert cancelled.execution["cancellation_reason"] == "天气变化取消作业"
    assert [entry["action"] for entry in cancelled.execution["audit"]] == [
        "return",
        "start",
        "cancel",
    ]


@pytest.mark.parametrize("status", ["pending", "in_progress", "returned"])
def test_cancel_supports_every_allowed_source(
    task_database: sessionmaker[Session],
    status: TaskStatus,
) -> None:
    seeded = _seed_tasks(task_database)
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status=status,
    )

    task = farm_task_service.cancel(
        user_id=int(seeded["owner_id"]),
        task_id=str(seeded["task_id"]),
        note="人工取消",
    )

    assert task.status == "cancelled"


@pytest.mark.parametrize(
    "submit_request",
    [
        TaskSubmitRequest(note="", trajectory_file_ids=[], attachment_urls=[]),
        TaskSubmitRequest(note="   ", trajectory_file_ids=[], attachment_urls=[]),
    ],
)
def test_submit_requires_note_trajectory_or_attachment(
    task_database: sessionmaker[Session],
    submit_request: TaskSubmitRequest,
) -> None:
    seeded = _seed_tasks(task_database)
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status="in_progress",
    )

    with pytest.raises(AppException) as exc_info:
        farm_task_service.submit(
            user_id=int(seeded["owner_id"]),
            task_id=str(seeded["task_id"]),
            request=submit_request,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "TASK_EVIDENCE_REQUIRED"


@pytest.mark.parametrize(
    "url",
    [
        "not-a-url",
        "ftp://example.com/evidence.jpg",
        "file:///tmp/evidence.jpg",
        "https:///missing-host.jpg",
        "https://exa mple.com/evidence.jpg",
        "https://example.com:bad/evidence.jpg",
    ],
)
def test_submit_schema_rejects_non_http_attachment_urls(url: str) -> None:
    with pytest.raises(ValidationError):
        TaskSubmitRequest(note="", trajectory_file_ids=[], attachment_urls=[url])


@pytest.mark.parametrize(
    "trajectory_key",
    ["other_farm_trajectory_id", "foreign_trajectory_id", "missing"],
)
def test_submit_rejects_missing_or_wrong_farm_trajectory_without_disclosure(
    task_database: sessionmaker[Session],
    trajectory_key: str,
) -> None:
    seeded = _seed_tasks(task_database)
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status="in_progress",
    )
    trajectory_id = (
        999_999 if trajectory_key == "missing" else int(seeded[trajectory_key])
    )

    with pytest.raises(AppException) as exc_info:
        farm_task_service.submit(
            user_id=int(seeded["owner_id"]),
            task_id=str(seeded["task_id"]),
            request=TaskSubmitRequest(
                note="",
                trajectory_file_ids=[trajectory_id],
                attachment_urls=[],
            ),
        )

    assert exc_info.value.status_code == 403
    assert "农场" not in exc_info.value.message


def test_get_task_evidence_returns_task_goal_and_owned_trajectory_metadata(
    task_database: sessionmaker[Session],
) -> None:
    seeded = _seed_tasks(task_database)
    execution = {
        "note": "已清沟",
        "trajectory_file_ids": [int(seeded["trajectory_id"])],
        "attachment_urls": ["https://example.com/photo.jpg"],
        "audit": [],
    }
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status="submitted",
        execution=execution,
    )

    bundle = farm_task_service.get_task_evidence(
        user_id=int(seeded["owner_id"]),
        task_id=str(seeded["task_id"]),
    )

    assert isinstance(bundle, TaskEvidenceBundle)
    assert bundle.task_id == seeded["task_id"]
    assert bundle.instructions == "清理堵塞点并提交证据"
    assert bundle.acceptance_criteria == ["排水畅通", "提交执行证据"]
    assert bundle.execution == execution
    assert [trajectory.id for trajectory in bundle.trajectory_files] == [
        seeded["trajectory_id"]
    ]
    assert bundle.attachment_urls == ["https://example.com/photo.jpg"]


@pytest.mark.parametrize(
    "status",
    ["pending", "in_progress", "returned", "completed", "cancelled"],
)
def test_verification_draft_only_saves_while_submitted(
    task_database: sessionmaker[Session],
    status: TaskStatus,
) -> None:
    seeded = _seed_tasks(task_database)
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status=status,
    )

    with pytest.raises(AppException) as exc_info:
        farm_task_service.save_verification_draft(
            user_id=int(seeded["owner_id"]),
            task_id=str(seeded["task_id"]),
            verdict=TaskVerificationDraft(verdict="pass", note="不得保存"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TASK_TRANSITION"


def test_verification_draft_updates_only_verdict_and_never_status_or_execution(
    task_database: sessionmaker[Session],
) -> None:
    seeded = _seed_tasks(task_database)
    execution = {"note": "现场已完成", "audit": [{"existing": True}]}
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status="submitted",
        execution=execution,
    )

    result = farm_task_service.save_verification_draft(
        user_id=int(seeded["owner_id"]),
        task_id=str(seeded["task_id"]),
        verdict=TaskVerificationDraft(
            verdict="manual_review",
            note="需要人工查看原始照片",
            evidence_refs=["attachment:0"],
        ),
    )

    assert result.status == "submitted"
    assert result.execution == execution
    assert result.agent_verdict["verdict"] == "manual_review"


@pytest.mark.parametrize("verdict", [{}, {"verdict": "needs_evidence"}, {"verdict": "rework"}])
def test_complete_requires_pass_or_manual_review_draft(
    task_database: sessionmaker[Session],
    verdict: dict[str, object],
) -> None:
    seeded = _seed_tasks(task_database)
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status="submitted",
        verdict=verdict,
    )

    with pytest.raises(AppException) as exc_info:
        farm_task_service.complete(
            user_id=int(seeded["owner_id"]),
            task_id=str(seeded["task_id"]),
            note="人工完成",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "TASK_VERIFICATION_REQUIRED"


@pytest.mark.parametrize("verdict", ["pass", "manual_review"])
def test_complete_accepts_human_approved_verdicts(
    task_database: sessionmaker[Session],
    verdict: str,
) -> None:
    seeded = _seed_tasks(task_database)
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status="submitted",
        verdict={"verdict": verdict, "note": "草稿"},
    )

    result = farm_task_service.complete(
        user_id=int(seeded["owner_id"]),
        task_id=str(seeded["task_id"]),
        note="人工最终确认",
    )

    assert result.status == "completed"


@pytest.mark.parametrize("note", ["", "   "])
def test_return_requires_a_non_blank_human_reason(
    task_database: sessionmaker[Session],
    note: str,
) -> None:
    seeded = _seed_tasks(task_database)
    _set_task_state(
        task_database,
        task_id=str(seeded["task_id"]),
        status="submitted",
    )

    with pytest.raises(AppException) as exc_info:
        farm_task_service.return_task(
            user_id=int(seeded["owner_id"]),
            task_id=str(seeded["task_id"]),
            note=note,
        )

    assert exc_info.value.status_code == 400
    assert exc_info.value.code == "TASK_DECISION_NOTE_REQUIRED"


def test_list_tasks_filters_only_owned_farms_and_validates_requested_farm(
    task_database: sessionmaker[Session],
) -> None:
    seeded = _seed_tasks(task_database)

    tasks = farm_task_service.list_tasks(
        user_id=int(seeded["owner_id"]),
        farm_id=int(seeded["farm_id"]),
        status="pending",
    )

    assert [task.task_id for task in tasks] == [seeded["task_id"]]
    for farm_id in (int(seeded["foreign_farm_id"]), 999_999):
        with pytest.raises(AppException) as exc_info:
            farm_task_service.list_tasks(
                user_id=int(seeded["owner_id"]),
                farm_id=farm_id,
                status=None,
            )
        assert exc_info.value.status_code == 403


def _foreign_service_calls(
    *,
    user_id: int,
    task_id: str,
) -> list[Callable[[], object]]:
    return [
        lambda: farm_task_service.start(user_id=user_id, task_id=task_id),
        lambda: farm_task_service.submit(
            user_id=user_id,
            task_id=task_id,
            request=TaskSubmitRequest(note="证据", trajectory_file_ids=[], attachment_urls=[]),
        ),
        lambda: farm_task_service.get_task_evidence(user_id=user_id, task_id=task_id),
        lambda: farm_task_service.save_verification_draft(
            user_id=user_id,
            task_id=task_id,
            verdict=TaskVerificationDraft(verdict="pass", note="草稿"),
        ),
        lambda: farm_task_service.complete(user_id=user_id, task_id=task_id, note="完成"),
        lambda: farm_task_service.return_task(user_id=user_id, task_id=task_id, note="退回"),
        lambda: farm_task_service.cancel(user_id=user_id, task_id=task_id, note="取消"),
    ]


@pytest.mark.parametrize("task_key", ["foreign_task_id", "missing"])
def test_all_owner_scoped_task_operations_return_non_disclosing_403(
    task_database: sessionmaker[Session],
    task_key: str,
) -> None:
    seeded = _seed_tasks(task_database)
    task_id = "task-missing" if task_key == "missing" else str(seeded[task_key])

    for call in _foreign_service_calls(
        user_id=int(seeded["owner_id"]),
        task_id=task_id,
    ):
        with pytest.raises(AppException) as exc_info:
            call()
        assert exc_info.value.status_code == 403
        assert exc_info.value.code == "FORBIDDEN"
        assert "他人任务" not in exc_info.value.message


def test_return_checks_task_ownership_before_validating_reason(
    task_database: sessionmaker[Session],
) -> None:
    seeded = _seed_tasks(task_database)

    with pytest.raises(AppException) as exc_info:
        farm_task_service.return_task(
            user_id=int(seeded["owner_id"]),
            task_id="task-missing",
            note="",
        )

    assert exc_info.value.status_code == 403
    assert exc_info.value.code == "FORBIDDEN"


def test_compare_and_set_prevents_double_transition_and_keeps_winner_audit(
    task_file_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_tasks(task_file_database)
    task_id = str(seeded["task_id"])
    original_update = Query.update
    injected: list[bool] = []

    def update_after_competitor(
        query: Query[object],
        values: object,
        *args: object,
        **kwargs: object,
    ) -> int:
        if not injected:
            injected.append(True)
            winner_time = datetime.now(timezone.utc).isoformat()
            with task_file_database() as competing_session:
                affected = original_update(
                    competing_session.query(FarmTask).filter(
                        FarmTask.task_id == task_id,
                        FarmTask.status == "pending",
                    ),
                        {
                            FarmTask.status: "in_progress",
                            FarmTask.execution_json: json.dumps(
                                {
                                    "audit": [
                                        {
                                            "actor": "human",
                                            "action": "winner",
                                            "note": "并发赢家",
                                            "timestamp": winner_time,
                                        }
                                    ]
                                },
                                ensure_ascii=False,
                            ),
                        FarmTask.updated_at: datetime.now(timezone.utc),
                    },
                    synchronize_session=False,
                )
                assert affected == 1
                competing_session.commit()
        return original_update(query, values, *args, **kwargs)

    monkeypatch.setattr(Query, "update", update_after_competitor)

    with pytest.raises(AppException) as exc_info:
        farm_task_service.start(
            user_id=int(seeded["owner_id"]),
            task_id=task_id,
        )

    assert injected == [True]
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_TASK_TRANSITION"
    with task_file_database() as session:
        persisted = session.query(FarmTask).filter(FarmTask.task_id == task_id).one()
        assert persisted.status == "in_progress"
        assert persisted.execution["audit"][0]["action"] == "winner"
