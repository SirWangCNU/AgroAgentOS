"""Farm Agent 比赛闭环的真实服务与持久化集成测试。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import AsyncIterator, Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.agents.stream_sink import emit
from app.core.sqlite import Base, HistoryRecord, sqlite_manager
from app.exceptions import ForbiddenError
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmActionProposal, FarmTask
from app.models.trajectory import TrajectoryFile
from app.models.user import User
from app.runtime.transitions import make_transition
from app.schemas.farm_agent import (
    FarmInspectionRequest,
    ProposalApprovalRequest,
    ProposalDraft,
    ProposedAction,
    TaskSubmitRequest,
    TaskVerificationDraft,
)
from app.schemas.weather import DailyForecastDetail, WeatherForecastResult
from app.services import (
    farm_agent_service,
    farm_proposal_service,
    farm_run_query_service,
    farm_task_service,
)
from app.tools.farm_agent_tools import create_action_proposal, save_task_verification_draft


@pytest.fixture()
def workflow_database(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[sessionmaker[Session]]:
    engine = create_engine(
        f"sqlite:///{tmp_path / 'closed-loop.db'}",
        connect_args={"check_same_thread": False},
    )

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection: sqlite3.Connection, _record: object) -> None:
        connection.execute("PRAGMA foreign_keys=ON")

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


class _DemoWeatherProvider:
    async def get_forecast_with_alerts(self, location: str, days: int = 2):
        return WeatherForecastResult(
            location=location,
            source="competition-demo:rainstorm-v1",
            daily=[
                DailyForecastDetail(
                    date="2026-07-18",
                    min_temp=24,
                    max_temp=29,
                    precipitation_mm=82,
                    condition="暴雨",
                    wind_level=5,
                )
            ],
        )


class _ClosedLoopGraph:
    async def astream(self, state, config) -> AsyncIterator[dict]:
        if state["run_type"] == "inspection":
            field_id = state["business_context"]["snapshot"]["fields"][0]["id"]
            proposal = create_action_proposal.func(
                draft=ProposalDraft(
                    risk_key="weather.rainstorm_drainage",
                    title="暴雨前排水检查",
                    severity="critical",
                    summary="未来 24 小时降雨 82mm，需要先检查 A1 排水能力",
                    confidence=0.9,
                    evidence=[{
                        "source_type": "weather_forecast",
                        "source_id": "competition-demo:rainstorm-v1",
                        "summary": "未来 24 小时累计降雨 82mm",
                        "observed_at": "2026-07-18T08:00:00+08:00",
                        "fact_kind": "measured",
                        "payload": {"rainfall_24h_mm": 82.0},
                    }],
                    actions=[ProposedAction(
                        action_key="drainage-a1",
                        title="检查 A1 排水沟",
                        task_type="drainage",
                        instructions="清理堵塞点并提交轨迹或文字证据",
                        priority="urgent",
                        field_id=field_id,
                        acceptance_criteria=["排水沟无明显堵塞", "提交执行说明"],
                    )],
                )
            )
            await emit({
                "type": "tool_call",
                "name": "create_action_proposal",
                "elapsed_ms": 2,
                "read_only": False,
                "result_chars": 100,
                "status": "ok",
            })
            yield {"executor": {
                "past_steps": [("生成有证据的行动提案", proposal["proposal_id"])],
                "proposal_ids": [proposal["proposal_id"]],
                "transition_history": [
                    make_transition("executor", "proposal_persisted", "行动提案已持久化")
                ],
            }}
            yield {"replanner": {
                "response": "已生成待人工审批的暴雨排水提案。",
                "transition_history": [
                    make_transition("replanner", "workflow_finished", "等待人工审批")
                ],
            }}
            return

        task = save_task_verification_draft.func(
            verdict=TaskVerificationDraft(
                verdict="pass",
                note="轨迹与文字证据满足验收条件，等待人工最终确认",
                evidence_refs=["trajectory:demo-low-quality.xlsx", "submission:note"],
            )
        )
        await emit({
            "type": "tool_call",
            "name": "save_task_verification_draft",
            "elapsed_ms": 2,
            "read_only": False,
            "result_chars": 100,
            "status": "ok",
        })
        yield {"executor": {
            "past_steps": [("保存 AI 复核草稿", task["task_id"])],
            "transition_history": [
                make_transition("executor", "verification_draft_saved", "复核草稿已保存")
            ],
        }}
        yield {"replanner": {
            "response": "AI 复核草稿已保存，任务仍等待人工决定。",
            "transition_history": [
                make_transition("replanner", "workflow_finished", "等待人工确认")
            ],
        }}


def _seed_workflow(session_factory: sessionmaker[Session]) -> dict[str, int]:
    with session_factory() as session:
        owner = User(username="demo-owner", email="demo@example.com", hashed_password="hash")
        other = User(username="other", email="other@example.com", hashed_password="hash")
        session.add_all([owner, other])
        session.flush()
        farm = Farm(
            user_id=owner.id,
            name="阳光农场",
            location="江苏省南京市江宁区",
            area_mu=30,
            description="[competition-demo:demo-sunshine-farm] 比赛演示数据",
        )
        session.add(farm)
        session.flush()
        field = Field(
            farm_id=farm.id,
            name="A1",
            area_mu=12,
            current_crop="水稻",
            growth_stage="分蘖期",
            status="planting",
            boundary_json="[]",
        )
        session.add(field)
        session.flush()
        trajectory = TrajectoryFile(
            field_id=field.id,
            filename="demo-low-quality.xlsx",
            point_count=128,
            work_area_mu=5,
            depth_std=7.5,
        )
        session.add(trajectory)
        session.commit()
        return {
            "owner_id": owner.id,
            "other_id": other.id,
            "farm_id": farm.id,
            "field_id": field.id,
            "trajectory_id": trajectory.id,
        }


@pytest.mark.asyncio
async def test_competition_workflow_keeps_both_human_decision_gates(
    workflow_database: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
):
    ids = _seed_workflow(workflow_database)
    monkeypatch.setattr(farm_agent_service, "_get_graph", lambda: _ClosedLoopGraph())
    monkeypatch.setattr(
        farm_agent_service,
        "_select_inspection_weather_provider",
        lambda request: _DemoWeatherProvider(),
    )

    inspection_events = [
        event
        async for event in farm_agent_service.stream_inspection(
            user_id=ids["owner_id"],
            request=FarmInspectionRequest(farm_id=ids["farm_id"], demo_scenario="rainstorm"),
        )
    ]
    run_id = next(event["run_id"] for event in inspection_events if event["type"] == "start")
    event_types = {event["type"] for event in inspection_events}
    assert {"context_loaded", "tool_call", "proposal_created", "report", "complete"} <= event_types
    assert any(
        risk["evidence"][0]["payload"].get("precipitation_first_forecast_day_mm") == 82
        for event in inspection_events if event["type"] == "context_loaded"
        for risk in event["data"]["inspection"]["risks"]
        if risk["risk_key"] == "weather.rainstorm_drainage"
    )

    proposals = farm_proposal_service.list_proposals(
        user_id=ids["owner_id"], farm_id=ids["farm_id"], status="pending"
    )
    assert len(proposals) == 1
    proposal = proposals[0]
    assert farm_task_service.list_tasks(
        user_id=ids["owner_id"], farm_id=ids["farm_id"], status=None
    ) == []
    assert farm_proposal_service.list_proposals(
        user_id=ids["other_id"], farm_id=None, status=None
    ) == []

    approval = ProposalApprovalRequest(
        actions=[ProposedAction.model_validate(proposal.actions[0])],
        decision_note="人工确认暴雨排水风险",
    )
    _, first_tasks = farm_proposal_service.approve(
        user_id=ids["owner_id"], proposal_id=proposal.proposal_id, request=approval
    )
    _, repeated_tasks = farm_proposal_service.approve(
        user_id=ids["owner_id"], proposal_id=proposal.proposal_id, request=approval
    )
    assert [task.task_id for task in first_tasks] == [task.task_id for task in repeated_tasks]
    task_id = first_tasks[0].task_id

    farm_task_service.start(user_id=ids["owner_id"], task_id=task_id)
    farm_task_service.submit(
        user_id=ids["owner_id"],
        task_id=task_id,
        request=TaskSubmitRequest(
            note="已清理 A1 排水沟堵塞点",
            trajectory_file_ids=[ids["trajectory_id"]],
        ),
    )
    verification_events = [
        event
        async for event in farm_agent_service.stream_task_verification(
            user_id=ids["owner_id"], task_id=task_id
        )
    ]
    assert any(event["type"] == "tool_call" for event in verification_events)
    submitted = farm_task_service.list_tasks(
        user_id=ids["owner_id"], farm_id=ids["farm_id"], status="submitted"
    )
    assert len(submitted) == 1
    assert submitted[0].agent_verdict["verdict"] == "pass"

    completed = farm_task_service.complete(
        user_id=ids["owner_id"], task_id=task_id, note="人工验收通过"
    )
    assert completed.status == "completed"
    timeline = await farm_run_query_service.get_run_timeline(
        user_id=ids["owner_id"], run_id=run_id
    )
    assert timeline.events
    assert timeline.proposal_ids == [proposal.proposal_id]
    assert timeline.outcome["proposal_ids"] == [proposal.proposal_id]
    with pytest.raises(ForbiddenError):
        await farm_run_query_service.get_run_timeline(
            user_id=ids["other_id"], run_id=run_id
        )
    with workflow_database() as session:
        assert session.query(FarmTask).filter(FarmTask.proposal_id == proposal.proposal_id).count() == 1
        assert session.query(HistoryRecord).filter(
            HistoryRecord.session_id == run_id,
            HistoryRecord.source == "farm_agent",
        ).count() == 1
