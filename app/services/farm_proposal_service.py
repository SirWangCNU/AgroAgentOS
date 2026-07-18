"""Farm Agent 提案持久化和人工审批服务。"""

from __future__ import annotations

import hashlib
import re
import uuid
from datetime import datetime, timezone
from typing import NoReturn

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.sqlite import AgentRun, sqlite_manager
from app.exceptions import AppException, ForbiddenError
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmActionProposal, FarmTask
from app.schemas.farm_agent import (
    ProposalApprovalRequest,
    ProposalDraft,
    ProposalRejectRequest,
    ProposalStatus,
    ProposedAction,
)

_PROPOSAL_UNIQUE_CONSTRAINT = "uq_proposal_run_risk"
_PROPOSAL_UNIQUE_SQLITE_COLUMNS = (
    "farm_action_proposals.run_id",
    "farm_action_proposals.risk_fingerprint",
)


def _is_unique_constraint_violation(
    error: IntegrityError,
    *,
    constraint_name: str,
    sqlite_columns: tuple[str, ...],
) -> bool:
    message = str(error.orig).lower()
    sqlite_signature = (
        "unique constraint failed: " + ", ".join(sqlite_columns)
    ).lower()
    if message.strip() == sqlite_signature:
        return True
    mysql_key_match = re.search(
        r"\bfor key\s+[`'\"]([^`'\"]+)[`'\"]",
        message,
    )
    if "duplicate entry" not in message or mysql_key_match is None:
        return False
    mysql_key_name = mysql_key_match.group(1).rsplit(".", maxsplit=1)[-1]
    return mysql_key_name == constraint_name.lower()


def _build_risk_fingerprint(*, farm_id: int, risk_key: str) -> str:
    return hashlib.sha256(f"{farm_id}:{risk_key}".encode()).hexdigest()


def _raise_forbidden() -> NoReturn:
    raise ForbiddenError(message="无权访问目标资源")


def _raise_invalid_transition() -> NoReturn:
    raise AppException(
        status_code=409,
        code="INVALID_PROPOSAL_TRANSITION",
        message="当前提案状态不允许该操作",
    )


def _require_owned_farm(session: Session, *, farm_id: int, user_id: int) -> Farm:
    farm = (
        session.query(Farm)
        .filter(Farm.id == farm_id, Farm.user_id == user_id)
        .first()
    )
    if farm is None:
        _raise_forbidden()
    return farm


def _require_owned_proposal(
    session: Session,
    *,
    proposal_id: str,
    user_id: int,
) -> FarmActionProposal:
    proposal = (
        session.query(FarmActionProposal)
        .join(Farm, Farm.id == FarmActionProposal.farm_id)
        .filter(
            FarmActionProposal.proposal_id == proposal_id,
            Farm.user_id == user_id,
        )
        .first()
    )
    if proposal is None:
        _raise_forbidden()
    return proposal


def _require_owned_run(
    session: Session,
    *,
    run_id: str,
    farm_id: int,
    user_id: int,
) -> None:
    run_exists = (
        session.query(AgentRun.id)
        .filter(
            AgentRun.run_id == run_id,
            AgentRun.farm_id == farm_id,
            AgentRun.user_id == user_id,
        )
        .first()
    )
    if run_exists is None:
        _raise_forbidden()


def _require_action_fields(
    session: Session,
    *,
    farm_id: int,
    actions: list[ProposedAction],
) -> None:
    requested_field_ids = {
        action.field_id for action in actions if action.field_id is not None
    }
    if not requested_field_ids:
        return
    owned_field_ids = {
        field_id
        for (field_id,) in (
            session.query(Field.id)
            .filter(
                Field.farm_id == farm_id,
                Field.id.in_(requested_field_ids),
            )
            .all()
        )
    }
    if owned_field_ids != requested_field_ids:
        _raise_forbidden()


def _detach_proposal(session: Session, proposal: FarmActionProposal) -> None:
    session.expunge(proposal)


