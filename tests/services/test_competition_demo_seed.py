"""比赛演示 fixture、幂等 seed 与显式天气开关测试。"""

from __future__ import annotations

import importlib.util
import json
from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import Settings
from app.core.sqlite import Base
from app.models.farm import Farm, Field
from app.models.trajectory import TrajectoryFile
from app.models.user import User
from app.exceptions import AppException
from app.schemas.farm_agent import FarmInspectionRequest
from app.services import farm_agent_service, farm_risk_service

ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = ROOT / "app" / "data" / "demo_rainstorm_scenario.json"
SCRIPT_PATH = ROOT / "scripts" / "seed_competition_demo.py"


def _load_seed_module():
    spec = importlib.util.spec_from_file_location("seed_competition_demo", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def demo_database(monkeypatch) -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def test_session():
        session = session_factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    module = _load_seed_module()
    monkeypatch.setattr(module.sqlite_manager, "session", test_session)
    monkeypatch.setattr(module, "DEFAULT_FIXTURE_PATH", FIXTURE_PATH)
    return session_factory, module


def test_rainstorm_fixture_is_versioned_and_contains_only_source_facts():
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    # fixture 只包含"源事实"（不含 agent 产出的 proposal/verdict/agent_plan/agent_report），
    # 但允许扩展茬次/感知/预期风险这三类输入数据。
    assert set(fixture) == {
        "scenario_id", "label", "farm", "weather", "fields", "trajectory_summaries",
        "seasons", "sensor_readings", "expected_risks",
    }
    assert fixture["scenario_id"] == "rainstorm-v1"
    assert fixture["label"] == "比赛演示数据"
    assert fixture["farm"] == {
        "external_key": "demo-sunshine-farm",
        "name": "阳光农场",
        "location": "江苏省南京市江宁区",
        "area_mu": 30.0,
        "description": "比赛演示专用农场",
    }
    assert fixture["weather"]["rainfall_24h_mm"] == 82.0
    assert [field["name"] for field in fixture["fields"]] == ["A1", "A2", "A3"]
    assert fixture["fields"][0]["current_crop"] == "水稻"
    assert fixture["fields"][0]["growth_stage"] == "分蘖期"
    assert len(fixture["trajectory_summaries"]) == 1
    assert fixture["trajectory_summaries"][0]["quality"] == "low"
    # 扩展的源事实字段：茬次、感知读数、预期风险
    assert len(fixture["seasons"]) == 3
    assert len(fixture["sensor_readings"]) > 0
    assert any(risk["risk_key_prefix"].startswith("weather") for risk in fixture["expected_risks"])
    serialized = json.dumps(fixture, ensure_ascii=False).lower()
    for forbidden in ("proposal", "verdict", "agent_plan", "agent_report"):
        assert forbidden not in serialized


def test_seed_is_idempotent_and_scoped_to_requested_user(demo_database):
    session_factory, module = demo_database
    with session_factory() as session:
        owner = User(
            username="demo-owner", email="demo@example.com", hashed_password="existing"
        )
        other = User(
            username="other-owner", email="other@example.com", hashed_password="existing"
        )
        session.add_all([owner, other])
        session.flush()
        session.add(Farm(user_id=other.id, name="阳光农场", description="用户自己的数据"))
        session.commit()

    first = module.seed_competition_demo(username="demo-owner")
    second = module.seed_competition_demo(username="demo-owner")

    assert first.farm_id == second.farm_id
    with session_factory() as session:
        owner = session.query(User).filter(User.username == "demo-owner").one()
        other = session.query(User).filter(User.username == "other-owner").one()
        demo_farms = session.query(Farm).filter(Farm.user_id == owner.id).all()
        assert len(demo_farms) == 1
        demo_farm = demo_farms[0]
        assert demo_farm.name == "阳光农场"
        assert [row.name for row in session.query(Field).filter(
            Field.farm_id == demo_farm.id
        ).order_by(Field.name).all()] == ["A1", "A2", "A3"]
        assert session.query(TrajectoryFile).join(Field).filter(
            Field.farm_id == demo_farm.id
        ).count() == 1
        assert session.query(Farm).filter(Farm.user_id == other.id).count() == 1
        assert session.query(Farm).filter(
            Farm.user_id == other.id, Farm.description == "用户自己的数据"
        ).count() == 1


def test_seed_rejects_unknown_user_without_creating_credentials(demo_database):
    session_factory, module = demo_database

    with pytest.raises(module.DemoSeedError, match="用户不存在"):
        module.seed_competition_demo(username="missing-user")

    with session_factory() as session:
        assert session.query(User).count() == 0


def test_competition_demo_is_disabled_by_default():
    assert Settings(_env_file=None).competition_demo_enabled is False


@pytest.mark.asyncio
async def test_demo_weather_requires_explicit_request_and_enabled_config(monkeypatch):
    real_request = FarmInspectionRequest(farm_id=1)
    assert isinstance(
        farm_agent_service._select_inspection_weather_provider(real_request),
        farm_risk_service.WeatherServiceProvider,
    )

    demo_request = FarmInspectionRequest(farm_id=1, demo_scenario="rainstorm")
    monkeypatch.setattr(farm_agent_service.settings, "competition_demo_enabled", False)
    with pytest.raises(AppException) as exc_info:
        farm_agent_service._select_inspection_weather_provider(demo_request)
    assert exc_info.value.code == "COMPETITION_DEMO_DISABLED"

    monkeypatch.setattr(farm_agent_service.settings, "competition_demo_enabled", True)
    provider = farm_agent_service._select_inspection_weather_provider(demo_request)
    forecast = await provider.get_forecast_with_alerts("任意真实位置")
    assert forecast.source == "competition-demo:rainstorm-v1"
    assert forecast.daily[0].precipitation_mm == 82.0
