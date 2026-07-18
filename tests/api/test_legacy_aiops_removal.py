"""旧 AIOps 路由移除和历史只读兼容测试。"""

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.v1 import farm_agent, farm_tasks, history


def test_legacy_aiops_routes_are_not_registered():
    app = FastAPI()
    app.include_router(farm_agent.router, prefix="/api/v1")
    app.include_router(farm_tasks.router, prefix="/api/v1")
    client = TestClient(app)

    assert client.post("/api/v1/aiops/diagnose", json={}).status_code == 404
    assert client.get("/api/v1/aiops/timeline/x").status_code == 404


def test_history_reads_aiops_and_farm_agent_sources(monkeypatch):
    requested_sources: list[str | None] = []

    async def fake_list_records(*, page, page_size, source):
        requested_sources.append(source)
        return {"total": 0, "page": page, "page_size": page_size, "records": []}

    monkeypatch.setattr(history.history_service, "list_records", fake_list_records)
    app = FastAPI()
    app.include_router(history.router, prefix="/api/v1")
    client = TestClient(app)

    assert client.get("/api/v1/history?source=aiops").status_code == 200
    assert client.get("/api/v1/history?source=farm_agent").status_code == 200
    assert requested_sources == ["aiops", "farm_agent"]
