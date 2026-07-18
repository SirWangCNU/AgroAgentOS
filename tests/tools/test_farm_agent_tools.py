"""Controlled Farm Agent tool adapter tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Iterator, Literal

import pytest
from langchain_core.tools import StructuredTool
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.sqlite import Base, sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm
from app.models.user import User
from app.runtime.farm_run_context import FarmRunContext, bind_farm_run_context
from app.schemas.farm_agent import (
    FarmEvidence,
    ProposalDraft,
    ProposedAction,
    TaskVerificationDraft,
)
from app.services import farm_proposal_service, farm_task_service
from app.tools.farm_agent_tools import (
    create_action_proposal,
    get_farm_snapshot,
    get_field_work_quality,
    get_pending_farm_tasks,
    get_task_evidence,
    inspect_farm_weather_risks,
    save_task_verification_draft,
)
from app.tools.mcp_loader import get_local_tools


FARM_TOOL_NAMES = {
    "get_farm_snapshot",
    "inspect_farm_weather_risks",
    "get_field_work_quality",
    "get_pending_farm_tasks",
    "get_task_evidence",
    "create_action_proposal",
    "save_task_verification_draft",
}


def _context(
    *,
    user_id: int = 7,
    farm_id: int = 11,
    run_id: str = "run-context",
    run_type: Literal["inspection", "task_verification"] = "task_verification",
    task_id: str | None = "task-context",
) -> FarmRunContext:
    return FarmRunContext(
        user_id=user_id,
        farm_id=farm_id,
        run_id=run_id,
        run_type=run_type,
        task_id=task_id,
    )


def _proposal_draft() -> ProposalDraft:
    return ProposalDraft(
        risk_key="weather.rainstorm",
        title="Clear drains",
        severity="high",
        summary="Heavy rain is forecast",
        confidence=0.9,
        evidence=[
            FarmEvidence(
                source_type="forecast",
                source_id="forecast-1",
                summary="Rain threshold exceeded",
                observed_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
                fact_kind="measured",
            )
        ],
        actions=[
            ProposedAction(
                action_key="clear-drain",
                title="Clear drains",
                task_type="drainage",
                instructions="Clear blocked drainage points",
            )
        ],
    )


@pytest.mark.parametrize(
    ("tool", "arguments"),
    [
        (get_farm_snapshot, {}),
        (get_field_work_quality, {}),
        (get_pending_farm_tasks, {}),
        (get_task_evidence, {}),
        (create_action_proposal, {"draft": _proposal_draft()}),
        (
            save_task_verification_draft,
            {
                "verdict": TaskVerificationDraft(
                    verdict="pass",
                    note="Evidence is sufficient",
                )
            },
        ),
    ],
)
def test_sync_farm_tools_reject_missing_run_context(
    tool: StructuredTool,
    arguments: dict[str, object],
) -> None:
    with pytest.raises(AppException) as exc_info:
        tool.func(**arguments)

    assert exc_info.value.code == "FARM_RUN_CONTEXT_MISSING"


@pytest.mark.asyncio
async def test_weather_tool_rejects_missing_run_context() -> None:
    with pytest.raises(AppException) as exc_info:
        await inspect_farm_weather_risks.coroutine(days=2)

    assert exc_info.value.code == "FARM_RUN_CONTEXT_MISSING"


@pytest.mark.parametrize(
    "tool",
    [
        get_farm_snapshot,
        inspect_farm_weather_risks,
        get_field_work_quality,
        get_pending_farm_tasks,
        get_task_evidence,
        create_action_proposal,
        save_task_verification_draft,
    ],
)
def test_farm_tool_schemas_never_expose_trusted_context_ids(tool: StructuredTool) -> None:
    assert tool.args_schema is not None
    fields = set(tool.args_schema.model_fields)

    assert fields.isdisjoint({"user_id", "farm_id", "run_id", "task_id"})


@pytest.mark.parametrize("days", [0, 8])
def test_weather_tool_restricts_forecast_days(days: int) -> None:
    with pytest.raises(ValidationError):
        inspect_farm_weather_risks.args_schema.model_validate({"days": days})


def test_proposal_tool_forces_all_context_ids(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def create_pending_proposal(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        draft = kwargs["draft"]
        assert isinstance(draft, ProposalDraft)
        return SimpleNamespace(
            proposal_id="proposal-1",
            farm_id=11,
            created_by=7,
            run_id="run-context",
            risk_fingerprint="fingerprint",
            title=draft.title,
            severity=draft.severity,
            summary=draft.summary,
            confidence=draft.confidence,
            evidence=[item.model_dump(mode="json") for item in draft.evidence],
            actions=[item.model_dump(mode="json") for item in draft.actions],
            status="pending",
            decision_note="",
            created_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
            decided_at=None,
        )

    monkeypatch.setattr(farm_proposal_service, "create_pending_proposal", create_pending_proposal)

    with bind_farm_run_context(_context()):
        result = create_action_proposal.func(draft=_proposal_draft())

    assert captured["user_id"] == 7
    assert captured["farm_id"] == 11
    assert captured["run_id"] == "run-context"
    assert result["proposal_id"] == "proposal-1"
    assert result["created_at"] == "2026-07-18T00:00:00Z"


def test_verification_tool_forces_context_task_id(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def save_verification_draft(**kwargs: object) -> SimpleNamespace:
        captured.update(kwargs)
        return SimpleNamespace(
            task_id="task-context",
            proposal_id=None,
            action_key=None,
            farm_id=11,
            field_id=None,
            assignee_name="",
            title="Inspect drains",
            task_type="drainage",
            instructions="Inspect every drain",
            acceptance_criteria=[],
            priority="normal",
            status="submitted",
            due_at=None,
            execution={},
            agent_verdict={"verdict": "pass", "note": "Enough evidence"},
            created_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
            updated_at=datetime(2026, 7, 18, tzinfo=timezone.utc),
        )

    monkeypatch.setattr(farm_task_service, "save_verification_draft", save_verification_draft)
    verdict = TaskVerificationDraft(verdict="pass", note="Enough evidence")

    with bind_farm_run_context(_context()):
        result = save_task_verification_draft.func(verdict=verdict)

    assert captured == {
        "user_id": 7,
        "task_id": "task-context",
        "verdict": verdict,
    }
    assert result["status"] == "submitted"


@pytest.fixture
def farm_tool_database(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
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


def test_snapshot_tool_uses_real_context_ownership_boundary(
    farm_tool_database: sessionmaker[Session],
) -> None:
    with farm_tool_database() as session:
        owner = User(username="tool-owner", email="tool-owner@example.com", hashed_password="hash")
        other = User(username="tool-other", email="tool-other@example.com", hashed_password="hash")
        session.add_all([owner, other])
        session.flush()
        farm = Farm(user_id=owner.id, name="Owned farm", location="Shouguang", area_mu=10)
        session.add(farm)
        session.commit()
        owner_id, other_id, farm_id = owner.id, other.id, farm.id

    with bind_farm_run_context(
        _context(user_id=owner_id, farm_id=farm_id, run_type="inspection", task_id=None)
    ):
        result = get_farm_snapshot.func()
    assert result["farm"]["id"] == farm_id

    with bind_farm_run_context(
        _context(user_id=other_id, farm_id=farm_id, run_type="inspection", task_id=None)
    ):
        with pytest.raises(AppException) as exc_info:
            get_farm_snapshot.func()
    assert exc_info.value.status_code == 403


def test_local_tool_collection_contains_all_farm_tools_without_duplicates() -> None:
    names = [tool.name for tool in get_local_tools()]

    assert FARM_TOOL_NAMES <= set(names)
    assert len(names) == len(set(names))
