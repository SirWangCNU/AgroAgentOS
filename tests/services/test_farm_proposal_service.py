"""Farm Agent 提案幂等与人工审批边界测试。"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, sessionmaker

from app.core.sqlite import AgentRun, Base, sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmActionProposal, FarmTask
from app.models.user import User
from app.schemas.farm_agent import (
    EvidenceFactKind,
    FarmEvidence,
    ProposalApprovalRequest,
    ProposalDraft,
    ProposalRejectRequest,
    ProposedAction,
    TaskPriority,
)
from app.services import farm_proposal_service


@pytest.fixture
def proposal_database(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    """让服务通过真实 SQLite 约束执行事务。"""

    engine = create_engine("sqlite:///:memory:")

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(
        dbapi_connection: sqlite3.Connection,
        _record: object,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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
def proposal_file_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> sessionmaker[Session]:
    """为重叠决策测试提供独立连接的文件 SQLite。"""

    database_path = tmp_path / "proposal-cas.db"
    engine = create_engine(
        f"sqlite:///{database_path}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def configure_sqlite(
        dbapi_connection: sqlite3.Connection,
        _record: object,
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.close()

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


def _seed_farms(session_factory: sessionmaker[Session]) -> dict[str, int | str]:
    with session_factory() as session:
        owner = User(
            username="proposal-owner",
            email="proposal-owner@example.com",
            hashed_password="hash",
        )
        other = User(
            username="proposal-other",
            email="proposal-other@example.com",
            hashed_password="hash",
        )
        session.add_all([owner, other])
        session.flush()

        owned_farm = Farm(user_id=owner.id, name="不可泄露的提案农场")
        other_farm = Farm(user_id=other.id, name="其他用户农场")
        session.add_all([owned_farm, other_farm])
        session.flush()

        owned_field = Field(farm_id=owned_farm.id, name="本农场地块")
        other_field = Field(farm_id=other_farm.id, name="其他农场地块")
        session.add_all([owned_field, other_field])
        session.flush()

        owner_run = AgentRun(
            run_id="proposal-run-owner",
            user_id=owner.id,
            farm_id=owned_farm.id,
            run_type="farm_inspection",
        )
        other_run = AgentRun(
            run_id="proposal-run-other",
            user_id=other.id,
            farm_id=other_farm.id,
            run_type="farm_inspection",
        )
        wrong_user_run = AgentRun(
            run_id="proposal-run-wrong-user",
            user_id=other.id,
            farm_id=owned_farm.id,
            run_type="farm_inspection",
        )
        wrong_farm_run = AgentRun(
            run_id="proposal-run-wrong-farm",
            user_id=owner.id,
            farm_id=other_farm.id,
            run_type="farm_inspection",
        )
        session.add_all(
            [owner_run, other_run, wrong_user_run, wrong_farm_run]
        )
        session.commit()
        return {
            "owner_id": owner.id,
            "other_id": other.id,
            "farm_id": owned_farm.id,
            "farm_name": owned_farm.name,
            "other_farm_id": other_farm.id,
            "field_id": owned_field.id,
            "other_field_id": other_field.id,
            "run_id": owner_run.run_id,
            "other_run_id": other_run.run_id,
            "wrong_user_run_id": wrong_user_run.run_id,
            "wrong_farm_run_id": wrong_farm_run.run_id,
        }


def _evidence(*, fact_kind: EvidenceFactKind = "rule") -> FarmEvidence:
    return FarmEvidence(
        source_type="weather_forecast",
        source_id="forecast-2026-07-19",
        summary="首个预报日降雨达到排水风险阈值",
        observed_at=datetime(2026, 7, 18, 8, tzinfo=timezone.utc),
        fact_kind=fact_kind,
        payload={"precipitation_mm": 60.0},
    )


def _action(
    action_key: str,
    *,
    title: str | None = None,
    priority: TaskPriority = "normal",
) -> ProposedAction:
    return ProposedAction(
        action_key=action_key,
        title=title or f"任务 {action_key}",
        task_type="drainage",
        instructions=f"执行 {action_key}",
        priority=priority,
        assignee_name="值班员",
        acceptance_criteria=["上传现场照片", "确认排水畅通"],
    )


def _draft(
    *,
    risk_key: str = "weather.rainstorm_drainage",
    action: ProposedAction | None = None,
) -> ProposalDraft:
    return ProposalDraft(
        risk_key=risk_key,
        title="暴雨排水风险",
        severity="high",
        summary="需要人工确认排水巡查安排",
        confidence=0.9,
        evidence=[_evidence()],
        actions=[action or _action("draft-action")],
    )


def _create_proposal(seeded: dict[str, int | str]) -> FarmActionProposal:
    return farm_proposal_service.create_pending_proposal(
        user_id=int(seeded["owner_id"]),
        farm_id=int(seeded["farm_id"]),
        run_id=str(seeded["run_id"]),
        draft=_draft(),
    )


def _integrity_error(message: str) -> IntegrityError:
    return IntegrityError(
        "INSERT",
        {},
        sqlite3.IntegrityError(message),
    )


def _inject_competing_decision_before_cas(
    monkeypatch: pytest.MonkeyPatch,
    session_factory: sessionmaker[Session],
    *,
    proposal_id: str,
    winner_status: str,
    winner_note: str,
    farm_id: int,
) -> list[bool]:
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
            with session_factory() as competing_session:
                affected = original_update(
                    competing_session.query(FarmActionProposal).filter(
                        FarmActionProposal.proposal_id == proposal_id,
                        FarmActionProposal.status == "pending",
                    ),
                    {
                        FarmActionProposal.status: winner_status,
                        FarmActionProposal.decision_note: winner_note,
                        FarmActionProposal.decided_at: datetime.now(timezone.utc),
                    },
                    synchronize_session=False,
                )
                assert affected == 1
                if winner_status == "approved":
                    task = FarmTask(
                        task_id="task-competing-winner",
                        proposal_id=proposal_id,
                        action_key="winner-action",
                        farm_id=farm_id,
                        title="并发赢家任务",
                        task_type="drainage",
                        instructions="只保留赢家任务",
                        status="pending",
                    )
                    task.set_acceptance_criteria(["赢家验收条件"])
                    competing_session.add(task)
                competing_session.commit()
        return original_update(query, values, *args, **kwargs)

    monkeypatch.setattr(Query, "update", update_after_competitor)
    return injected


def test_create_pending_proposal_persists_typed_draft_as_pending(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)

    proposal = _create_proposal(seeded)

    assert proposal.status == "pending"
    assert proposal.created_by == seeded["owner_id"]
    assert proposal.evidence[0]["fact_kind"] == "rule"
    assert proposal.actions[0]["action_key"] == "draft-action"
    expected_fingerprint = hashlib.sha256(
        f'{seeded["farm_id"]}:weather.rainstorm_drainage'.encode()
    ).hexdigest()
    assert proposal.risk_fingerprint == expected_fingerprint
    with proposal_database() as session:
        assert session.query(FarmActionProposal).count() == 1


def test_create_pending_proposal_retry_returns_same_database_row(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)

    first = _create_proposal(seeded)
    retried = _create_proposal(seeded)

    assert retried.proposal_id == first.proposal_id
    with proposal_database() as session:
        assert session.query(FarmActionProposal).count() == 1


@pytest.mark.parametrize(
    "run_key",
    [
        "other_run_id",
        "wrong_user_run_id",
        "wrong_farm_run_id",
        "missing",
    ],
)
def test_create_requires_run_owned_by_same_user_and_farm(
    proposal_database: sessionmaker[Session],
    run_key: str,
) -> None:
    seeded = _seed_farms(proposal_database)
    run_id = (
        "missing-run"
        if run_key == "missing"
        else str(seeded[run_key])
    )

    with pytest.raises(AppException) as exc_info:
        farm_proposal_service.create_pending_proposal(
            user_id=int(seeded["owner_id"]),
            farm_id=int(seeded["farm_id"]),
            run_id=run_id,
            draft=_draft(risk_key=f"run-check:{run_key}"),
        )

    assert exc_info.value.status_code == 403
    with proposal_database() as session:
        assert session.query(FarmActionProposal).count() == 0


def test_create_retry_recovers_from_composite_unique_constraint_race(
    proposal_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_farms(proposal_database)
    original = _create_proposal(seeded)
    original_first = Query.first
    hid_business_key_once = False

    def hide_first_proposal_lookup(query: Query[object]) -> object | None:
        nonlocal hid_business_key_once
        entity = query.column_descriptions[0].get("entity")
        if entity is FarmActionProposal and not hid_business_key_once:
            hid_business_key_once = True
            return None
        return original_first(query)

    monkeypatch.setattr(Query, "first", hide_first_proposal_lookup)

    retried = _create_proposal(seeded)

    assert hid_business_key_once is True
    assert retried.proposal_id == original.proposal_id
    with proposal_database() as session:
        assert session.query(FarmActionProposal).count() == 1


@pytest.mark.parametrize(
    ("message", "constraint_name", "sqlite_columns"),
    [
        (
            "UNIQUE constraint failed: farm_action_proposals.run_id, "
            "farm_action_proposals.risk_fingerprint",
            "uq_proposal_run_risk",
            (
                "farm_action_proposals.run_id",
                "farm_action_proposals.risk_fingerprint",
            ),
        ),
        (
            "Duplicate entry 'run:risk' for key 'uq_proposal_run_risk'",
            "uq_proposal_run_risk",
            (
                "farm_action_proposals.run_id",
                "farm_action_proposals.risk_fingerprint",
            ),
        ),
        (
            "UNIQUE constraint failed: farm_tasks.proposal_id, "
            "farm_tasks.action_key",
            "uq_task_proposal_action",
            ("farm_tasks.proposal_id", "farm_tasks.action_key"),
        ),
        (
            "Duplicate entry 'proposal:action' for key "
            "'uq_task_proposal_action'",
            "uq_task_proposal_action",
            ("farm_tasks.proposal_id", "farm_tasks.action_key"),
        ),
    ],
)
def test_integrity_classifier_accepts_only_named_business_unique_constraints(
    message: str,
    constraint_name: str,
    sqlite_columns: tuple[str, ...],
) -> None:
    assert farm_proposal_service._is_unique_constraint_violation(
        _integrity_error(message),
        constraint_name=constraint_name,
        sqlite_columns=sqlite_columns,
    )


@pytest.mark.parametrize(
    "message",
    [
        "FOREIGN KEY constraint failed",
        "UNIQUE constraint failed: farm_action_proposals.proposal_id",
        (
            "UNIQUE constraint failed: farm_action_proposals.run_id, "
            "farm_action_proposals.risk_fingerprint, "
            "farm_action_proposals.proposal_id"
        ),
        "Duplicate entry 'x' for key 'ix_farm_action_proposals_proposal_id'",
        "Duplicate entry 'x' for key 'uq_proposal_run_risk_shadow'",
    ],
)
def test_integrity_classifier_rejects_unrelated_failures(message: str) -> None:
    assert not farm_proposal_service._is_unique_constraint_violation(
        _integrity_error(message),
        constraint_name="uq_proposal_run_risk",
        sqlite_columns=(
            "farm_action_proposals.run_id",
            "farm_action_proposals.risk_fingerprint",
        ),
    )


def test_create_does_not_swallow_unrelated_error_when_matching_row_appears(
    proposal_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_farms(proposal_database)
    _create_proposal(seeded)
    original_first = Query.first
    hid_business_key_once = False

    def hide_first_proposal_lookup(query: Query[object]) -> object | None:
        nonlocal hid_business_key_once
        entity = query.column_descriptions[0].get("entity")
        if entity is FarmActionProposal and not hid_business_key_once:
            hid_business_key_once = True
            return None
        return original_first(query)

    monkeypatch.setattr(Query, "first", hide_first_proposal_lookup)
    original_flush = Session.flush
    raised_unrelated_error = False

    def fail_first_flush(
        session: Session,
        objects: object | None = None,
    ) -> None:
        nonlocal raised_unrelated_error
        if not raised_unrelated_error and any(
            isinstance(item, FarmActionProposal) for item in session.new
        ):
            raised_unrelated_error = True
            raise _integrity_error("FOREIGN KEY constraint failed")
        original_flush(session, objects=objects)

    monkeypatch.setattr(Session, "flush", fail_first_flush)

    with pytest.raises(IntegrityError, match="FOREIGN KEY constraint failed"):
        _create_proposal(seeded)


def test_create_propagates_unrelated_integrity_error(
    proposal_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_farms(proposal_database)
    original = _create_proposal(seeded)
    colliding_uuid = UUID(hex=original.proposal_id.removeprefix("proposal-"))
    with proposal_database() as session:
        session.add(
            AgentRun(
                run_id="proposal-run-owner-second",
                user_id=int(seeded["owner_id"]),
                farm_id=int(seeded["farm_id"]),
                run_type="farm_inspection",
            )
        )
        session.commit()
    monkeypatch.setattr(farm_proposal_service.uuid, "uuid4", lambda: colliding_uuid)

    with pytest.raises(IntegrityError):
        farm_proposal_service.create_pending_proposal(
            user_id=int(seeded["owner_id"]),
            farm_id=int(seeded["farm_id"]),
            run_id="proposal-run-owner-second",
            draft=_draft(risk_key="different-business-key"),
        )

    with proposal_database() as session:
        assert session.query(FarmActionProposal).count() == 1


def test_high_confidence_inference_only_draft_is_rejected_before_database_write(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)

    with pytest.raises(ValidationError):
        ProposalDraft(
            risk_key="weather.inference-only",
            title="推断风险",
            severity="high",
            summary="没有观测或规则证据",
            confidence=0.9,
            evidence=[_evidence(fact_kind="inference")],
            actions=[_action("inspect")],
        )

    with proposal_database() as session:
        assert session.query(FarmActionProposal).count() == 0


def test_approve_uses_human_confirmed_actions_instead_of_draft_actions(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)
    confirmed_action = _action(
        "human-confirmed",
        title="人工调整后的任务",
        priority="urgent",
    ).model_copy(update={"field_id": int(seeded["field_id"])})

    approved, tasks = farm_proposal_service.approve(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=ProposalApprovalRequest(
            actions=[confirmed_action],
            decision_note="已调整执行人和优先级",
        ),
    )

    assert approved.status == "approved"
    assert approved.decision_note == "已调整执行人和优先级"
    assert approved.decided_at is not None
    assert len(tasks) == 1
    assert tasks[0].action_key == "human-confirmed"
    assert tasks[0].title == "人工调整后的任务"
    assert tasks[0].priority == "urgent"
    assert tasks[0].acceptance_criteria == ["上传现场照片", "确认排水畅通"]


def test_duplicate_approval_returns_original_tasks_without_inserting_again(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)
    original_request = ProposalApprovalRequest(
        actions=[_action("check-drain"), _action("prepare-pump")],
        decision_note="批准",
    )
    _, original_tasks = farm_proposal_service.approve(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=original_request,
    )

    retried_proposal, retried_tasks = farm_proposal_service.approve(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=ProposalApprovalRequest(
            actions=[_action("different-retry-action")],
            decision_note="重复请求不应覆盖原决定",
        ),
    )

    assert retried_proposal.status == "approved"
    assert {task.task_id for task in retried_tasks} == {
        task.task_id for task in original_tasks
    }
    assert {task.action_key for task in retried_tasks} == {
        "check-drain",
        "prepare-pump",
    }
    with proposal_database() as session:
        assert session.query(FarmTask).count() == 2


def test_overlapping_approve_loser_returns_only_committed_winner_tasks(
    proposal_file_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_farms(proposal_file_database)
    proposal = _create_proposal(seeded)
    injected = _inject_competing_decision_before_cas(
        monkeypatch,
        proposal_file_database,
        proposal_id=proposal.proposal_id,
        winner_status="approved",
        winner_note="并发赢家批准",
        farm_id=int(seeded["farm_id"]),
    )

    approved, tasks = farm_proposal_service.approve(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=ProposalApprovalRequest(
            actions=[_action("loser-disjoint-action")],
            decision_note="并发输家不得覆盖",
        ),
    )

    assert injected == [True]
    assert approved.status == "approved"
    assert approved.decision_note == "并发赢家批准"
    assert {task.action_key for task in tasks} == {"winner-action"}
    with proposal_file_database() as session:
        assert session.query(FarmTask).count() == 1


def test_overlapping_approve_loses_to_reject_with_409_and_no_tasks(
    proposal_file_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_farms(proposal_file_database)
    proposal = _create_proposal(seeded)
    injected = _inject_competing_decision_before_cas(
        monkeypatch,
        proposal_file_database,
        proposal_id=proposal.proposal_id,
        winner_status="rejected",
        winner_note="并发拒绝获胜",
        farm_id=int(seeded["farm_id"]),
    )

    with pytest.raises(AppException) as exc_info:
        farm_proposal_service.approve(
            user_id=int(seeded["owner_id"]),
            proposal_id=proposal.proposal_id,
            request=ProposalApprovalRequest(
                actions=[_action("loser-action")],
                decision_note="输家批准",
            ),
        )

    assert injected == [True]
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_PROPOSAL_TRANSITION"
    with proposal_file_database() as session:
        persisted = (
            session.query(FarmActionProposal)
            .filter(FarmActionProposal.proposal_id == proposal.proposal_id)
            .one()
        )
        assert persisted.status == "rejected"
        assert persisted.decision_note == "并发拒绝获胜"
        assert session.query(FarmTask).count() == 0


def test_overlapping_reject_loses_to_approve_with_409(
    proposal_file_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_farms(proposal_file_database)
    proposal = _create_proposal(seeded)
    injected = _inject_competing_decision_before_cas(
        monkeypatch,
        proposal_file_database,
        proposal_id=proposal.proposal_id,
        winner_status="approved",
        winner_note="并发批准获胜",
        farm_id=int(seeded["farm_id"]),
    )

    with pytest.raises(AppException) as exc_info:
        farm_proposal_service.reject(
            user_id=int(seeded["owner_id"]),
            proposal_id=proposal.proposal_id,
            request=ProposalRejectRequest(decision_note="输家拒绝"),
        )

    assert injected == [True]
    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_PROPOSAL_TRANSITION"
    with proposal_file_database() as session:
        persisted = (
            session.query(FarmActionProposal)
            .filter(FarmActionProposal.proposal_id == proposal.proposal_id)
            .one()
        )
        assert persisted.status == "approved"
        assert persisted.decision_note == "并发批准获胜"
        assert {
            task.action_key for task in session.query(FarmTask).all()
        } == {"winner-action"}


def test_approval_reuses_partially_created_actions_and_inserts_only_missing_tasks(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)
    with proposal_database() as session:
        partial_task = FarmTask(
            task_id="partial-task-existing",
            proposal_id=proposal.proposal_id,
            action_key="check-drain",
            farm_id=int(seeded["farm_id"]),
            title="已在前次尝试创建",
            task_type="drainage",
            instructions="保留原任务",
            status="pending",
        )
        partial_task.set_acceptance_criteria(["保留原验收条件"])
        session.add(partial_task)
        session.commit()

    approved, tasks = farm_proposal_service.approve(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=ProposalApprovalRequest(
            actions=[_action("check-drain"), _action("prepare-pump")],
            decision_note="恢复审批",
        ),
    )

    assert approved.status == "approved"
    tasks_by_action = {task.action_key: task for task in tasks}
    assert tasks_by_action["check-drain"].task_id == "partial-task-existing"
    assert tasks_by_action["check-drain"].title == "已在前次尝试创建"
    assert tasks_by_action["prepare-pump"].task_id != "partial-task-existing"
    with proposal_database() as session:
        assert session.query(FarmTask).count() == 2


def test_approval_propagates_unrelated_integrity_error_and_rolls_back_atomically(
    proposal_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)
    colliding_uuid = UUID(int=0)
    colliding_task_id = f"task-{colliding_uuid.hex}"
    with proposal_database() as session:
        session.add(
            FarmTask(
                task_id=colliding_task_id,
                farm_id=int(seeded["farm_id"]),
                title="不相关的既有任务",
                task_type="inspection",
                instructions="不应被审批重试吞掉",
                status="pending",
            )
        )
        session.commit()
    monkeypatch.setattr(farm_proposal_service.uuid, "uuid4", lambda: colliding_uuid)

    with pytest.raises(IntegrityError):
        farm_proposal_service.approve(
            user_id=int(seeded["owner_id"]),
            proposal_id=proposal.proposal_id,
            request=ProposalApprovalRequest(
                actions=[_action("new-action-with-colliding-task-id")],
                decision_note="必须原子回滚",
            ),
        )

    with proposal_database() as session:
        persisted = (
            session.query(FarmActionProposal)
            .filter(FarmActionProposal.proposal_id == proposal.proposal_id)
            .one()
        )
        assert persisted.status == "pending"
        assert persisted.decision_note == ""
        assert (
            session.query(FarmTask)
            .filter(FarmTask.proposal_id == proposal.proposal_id)
            .count()
            == 0
        )


@pytest.mark.parametrize("field_key", ["other_field_id", "missing"])
def test_approval_rejects_field_outside_proposal_farm_before_transition(
    proposal_database: sessionmaker[Session],
    field_key: str,
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)
    field_id = (
        999_999
        if field_key == "missing"
        else int(seeded[field_key])
    )

    with pytest.raises(AppException) as exc_info:
        farm_proposal_service.approve(
            user_id=int(seeded["owner_id"]),
            proposal_id=proposal.proposal_id,
            request=ProposalApprovalRequest(
                actions=[
                    _action("invalid-field").model_copy(
                        update={"field_id": field_id}
                    )
                ],
                decision_note="字段关系必须先校验",
            ),
        )

    assert exc_info.value.status_code == 403
    with proposal_database() as session:
        persisted = (
            session.query(FarmActionProposal)
            .filter(FarmActionProposal.proposal_id == proposal.proposal_id)
            .one()
        )
        assert persisted.status == "pending"
        assert session.query(FarmTask).count() == 0


def test_rejected_proposal_cannot_be_approved(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)
    rejected = farm_proposal_service.reject(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=ProposalRejectRequest(decision_note="风险已由线下处置"),
    )
    assert rejected.status == "rejected"

    with pytest.raises(AppException) as exc_info:
        farm_proposal_service.approve(
            user_id=int(seeded["owner_id"]),
            proposal_id=proposal.proposal_id,
            request=ProposalApprovalRequest(
                actions=[_action("must-not-create")],
                decision_note="非法批准",
            ),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_PROPOSAL_TRANSITION"
    with proposal_database() as session:
        assert session.query(FarmTask).count() == 0


def test_repeated_reject_returns_original_decision_without_overwriting_note(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)
    first = farm_proposal_service.reject(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=ProposalRejectRequest(decision_note="首次拒绝理由"),
    )

    retried = farm_proposal_service.reject(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=ProposalRejectRequest(decision_note="重复请求不得覆盖"),
    )

    assert retried.status == "rejected"
    assert retried.decision_note == "首次拒绝理由"
    assert retried.decided_at == first.decided_at


def test_approved_proposal_cannot_be_rejected(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)
    farm_proposal_service.approve(
        user_id=int(seeded["owner_id"]),
        proposal_id=proposal.proposal_id,
        request=ProposalApprovalRequest(
            actions=[_action("approved-action")],
            decision_note="批准",
        ),
    )

    with pytest.raises(AppException) as exc_info:
        farm_proposal_service.reject(
            user_id=int(seeded["owner_id"]),
            proposal_id=proposal.proposal_id,
            request=ProposalRejectRequest(decision_note="非法拒绝"),
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "INVALID_PROPOSAL_TRANSITION"


@pytest.mark.parametrize("operation", ["create", "list", "approve", "reject"])
def test_cross_user_proposal_access_returns_403_without_business_data(
    proposal_database: sessionmaker[Session],
    operation: str,
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)

    with pytest.raises(AppException) as exc_info:
        if operation == "create":
            farm_proposal_service.create_pending_proposal(
                user_id=int(seeded["other_id"]),
                farm_id=int(seeded["farm_id"]),
                run_id=str(seeded["run_id"]),
                draft=_draft(risk_key="cross-user"),
            )
        elif operation == "list":
            farm_proposal_service.list_proposals(
                user_id=int(seeded["other_id"]),
                farm_id=int(seeded["farm_id"]),
                status=None,
            )
        elif operation == "approve":
            farm_proposal_service.approve(
                user_id=int(seeded["other_id"]),
                proposal_id=proposal.proposal_id,
                request=ProposalApprovalRequest(
                    actions=[_action("cross-user")],
                    decision_note="越权",
                ),
            )
        else:
            farm_proposal_service.reject(
                user_id=int(seeded["other_id"]),
                proposal_id=proposal.proposal_id,
                request=ProposalRejectRequest(decision_note="越权"),
            )

    assert exc_info.value.status_code == 403
    assert str(seeded["farm_name"]) not in exc_info.value.message
    assert str(seeded["farm_name"]) not in str(exc_info.value.detail)


@pytest.mark.parametrize("operation", ["create", "list"])
def test_foreign_and_missing_farm_identifiers_are_indistinguishable(
    proposal_database: sessionmaker[Session],
    operation: str,
) -> None:
    seeded = _seed_farms(proposal_database)

    def invoke(farm_id: int) -> None:
        if operation == "create":
            farm_proposal_service.create_pending_proposal(
                user_id=int(seeded["owner_id"]),
                farm_id=farm_id,
                run_id=str(seeded["run_id"]),
                draft=_draft(risk_key=f"nondisclosure:{farm_id}"),
            )
        else:
            farm_proposal_service.list_proposals(
                user_id=int(seeded["owner_id"]),
                farm_id=farm_id,
                status=None,
            )

    errors: list[AppException] = []
    for farm_id in (int(seeded["other_farm_id"]), 999_999):
        with pytest.raises(AppException) as exc_info:
            invoke(farm_id)
        errors.append(exc_info.value)

    assert {
        (error.status_code, error.code, error.message) for error in errors
    } == {(403, "FORBIDDEN", "无权访问目标资源")}


@pytest.mark.parametrize("operation", ["approve", "reject"])
def test_foreign_and_missing_proposal_identifiers_are_indistinguishable(
    proposal_database: sessionmaker[Session],
    operation: str,
) -> None:
    seeded = _seed_farms(proposal_database)
    proposal = _create_proposal(seeded)

    def invoke(*, user_id: int, proposal_id: str) -> None:
        if operation == "approve":
            farm_proposal_service.approve(
                user_id=user_id,
                proposal_id=proposal_id,
                request=ProposalApprovalRequest(
                    actions=[_action("nondisclosure")],
                    decision_note="不得泄露",
                ),
            )
        else:
            farm_proposal_service.reject(
                user_id=user_id,
                proposal_id=proposal_id,
                request=ProposalRejectRequest(decision_note="不得泄露"),
            )

    errors: list[AppException] = []
    for user_id, proposal_id in (
        (int(seeded["other_id"]), proposal.proposal_id),
        (int(seeded["owner_id"]), "missing-proposal"),
    ):
        with pytest.raises(AppException) as exc_info:
            invoke(user_id=user_id, proposal_id=proposal_id)
        errors.append(exc_info.value)

    assert {
        (error.status_code, error.code, error.message) for error in errors
    } == {(403, "FORBIDDEN", "无权访问目标资源")}


def test_list_proposals_filters_owned_farm_and_status(
    proposal_database: sessionmaker[Session],
) -> None:
    seeded = _seed_farms(proposal_database)
    pending = _create_proposal(seeded)
    second = farm_proposal_service.create_pending_proposal(
        user_id=int(seeded["owner_id"]),
        farm_id=int(seeded["farm_id"]),
        run_id=str(seeded["run_id"]),
        draft=_draft(risk_key="trajectory.work_quality:1:1"),
    )
    farm_proposal_service.reject(
        user_id=int(seeded["owner_id"]),
        proposal_id=second.proposal_id,
        request=ProposalRejectRequest(decision_note="暂不执行"),
    )

    proposals = farm_proposal_service.list_proposals(
        user_id=int(seeded["owner_id"]),
        farm_id=int(seeded["farm_id"]),
        status="pending",
    )

    assert [proposal.proposal_id for proposal in proposals] == [pending.proposal_id]