def _load_tasks(session: Session, *, proposal_id: str) -> list[FarmTask]:
    return (
        session.query(FarmTask)
        .filter(FarmTask.proposal_id == proposal_id)
        .order_by(FarmTask.id.asc())
        .all()
    )


def _detach_approval_result(
    session: Session,
    proposal: FarmActionProposal,
    tasks: list[FarmTask],
) -> tuple[FarmActionProposal, list[FarmTask]]:
    _detach_proposal(session, proposal)
    for task in tasks:
        session.expunge(task)
    return proposal, tasks


def _task_from_action(
    *,
    proposal: FarmActionProposal,
    action: ProposedAction,
) -> FarmTask:
    task = FarmTask(
        task_id=f"task-{uuid.uuid4().hex}",
        proposal_id=proposal.proposal_id,
        action_key=action.action_key,
        farm_id=proposal.farm_id,
        field_id=action.field_id,
        assignee_name=action.assignee_name,
        title=action.title,
        task_type=action.task_type,
        instructions=action.instructions,
        priority=action.priority,
        status="pending",
        due_at=action.due_at,
    )
    task.set_acceptance_criteria(action.acceptance_criteria)
    return task


def _create_missing_tasks(
    session: Session,
    *,
    proposal: FarmActionProposal,
    request: ProposalApprovalRequest,
) -> list[FarmTask]:
    existing_tasks = _load_tasks(session, proposal_id=proposal.proposal_id)
    tasks_by_action = {
        task.action_key: task
        for task in existing_tasks
        if task.action_key is not None
    }

    for action in request.actions:
        if action.action_key in tasks_by_action:
            continue
        task = _task_from_action(proposal=proposal, action=action)
        session.add(task)
        tasks_by_action[action.action_key] = task
        existing_tasks.append(task)
    return existing_tasks


def _compare_and_set_decision(
    session: Session,
    *,
    proposal_id: str,
    status: ProposalStatus,
    decision_note: str,
) -> bool:
    affected_rows = (
        session.query(FarmActionProposal)
        .filter(
            FarmActionProposal.proposal_id == proposal_id,
            FarmActionProposal.status == "pending",
        )
        .update(
            {
                FarmActionProposal.status: status,
                FarmActionProposal.decision_note: decision_note,
                FarmActionProposal.decided_at: datetime.now(timezone.utc),
            },
            synchronize_session=False,
        )
    )
    return affected_rows == 1


def create_pending_proposal(
    *,
    user_id: int,
    farm_id: int,
    run_id: str,
    draft: ProposalDraft,
) -> FarmActionProposal:
    """创建 pending 提案；同一运行和风险的重试返回原记录。"""

    fingerprint = _build_risk_fingerprint(
        farm_id=farm_id,
        risk_key=draft.risk_key,
    )
    with sqlite_manager.session() as session:
        _require_owned_farm(session, farm_id=farm_id, user_id=user_id)
        _require_owned_run(
            session,
            run_id=run_id,
            farm_id=farm_id,
            user_id=user_id,
        )
        existing = (
            session.query(FarmActionProposal)
            .filter(
                FarmActionProposal.run_id == run_id,
                FarmActionProposal.risk_fingerprint == fingerprint,
            )
            .first()
        )
        if existing is not None:
            _detach_proposal(session, existing)
            return existing

        proposal = FarmActionProposal(
            proposal_id=f"proposal-{uuid.uuid4().hex}",
            farm_id=farm_id,
            created_by=user_id,
            run_id=run_id,
            risk_fingerprint=fingerprint,
            title=draft.title,
            severity=draft.severity,
            summary=draft.summary,
            confidence=draft.confidence,
            status="pending",
        )
        proposal.set_evidence(
            [item.model_dump(mode="json") for item in draft.evidence]
        )
        proposal.set_actions(
            [item.model_dump(mode="json") for item in draft.actions]
        )
        session.add(proposal)
        try:
            session.flush()
        except IntegrityError as exc:
            if not _is_unique_constraint_violation(
                exc,
                constraint_name=_PROPOSAL_UNIQUE_CONSTRAINT,
                sqlite_columns=_PROPOSAL_UNIQUE_SQLITE_COLUMNS,
            ):
                raise
            session.rollback()
            existing = (
                session.query(FarmActionProposal)
                .filter(
                    FarmActionProposal.run_id == run_id,
                    FarmActionProposal.risk_fingerprint == fingerprint,
                )
                .first()
            )
            if existing is None:
                raise
            _detach_proposal(session, existing)
            return existing

        _detach_proposal(session, proposal)
        return proposal


