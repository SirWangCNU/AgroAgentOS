"""Farm Agent 巡检、时间线和提案 API 契约测试。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import farm_agent
from app.exceptions import AppException, ForbiddenError
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.farm_agent import AgentRunTimelineResponse, ProposalResponse


def _user() -> User:
    return User(id=7, username="owner", hashed_password="unused", role="user", is_active=1)


def _proposal() -> ProposalResponse:
    now = datetime.now(timezone.utc)
    return ProposalResponse(
        proposal_id="proposal-1",
        farm_id=11,
        created_by=7,
        run_id="run-1",
        risk_fingerprint="risk-1",
        title="暴雨排水",
        severity="high",
        summary="需要检查排水沟",
        confidence=0.9,
        evidence=[{
            "source_type": "weather_forecast",
            "source_id": "weather-1",
            "summary": "未来 24 小时降雨 82mm",
            "observed_at": now,
            "fact_kind": "measured",
            "payload": {"rainfall_mm": 82},
        }],
        actions=[{
            "action_key": "drainage-a1",
            "title": "检查排水沟",
            "task_type": "drainage",
            "instructions": "清理堵塞点",
            "priority": "urgent",
            "acceptance_criteria": ["无明显堵塞"],
        }],
        status="pending",
        created_at=now,
    )


def _app(*, authenticated: bool) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse.error(code=exc.code, message=exc.message).model_dump(),
        )

    app.include_router(farm_agent.router, prefix="/api/v1")
    if authenticated:
        app.dependency_overrides[get_current_user] = _user
    return app


def test_inspection_requires_authentication_and_streams_for_owner(monkeypatch):
    assert TestClient(_app(authenticated=False)).post(
        "/api/v1/farm-agent/inspections/stream",
        json={"farm_id": 11},
    ).status_code == 401

    async def fake_stream_inspection(*, user_id, request):
        assert user_id == 7
        assert request.farm_id == 11
        yield {"type": "start", "run_id": "run-1", "stage": "run_started"}

    async def allow_owned_farm(*, user_id, farm_id):
        assert (user_id, farm_id) == (7, 11)

    monkeypatch.setattr(farm_agent.farm_agent_service, "stream_inspection", fake_stream_inspection)
    monkeypatch.setattr(
        farm_agent.farm_run_query_service,
        "require_owned_farm",
        allow_owned_farm,
    )
    response = TestClient(_app(authenticated=True)).post(
        "/api/v1/farm-agent/inspections/stream",
        json={"farm_id": 11},
    )
    assert response.status_code == 200
    assert '"run_id": "run-1"' in response.text


def test_inspection_rejects_cross_user_farm_before_opening_sse(monkeypatch):
    async def reject_cross_user(*, user_id, farm_id):
        raise ForbiddenError(message="无权访问目标资源")

    monkeypatch.setattr(
        farm_agent.farm_run_query_service,
        "require_owned_farm",
        reject_cross_user,
    )
    response = TestClient(_app(authenticated=True)).post(
        "/api/v1/farm-agent/inspections/stream",
        json={"farm_id": 99},
    )

    assert response.status_code == 403


def test_timeline_and_proposals_use_current_user(monkeypatch):
    captured: list[tuple[str, int]] = []

    async def fake_timeline(*, user_id, run_id):
        captured.append((run_id, user_id))
        return AgentRunTimelineResponse(run_id=run_id, farm_id=11, status="completed")

    monkeypatch.setattr(farm_agent.farm_run_query_service, "get_run_timeline", fake_timeline)
    monkeypatch.setattr(
        farm_agent.farm_proposal_service,
        "list_proposals",
        lambda *, user_id, farm_id, status: [_proposal()],
    )
    client = TestClient(_app(authenticated=True))

    timeline = client.get("/api/v1/farm-agent/runs/run-1/timeline")
    proposals = client.get("/api/v1/farm-agent/proposals?farm_id=11&status=pending")

    assert timeline.json()["data"]["run_id"] == "run-1"
    assert captured == [("run-1", 7)]
    assert proposals.json()["data"][0]["proposal_id"] == "proposal-1"


def test_approve_is_idempotent_at_api_boundary(monkeypatch):
    proposal = _proposal().model_copy(update={"status": "approved"})
    task = {
        "task_id": "task-1", "proposal_id": "proposal-1", "action_key": "drainage-a1",
        "farm_id": 11, "title": "检查排水沟", "task_type": "drainage",
        "instructions": "清理堵塞点", "acceptance_criteria": ["无明显堵塞"],
        "priority": "urgent", "status": "pending", "execution": {},
        "agent_verdict": {}, "created_at": datetime.now(timezone.utc),
        "updated_at": datetime.now(timezone.utc),
    }
    monkeypatch.setattr(
        farm_agent.farm_proposal_service,
        "approve",
        lambda *, user_id, proposal_id, request: (proposal, [task]),
    )
    payload = {
        "actions": [{
            "action_key": "drainage-a1", "title": "检查排水沟",
            "task_type": "drainage", "instructions": "清理堵塞点",
            "priority": "urgent", "acceptance_criteria": ["无明显堵塞"],
        }],
        "decision_note": "批准",
    }
    client = TestClient(_app(authenticated=True))

    first = client.post("/api/v1/farm-agent/proposals/proposal-1/approve", json=payload)
    second = client.post("/api/v1/farm-agent/proposals/proposal-1/approve", json=payload)

    assert first.json()["data"]["task_ids"] == ["task-1"]
    assert second.json()["data"]["task_ids"] == ["task-1"]
