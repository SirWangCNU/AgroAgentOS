"""Farm Agent 提案持久化和人工审批服务。"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import NoReturn

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.sqlite import sqlite_manager
from app.exceptions import AppException, ForbiddenError
from app.models.farm import Farm
from app.models.farm_agent import FarmActionProposal, FarmTask
from app.schemas.farm_agent import (
    ProposalApprovalRequest,
    ProposalDraft,
    ProposalRejectRequest,
    ProposalStatus,
    ProposedAction,
)


def _build_risk_fingerprint(*, farm_id: int, risk_key: str) -> str:
    return hashlib.sha256(f"{farm_id}:{risk_key}".encode()).hexdigest()


def _raise_not_found() -> NoReturn:
    raise AppException(
        status_code=404,
        code="NOT_FOUND",
        message="提案不存在",
    )


def _raise_invalid_transition() -> NoReturn:
    raise AppException(
        status_code=409,
        code="INVALID_PROPOSAL_TRANSITION",
        message="当前提案状态不允许该操作",
    )


def _require_owned_farm(session: Session, *, farm_id: int, user_id: int) -> Farm:
    farm = session.query(Farm).filter(Farm.id == farm_id).first()
    if farm is None:
        raise AppException(
            status_code=404,
            code="NOT_FOUND",
            message="农场不存在",
        )
    if farm.user_id != user_id:
        raise ForbiddenError(message="无权访问目标农场")
    return farm


def _require_owned_proposal(
    session: Session,
    *,
    proposal_id: str,
    user_id: int,
) -> FarmActionProposal:
    proposal = (
        session.query(FarmActionProposal)
        .filter(FarmActionProposal.proposal_id == proposal_id)
        .first()
    )
    if proposal is None:
        _raise_not_found()
    _require_owned_farm(session, farm_id=proposal.farm_id, user_id=user_id)
    return proposal


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


def _approve_pending(
    session: Session,
    *,
    proposal: FarmActionProposal,
    request: ProposalApprovalRequest,
) -> tuple[list[FarmTask], set[str], set[str]]:
    existing_tasks = _load_tasks(session, proposal_id=proposal.proposal_id)
    tasks_by_action = {
        task.action_key: task
        for task in existing_tasks
        if task.action_key is not None
    }
    preexisting_action_keys = set(tasks_by_action)
    attempted_action_keys: set[str] = set()

    for action in request.actions:
        if action.action_key in tasks_by_action:
            continue
        task = _task_from_action(proposal=proposal, action=action)
        session.add(task)
        tasks_by_action[action.action_key] = task
        existing_tasks.append(task)
        attempted_action_keys.add(action.action_key)

    proposal.status = "approved"
    proposal.decision_note = request.decision_note
    proposal.decided_at = datetime.now(timezone.utc)
    return existing_tasks, preexisting_action_keys, attempted_action_keys


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
        except IntegrityError:
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

        try:
            tasks, preexisting_action_keys, attempted_action_keys = _approve_pending(
                session,
                proposal=proposal,
                request=request,
            )
            session.flush()
        except IntegrityError:
            session.rollback()
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

            current_tasks = _load_tasks(session, proposal_id=proposal.proposal_id)
            current_action_keys = {
                task.action_key
                for task in current_tasks
                if task.action_key is not None
            }
            raced_action_keys = (
                current_action_keys - preexisting_action_keys
            ) & attempted_action_keys
            if not raced_action_keys:
                raise
            tasks, _, _ = _approve_pending(
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

        proposal.status = "rejected"
        proposal.decision_note = request.decision_note
        proposal.decided_at = datetime.now(timezone.utc)
        session.flush()
        _detach_proposal(session, proposal)
        return proposal