def list_proposals(
    *,
    user_id: int,
    farm_id: int | None,
    status: ProposalStatus | None,
) -> list[FarmActionProposal]:
    """列出当前用户拥有农场的提案。"""

    with sqlite_manager.session() as session:
        if farm_id is not None:
            _require_owned_farm(session, farm_id=farm_id, user_id=user_id)

        query = (
            session.query(FarmActionProposal)
            .join(Farm, Farm.id == FarmActionProposal.farm_id)
            .filter(Farm.user_id == user_id)
        )
        if farm_id is not None:
            query = query.filter(FarmActionProposal.farm_id == farm_id)
        if status is not None:
            query = query.filter(FarmActionProposal.status == status)
        proposals = query.order_by(
            FarmActionProposal.created_at.desc(),
            FarmActionProposal.id.desc(),
        ).all()
        for proposal in proposals:
            _detach_proposal(session, proposal)
        return proposals


def approve(
    *,
    user_id: int,
    proposal_id: str,
    request: ProposalApprovalRequest,
) -> tuple[FarmActionProposal, list[FarmTask]]:
    """人工批准 pending 提案，并在同一事务中创建执行任务。"""

    with sqlite_manager.session() as session:
        proposal = _require_owned_proposal(
            session,
            proposal_id=proposal_id,
            user_id=user_id,
        )
        if proposal.status == "approved":
            tasks = _load_tasks(session, proposal_id=proposal.proposal_id)
            return _detach_approval_result(session, proposal, tasks)
        if proposal.status != "pending":
            _raise_invalid_transition()
        _require_action_fields(
            session,
            farm_id=proposal.farm_id,
            actions=request.actions,
        )
        if not _compare_and_set_decision(
            session,
            proposal_id=proposal.proposal_id,
            status="approved",
            decision_note=request.decision_note,
        ):
            session.rollback()
            proposal = _require_owned_proposal(
                session,
                proposal_id=proposal_id,
                user_id=user_id,
            )
            if proposal.status == "approved":
                tasks = _load_tasks(session, proposal_id=proposal.proposal_id)
                return _detach_approval_result(session, proposal, tasks)
            _raise_invalid_transition()

        session.expire(proposal)
        session.refresh(proposal)
        tasks = _create_missing_tasks(
            session,
            proposal=proposal,
            request=request,
        )
        session.flush()
        return _detach_approval_result(session, proposal, tasks)


def reject(
    *,
    user_id: int,
    proposal_id: str,
    request: ProposalRejectRequest,
) -> FarmActionProposal:
    """人工拒绝 pending 提案。"""

    with sqlite_manager.session() as session:
        proposal = _require_owned_proposal(
            session,
            proposal_id=proposal_id,
            user_id=user_id,
        )
        if proposal.status == "rejected":
            _detach_proposal(session, proposal)
            return proposal
        if proposal.status != "pending":
            _raise_invalid_transition()
        if not _compare_and_set_decision(
            session,
            proposal_id=proposal.proposal_id,
            status="rejected",
            decision_note=request.decision_note,
        ):
            session.rollback()
            proposal = _require_owned_proposal(
                session,
                proposal_id=proposal_id,
                user_id=user_id,
            )
            if proposal.status == "rejected":
                _detach_proposal(session, proposal)
                return proposal
            _raise_invalid_transition()

        session.expire(proposal)
        session.refresh(proposal)
        _detach_proposal(session, proposal)
        return proposal
