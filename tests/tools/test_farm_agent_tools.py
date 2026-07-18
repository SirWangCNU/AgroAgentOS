"""Controlled Farm Agent tool adapter tests."""

from __future__ import annotations

import asyncio
import json
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Iterator, Literal

import pytest
from langchain_core.tools import StructuredTool
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.sqlite import AgentRun, Base, sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm
from app.models.farm_agent import FarmActionProposal, FarmTask
from app.models.user import User
from app.runtime.farm_run_context import (
    FarmRunContext,
    bind_farm_run_context,
    require_farm_run_context,
)
from app.schemas.farm_agent import (
    FarmEvidence,
    ProposalDraft,
    ProposedAction,
    TaskVerificationDraft,
)
from app.schemas.weather import DailyForecastDetail, WeatherForecastResult
from app.services import (
    farm_proposal_service,
    farm_risk_service,
    farm_snapshot_service,
    farm_task_service,
)
from app.services.farm_snapshot_service import FarmSnapshot
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


def _farm_snapshot() -> FarmSnapshot:
    observed_at = datetime(2026, 7, 18, 8, tzinfo=timezone.utc)
    return FarmSnapshot.model_validate(
        {
            "farm": {
                "id": 11,
                "user_id": 7,
                "name": "Owned farm",
                "location": "Shouguang",
                "latitude": 36.8,
                "longitude": 118.7,
                "area_mu": 10.0,
                "description": "",
                "created_at": observed_at,
                "updated_at": observed_at,
            },
            "fields": [],
            "recent_trajectory_files": [],
            "pending_task_count": 0,
            "captured_at": observed_at,
            "data_gaps": [],
        }
    )


