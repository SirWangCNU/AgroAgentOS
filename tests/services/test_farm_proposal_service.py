"""Farm Agent 提案幂等与人工审批边界测试。"""

from __future__ import annotations

import hashlib
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator
from uuid import UUID

import pytest
from pydantic import ValidationError
from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Query, Session, sessionmaker

from app.core.sqlite import AgentRun, Base, sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm
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
        session.add_all([owner_run, other_run])
        session.commit()
        return {
            "owner_id": owner.id,
            "other_id": other.id,
            "farm_id": owned_farm.id,
            "farm_name": owned_farm.name,
            "other_farm_id": other_farm.id,
            "run_id": owner_run.run_id,
            "other_run_id": other_run.run_id,
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
    )

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
