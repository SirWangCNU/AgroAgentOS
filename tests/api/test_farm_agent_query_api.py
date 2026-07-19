"""B9 Farm Agent 比赛演示场景/感知/事件/茬次查询 API 契约测试.

覆盖 5 个新 endpoint:
  - GET  /farm-agent/scenarios
  - POST /farm-agent/scenarios/{scenario_id}/inject
  - GET  /farm-agent/sensors
  - GET  /farm-agent/events
  - GET  /farm-agent/seasons
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.v1 import farm_agent
from app.exceptions import AppException, ForbiddenError, NotFoundError
from app.models.user import User
from app.schemas.common import ApiResponse
from app.services import farm_query_service


def _user() -> User:
    return User(
        id=7,
        username="owner",
        hashed_password="unused",
        role="user",
        is_active=1,
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


def _sensor_row(*, id: int = 1, field_id: int = 11, sensor_type: str = "soil_moisture") -> Any:
    """构造一个最小可被 model_validate 的伪 ORM 对象."""
    from app.models.farm import SensorReading

    reading = SensorReading(
        field_id=field_id,
        sensor_type=sensor_type,
        value_float=42.5,
        unit="%",
        observed_at=datetime(2026, 7, 18, 8, 0, 0, tzinfo=timezone.utc),
        source="demo_scenario",
        scenario_id="rainstorm",
        note="",
    )
    reading.id = id
    reading.set_value({"raw": 42.5})
    return reading


def _event_row(*, id: int = 1, field_id: int = 11) -> Any:
    from app.models.farm_agent import FarmEvent

    event = FarmEvent(
        field_id=field_id,
        event_type="spraying",
        event_time=datetime(2026, 7, 25, 9, 30, 0, tzinfo=timezone.utc),
        operator="user:7",
        source="task_completion",
        related_task_id="task-1",
        note="完成玉米田喷雾",
    )
    event.id = id
    event.set_inputs([{"material": "甲维盐", "rate_per_mu": "10ml"}])
    return event


def _season_row(*, id: int = 1, field_id: int = 11) -> Any:
    from app.models.farm import CropSeason

    season = CropSeason(
        field_id=field_id,
        crop_name="玉米",
        variety="苏玉29",
        season_code="2026-S1",
        start_date=date(2026, 6, 5),
        expected_harvest=date(2026, 9, 28),
        current_stage="大喇叭口期",
        area_mu=10.0,
        target_yield="600 kg/亩",
        status="growing",
    )
    season.id = id
    return season


# ==================== 鉴权 ====================


def test_all_new_endpoints_require_authentication() -> None:
    """未登录访问 5 个 endpoint 都返回 401."""
    client = TestClient(_app(authenticated=False))
    assert client.get("/api/v1/farm-agent/scenarios").status_code == 401
    assert client.get("/api/v1/farm-agent/sensors?farm_id=11").status_code == 401
    assert client.get("/api/v1/farm-agent/events?farm_id=11").status_code == 401
    assert client.get("/api/v1/farm-agent/seasons?farm_id=11").status_code == 401
    assert client.post(
        "/api/v1/farm-agent/scenarios/rainstorm/inject", json={"farm_id": 11}
    ).status_code == 401


# ==================== GET /scenarios ====================


def test_list_scenarios_returns_metas(monkeypatch) -> None:
    """GET /scenarios 返回 4 个场景元信息数组."""
    from app.services import demo_scenario_service

    metas = demo_scenario_service.list_scenarios()
    monkeypatch.setattr(farm_query_service, "list_scenario_metas", lambda: metas)

    response = TestClient(_app(authenticated=True)).get("/api/v1/farm-agent/scenarios")
    assert response.status_code == 200
    data = response.json()["data"]
    assert isinstance(data, list)
    assert len(data) == 4
    scenario_ids = {item["scenario_id"] for item in data}
    assert scenario_ids == {
        "rainstorm",
        "pest_outbreak",
        "nutrient_deficiency",
        "drought",
    }
    for item in data:
        assert item["label"]
        assert item["field_count"] == 3
        assert item["sensor_count"] > 0
        assert item["weather_summary"]


# ==================== POST /scenarios/{id}/inject ====================


def test_inject_scenario_returns_injection_report(monkeypatch) -> None:
    """POST inject 成功时返回 InjectionReport 字段."""
    captured: dict[str, Any] = {}

    def fake_inject(*, user_id, farm_id, scenario_id):
        captured.update(user_id=user_id, farm_id=farm_id, scenario_id=scenario_id)
        from app.services.demo_scenario_service import InjectionReport

        return InjectionReport(
            scenario_id=scenario_id,
            farm_id=farm_id,
            created_sensors=6,
            skipped_sensors=0,
            created_seasons=3,
            updated_seasons=0,
            fields_covered=["A1", "A2", "A3"],
        )

    monkeypatch.setattr(farm_query_service, "inject_scenario", fake_inject)

    response = TestClient(_app(authenticated=True)).post(
        "/api/v1/farm-agent/scenarios/rainstorm/inject",
        json={"farm_id": 11},
    )
    assert response.status_code == 200
    data = response.json()["data"]
    assert data["scenario_id"] == "rainstorm"
    assert data["farm_id"] == 11
    assert data["created_sensors"] == 6
    assert data["created_seasons"] == 3
    assert data["fields_covered"] == ["A1", "A2", "A3"]
    assert captured == {"user_id": 7, "farm_id": 11, "scenario_id": "rainstorm"}


def test_inject_scenario_propagates_forbidden(monkeypatch) -> None:
    """POST inject 越权访问他人农场 → 403."""
    def reject(*, user_id, farm_id, scenario_id):
        raise ForbiddenError(message="无权访问目标农场")

    monkeypatch.setattr(farm_query_service, "inject_scenario", reject)

    response = TestClient(_app(authenticated=True)).post(
        "/api/v1/farm-agent/scenarios/rainstorm/inject",
        json={"farm_id": 99},
    )
    assert response.status_code == 403


def test_inject_scenario_propagates_not_found(monkeypatch) -> None:
    """POST inject 未知 scenario_id → 404."""
    def raise_not_found(*, user_id, farm_id, scenario_id):
        raise NotFoundError(message="未知场景", code="DEMO_SCENARIO_NOT_FOUND")

    monkeypatch.setattr(farm_query_service, "inject_scenario", raise_not_found)

    response = TestClient(_app(authenticated=True)).post(
        "/api/v1/farm-agent/scenarios/unknown/inject",
        json={"farm_id": 11},
    )
    assert response.status_code == 404


# ==================== GET /sensors ====================


def test_list_sensors_passes_filters_and_returns_rows(monkeypatch) -> None:
    """GET /sensors 把 query 参数传给 service 并返回序列化结果."""
    captured: dict[str, Any] = {}

    def fake_list(*, user_id, farm_id, field_id, sensor_type, days):
        captured.update(
            user_id=user_id,
            farm_id=farm_id,
            field_id=field_id,
            sensor_type=sensor_type,
            days=days,
        )
        return [_sensor_row(id=1), _sensor_row(id=2, sensor_type="pest_count")]

    monkeypatch.setattr(farm_query_service, "list_sensor_readings", fake_list)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/sensors?farm_id=11&field_id=21&sensor_type=soil_moisture&days=3"
    )
    assert response.status_code == 200
    assert captured == {
        "user_id": 7,
        "farm_id": 11,
        "field_id": 21,
        "sensor_type": "soil_moisture",
        "days": 3,
    }
    data = response.json()["data"]
    assert len(data) == 2
    assert data[0]["sensor_type"] == "soil_moisture"
    assert data[0]["value_float"] == 42.5
    assert data[0]["scenario_id"] == "rainstorm"
    assert data[1]["sensor_type"] == "pest_count"


def test_list_sensors_uses_default_days(monkeypatch) -> None:
    """GET /sensors 不传 days 时默认 7 天."""
    captured: dict[str, Any] = {}

    def fake_list(*, user_id, farm_id, field_id, sensor_type, days):
        captured["days"] = days
        return []

    monkeypatch.setattr(farm_query_service, "list_sensor_readings", fake_list)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/sensors?farm_id=11"
    )
    assert response.status_code == 200
    assert captured["days"] == 7


def test_list_sensors_rejects_invalid_days() -> None:
    """GET /sensors days 越界（<1 或 >365）→ 422."""
    client = TestClient(_app(authenticated=True))
    assert client.get("/api/v1/farm-agent/sensors?farm_id=11&days=0").status_code == 422
    assert client.get("/api/v1/farm-agent/sensors?farm_id=11&days=400").status_code == 422


def test_list_sensors_propagates_forbidden(monkeypatch) -> None:
    """GET /sensors 越权 → 403."""
    def reject(*, user_id, farm_id, field_id, sensor_type, days):
        raise ForbiddenError(message="无权访问目标农场")

    monkeypatch.setattr(farm_query_service, "list_sensor_readings", reject)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/sensors?farm_id=99"
    )
    assert response.status_code == 403


# ==================== GET /events ====================


def test_list_events_passes_filters_and_returns_rows(monkeypatch) -> None:
    """GET /events 把 query 参数传给 service 并返回序列化结果."""
    captured: dict[str, Any] = {}

    def fake_list(*, user_id, farm_id, field_id, days):
        captured.update(user_id=user_id, farm_id=farm_id, field_id=field_id, days=days)
        return [_event_row(id=1), _event_row(id=2)]

    monkeypatch.setattr(farm_query_service, "list_farm_events", fake_list)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/events?farm_id=11&field_id=21&days=14"
    )
    assert response.status_code == 200
    assert captured == {
        "user_id": 7,
        "farm_id": 11,
        "field_id": 21,
        "days": 14,
    }
    data = response.json()["data"]
    assert len(data) == 2
    assert data[0]["event_type"] == "spraying"
    assert data[0]["source"] == "task_completion"
    assert data[0]["related_task_id"] == "task-1"
    assert data[0]["inputs"] == [{"material": "甲维盐", "rate_per_mu": "10ml"}]


def test_list_events_uses_default_days(monkeypatch) -> None:
    """GET /events 不传 days 时默认 14 天."""
    captured: dict[str, Any] = {}

    def fake_list(*, user_id, farm_id, field_id, days):
        captured["days"] = days
        return []

    monkeypatch.setattr(farm_query_service, "list_farm_events", fake_list)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/events?farm_id=11"
    )
    assert response.status_code == 200
    assert captured["days"] == 14


def test_list_events_propagates_forbidden(monkeypatch) -> None:
    """GET /events 越权 → 403."""
    def reject(*, user_id, farm_id, field_id, days):
        raise ForbiddenError(message="无权访问目标农场")

    monkeypatch.setattr(farm_query_service, "list_farm_events", reject)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/events?farm_id=99"
    )
    assert response.status_code == 403


# ==================== GET /seasons ====================


def test_list_seasons_passes_filters_and_returns_rows(monkeypatch) -> None:
    """GET /seasons 把 query 参数传给 service 并返回序列化结果."""
    captured: dict[str, Any] = {}

    def fake_list(*, user_id, farm_id, field_id, status):
        captured.update(user_id=user_id, farm_id=farm_id, field_id=field_id, status=status)
        return [_season_row(id=1), _season_row(id=2)]

    monkeypatch.setattr(farm_query_service, "list_crop_seasons", fake_list)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/seasons?farm_id=11&field_id=21&status=growing"
    )
    assert response.status_code == 200
    assert captured == {
        "user_id": 7,
        "farm_id": 11,
        "field_id": 21,
        "status": "growing",
    }
    data = response.json()["data"]
    assert len(data) == 2
    assert data[0]["crop_name"] == "玉米"
    assert data[0]["variety"] == "苏玉29"
    assert data[0]["season_code"] == "2026-S1"
    assert data[0]["current_stage"] == "大喇叭口期"
    assert data[0]["status"] == "growing"
    assert data[0]["start_date"] == "2026-06-05"


def test_list_seasons_without_status_passes_none(monkeypatch) -> None:
    """GET /seasons 不传 status 时 service 收到 None."""
    captured: dict[str, Any] = {}

    def fake_list(*, user_id, farm_id, field_id, status):
        captured["status"] = status
        return []

    monkeypatch.setattr(farm_query_service, "list_crop_seasons", fake_list)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/seasons?farm_id=11"
    )
    assert response.status_code == 200
    assert captured["status"] is None


def test_list_seasons_propagates_forbidden(monkeypatch) -> None:
    """GET /seasons 越权 → 403."""
    def reject(*, user_id, farm_id, field_id, status):
        raise ForbiddenError(message="无权访问目标农场")

    monkeypatch.setattr(farm_query_service, "list_crop_seasons", reject)

    response = TestClient(_app(authenticated=True)).get(
        "/api/v1/farm-agent/seasons?farm_id=99"
    )
    assert response.status_code == 403
