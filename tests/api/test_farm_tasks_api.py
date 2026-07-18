"""Farm Task 人工门控与复核流 API 契约测试。"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import farm_tasks
from app.exceptions import AppException
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.farm_agent import TaskResponse


def _user() -> User:
    return User(id=7, username="owner", hashed_password="unused", role="user", is_active=1)


def _task(status: str = "submitted") -> TaskResponse:
    now = datetime.now(timezone.utc)
    return TaskResponse(
        task_id="task-1", proposal_id="proposal-1", action_key="drainage-a1",
        farm_id=11, title="检查排水沟", task_type="drainage",
        instructions="清理堵塞点", acceptance_criteria=["无明显堵塞"],
        priority="urgent", status=status, execution={}, agent_verdict={},
        created_at=now, updated_at=now,
    )


def _app(*, authenticated: bool) -> FastAPI:
    app = FastAPI()

    @app.exception_handler(AppException)
    async def handle_app_exception(request: Request, exc: AppException) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ApiResponse.error(code=exc.code, message=exc.message).model_dump(),
        )

    app.include_router(farm_tasks.router, prefix="/api/v1")
    if authenticated:
        app.dependency_overrides[get_current_user] = _user
    return app


def test_human_task_decisions_require_authentication():
    client = TestClient(_app(authenticated=False))
    requests = [
        ("post", "/api/v1/farm-tasks/task-1/start", None),
        ("post", "/api/v1/farm-tasks/task-1/submit", {"note": "done"}),
        ("post", "/api/v1/farm-tasks/task-1/complete", {"note": "ok"}),
        ("post", "/api/v1/farm-tasks/task-1/return", {"note": "redo"}),
    ]
    for method, path, payload in requests:
        response = client.request(method, path, json=payload)
        assert response.status_code == 401


def test_task_routes_delegate_state_machine_to_service(monkeypatch):
    monkeypatch.setattr(farm_tasks.farm_task_service, "list_tasks", lambda **kwargs: [_task()])
    monkeypatch.setattr(farm_tasks.farm_task_service, "start", lambda **kwargs: _task("in_progress"))
    monkeypatch.setattr(farm_tasks.farm_task_service, "submit", lambda **kwargs: _task("submitted"))
    monkeypatch.setattr(farm_tasks.farm_task_service, "complete", lambda **kwargs: _task("completed"))
    monkeypatch.setattr(farm_tasks.farm_task_service, "return_task", lambda **kwargs: _task("returned"))
    client = TestClient(_app(authenticated=True))

    assert client.get("/api/v1/farm-tasks/").json()["data"][0]["status"] == "submitted"
    assert client.post("/api/v1/farm-tasks/task-1/start").json()["data"]["status"] == "in_progress"
    assert client.post("/api/v1/farm-tasks/task-1/submit", json={"note": "done"}).json()["data"]["status"] == "submitted"
    assert client.post("/api/v1/farm-tasks/task-1/complete", json={"note": "ok"}).json()["data"]["status"] == "completed"
    assert client.post("/api/v1/farm-tasks/task-1/return", json={"note": "redo"}).json()["data"]["status"] == "returned"


def test_verification_stream_leaves_task_submitted(monkeypatch):
    async def fake_verification(*, user_id, task_id):
        assert (user_id, task_id) == (7, "task-1")
        yield {
            "type": "complete", "run_id": "run-verify", "stage": "run_completed",
            "data": {"outcome": {"task_id": task_id, "task_status": "submitted"}},
        }

    monkeypatch.setattr(
        farm_tasks.farm_agent_service,
        "stream_task_verification",
        fake_verification,
    )
    response = TestClient(_app(authenticated=True)).post(
        "/api/v1/farm-tasks/task-1/verify/stream"
    )

    assert response.status_code == 200
    assert '"task_status": "submitted"' in response.text