def _detached_task(
    task_id: str,
    *,
    field_id: int,
    task_type: str,
) -> SimpleNamespace:
    timestamp = datetime(2026, 7, 18, tzinfo=timezone.utc)
    return SimpleNamespace(
        task_id=task_id,
        proposal_id=None,
        action_key=None,
        farm_id=11,
        field_id=field_id,
        assignee_name="",
        title=task_id,
        task_type=task_type,
        instructions="Inspect the field",
        acceptance_criteria=[],
        priority="normal",
        status="pending",
        due_at=None,
        execution={},
        agent_verdict={},
        created_at=timestamp,
        updated_at=timestamp,
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


@pytest.mark.asyncio
async def test_weather_tool_offloads_snapshot_and_awaits_provider(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    event_loop_thread_id = threading.get_ident()
    snapshot_calls: list[tuple[int, int, int, FarmRunContext]] = []
    provider_calls: list[tuple[str, int, int]] = []
    context = _context(run_type="inspection", task_id=None)

    def get_snapshot(*, farm_id: int, user_id: int) -> FarmSnapshot:
        snapshot_calls.append(
            (threading.get_ident(), farm_id, user_id, require_farm_run_context())
        )
        return _farm_snapshot()

    class AwaitedWeatherProvider:
        async def get_forecast_with_alerts(
            self,
            location: str,
            days: int = 2,
        ) -> WeatherForecastResult:
            await asyncio.sleep(0)
            provider_calls.append((location, days, threading.get_ident()))
            return WeatherForecastResult(
                location=location,
                daily=[
                    DailyForecastDetail(
                        date="2026-07-19",
                        min_temp=22,
                        max_temp=29,
                        precipitation_mm=60,
                        condition="Rainstorm",
                    )
                ],
                source="test",
            )

    monkeypatch.setattr(farm_snapshot_service, "get_snapshot", get_snapshot)
    monkeypatch.setattr(
        farm_risk_service,
        "WeatherServiceProvider",
        AwaitedWeatherProvider,
    )

    with bind_farm_run_context(context):
        result = await inspect_farm_weather_risks.coroutine(days=7)

    assert len(snapshot_calls) == 1
    snapshot_thread_id, farm_id, user_id, bound_context = snapshot_calls[0]
    assert (farm_id, user_id, bound_context) == (11, 7, context)
    assert snapshot_thread_id != event_loop_thread_id
    assert provider_calls == [("Shouguang", 7, event_loop_thread_id)]
    assert result["risks"][0]["risk_key"] == "weather.rainstorm_drainage"


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


def test_pending_tasks_total_counts_all_matches_before_limit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    tasks = [
        _detached_task("matching-1", field_id=21, task_type="drainage"),
        _detached_task("matching-2", field_id=21, task_type="drainage"),
        _detached_task("wrong-type", field_id=21, task_type="inspection"),
        _detached_task("wrong-field", field_id=22, task_type="drainage"),
    ]

    def list_tasks(**kwargs: object) -> list[SimpleNamespace]:
        assert kwargs == {"user_id": 7, "farm_id": 11, "status": "pending"}
        return tasks

    monkeypatch.setattr(farm_task_service, "list_tasks", list_tasks)

    with bind_farm_run_context(_context()):
        result = get_pending_farm_tasks.func(
            field_id=21,
            task_type="drainage",
            limit=1,
        )

    assert result["total"] == 2
    assert [task["task_id"] for task in result["tasks"]] == ["matching-1"]


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


def test_proposal_tool_serializes_real_detached_service_result(
    farm_tool_database: sessionmaker[Session],
) -> None:
    with farm_tool_database() as session:
        owner = User(
            username="real-proposal-owner",
            email="real-proposal-owner@example.com",
            hashed_password="hash",
        )
        session.add(owner)
        session.flush()
        farm = Farm(
            user_id=owner.id,
            name="Proposal farm",
            location="Shouguang",
            area_mu=12,
        )
        session.add(farm)
        session.flush()
        run = AgentRun(
            run_id="real-proposal-run",
            user_id=owner.id,
            farm_id=farm.id,
            run_type="farm_inspection",
        )
        session.add(run)
        session.commit()
        owner_id, farm_id, run_id = owner.id, farm.id, run.run_id

    with bind_farm_run_context(
        _context(
            user_id=owner_id,
            farm_id=farm_id,
            run_id=run_id,
            run_type="inspection",
            task_id=None,
        )
    ):
        result = create_action_proposal.func(draft=_proposal_draft())

    json.dumps(result, ensure_ascii=False)
    assert result["farm_id"] == farm_id
    assert result["created_by"] == owner_id
    assert result["run_id"] == run_id
    assert result["status"] == "pending"
    assert isinstance(result["created_at"], str)

    with farm_tool_database() as session:
        persisted = session.query(FarmActionProposal).one()
        assert persisted.run_id == run_id
        assert persisted.status == "pending"


def test_verification_tool_serializes_real_detached_task_without_transition(
    farm_tool_database: sessionmaker[Session],
) -> None:
    with farm_tool_database() as session:
        owner = User(
            username="real-verification-owner",
            email="real-verification-owner@example.com",
            hashed_password="hash",
        )
        session.add(owner)
        session.flush()
        farm = Farm(user_id=owner.id, name="Verification farm")
        session.add(farm)
        session.flush()
        target = FarmTask(
            task_id="real-target-task",
            farm_id=farm.id,
            title="Inspect drains",
            task_type="drainage",
            instructions="Inspect every drainage point",
            status="submitted",
        )
        target.set_execution({})
        decoy = FarmTask(
            task_id="real-decoy-task",
            farm_id=farm.id,
            title="Decoy task",
            task_type="inspection",
            instructions="Do not update this task",
            status="submitted",
        )
        decoy.set_execution({})
        session.add_all([target, decoy])
        session.commit()
        owner_id, farm_id = owner.id, farm.id

    verdict = TaskVerificationDraft(
        verdict="manual_review",
        note="A human should inspect the original image",
        evidence_refs=["attachment:0"],
    )
    with bind_farm_run_context(
        _context(
            user_id=owner_id,
            farm_id=farm_id,
            task_id="real-target-task",
        )
    ):
        result = save_task_verification_draft.func(verdict=verdict)

    json.dumps(result, ensure_ascii=False)
    assert result["task_id"] == "real-target-task"
    assert result["farm_id"] == farm_id
    assert result["status"] == "submitted"
    assert result["agent_verdict"] == verdict.model_dump(mode="json")
    assert isinstance(result["updated_at"], str)

    with farm_tool_database() as session:
        persisted_target = (
            session.query(FarmTask)
            .filter(FarmTask.task_id == "real-target-task")
            .one()
        )
        persisted_decoy = (
            session.query(FarmTask)
            .filter(FarmTask.task_id == "real-decoy-task")
            .one()
        )
        assert persisted_target.status == "submitted"
        assert persisted_target.agent_verdict == verdict.model_dump(mode="json")
        assert persisted_decoy.agent_verdict == {}


def test_local_tool_collection_contains_all_farm_tools_without_duplicates() -> None:
    names = [tool.name for tool in get_local_tools()]

    assert FARM_TOOL_NAMES <= set(names)
    assert len(names) == len(set(names))
