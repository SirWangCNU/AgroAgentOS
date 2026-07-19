"""B10/B11 + demo_scenario_service 场景加载与幂等注入测试.

覆盖：
  - load_scenario 加载 4 个比赛场景 fixture
  - list_scenarios 返回 4 个 ScenarioMeta
  - inject_scenario_to_db 创建 sensor_readings + seasons + 同步 Field.current_season_id
  - 重复注入同一场景 → 幂等（created_sensors=0, skipped_sensors=N）
  - 注入未知场景 → NotFoundError
  - 注入到无权访问的农场 → ForbiddenError
  - 注入到字段缺失的农场 → AppException(409, SCENARIO_FIELD_MISMATCH)
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.sqlite import Base, sqlite_manager
from app.exceptions import AppException, ForbiddenError, NotFoundError
from app.models.farm import CropSeason, Farm, Field, SensorReading
from app.models.user import User
from app.services import demo_scenario_service


SCENARIO_IDS = ("rainstorm", "pest_outbreak", "nutrient_deficiency", "drought")


@pytest.fixture
def scenario_database(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    """内存 SQLite，monkeypatch demo_scenario_service 内部使用的 sqlite_manager.session."""
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
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
    demo_scenario_service.load_scenario.cache_clear()
    yield session_factory
    engine.dispose()
    demo_scenario_service.load_scenario.cache_clear()


def _seed_owner_and_farm(
    session_factory: sessionmaker[Session],
    *,
    field_names: tuple[str, ...] = ("A1", "A2", "A3"),
    owner_username: str = "demo-owner",
) -> dict[str, int]:
    with session_factory() as session:
        owner = User(
            username=owner_username,
            email=f"{owner_username}@example.com",
            hashed_password="hash",
        )
        other = User(
            username="other",
            email="other@example.com",
            hashed_password="hash",
        )
        session.add_all([owner, other])
        session.flush()
        farm = Farm(
            user_id=owner.id,
            name="阳光农场",
            location="江苏省南京市江宁区",
            area_mu=30.0,
            description="比赛演示专用农场",
        )
        session.add(farm)
        session.flush()
        for name in field_names:
            session.add(Field(farm_id=farm.id, name=name, area_mu=10.0))
        session.commit()
        return {
            "owner_id": owner.id,
            "other_id": other.id,
            "farm_id": farm.id,
        }


# ==================== load_scenario / list_scenarios ====================


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_load_scenario_returns_validated_fixture(scenario_id: str) -> None:
    """4 个场景 fixture 都能被 load_scenario 正确加载.

    fixture 内部的 scenario_id 是版本化的（如 rainstorm-v1），服务入参用短 ID（rainstorm），
    这里验证两者前缀匹配 + 关键字段非空。
    """
    scenario = demo_scenario_service.load_scenario(scenario_id)

    assert scenario.scenario_id.startswith(scenario_id)
    assert "-" in scenario.scenario_id  # 必须带版本后缀，如 -v1
    assert scenario.label
    assert scenario.farm
    assert scenario.weather
    assert len(scenario.fields) == 3  # A1/A2/A3
    assert [field.name for field in scenario.fields] == ["A1", "A2", "A3"]
    assert len(scenario.sensor_readings) > 0 or len(scenario.seasons) > 0


def test_load_scenario_caches_fixture() -> None:
    """load_scenario 使用 lru_cache，重复调用返回同一对象."""
    demo_scenario_service.load_scenario.cache_clear()
    first = demo_scenario_service.load_scenario("rainstorm")
    second = demo_scenario_service.load_scenario("rainstorm")
    assert first is second


def test_load_scenario_raises_not_found_for_unknown_scenario() -> None:
    with pytest.raises(NotFoundError) as exc_info:
        demo_scenario_service.load_scenario("unknown-scenario")
    assert exc_info.value.code == "DEMO_SCENARIO_NOT_FOUND"


def test_list_scenarios_returns_all_four_metas() -> None:
    """list_scenarios 必须返回 4 个场景元信息，缺文件降级为跳过."""
    metas = demo_scenario_service.list_scenarios()

    assert len(metas) == 4
    assert {meta.scenario_id for meta in metas} == set(SCENARIO_IDS)
    for meta in metas:
        assert meta.label
        assert meta.field_count == 3
        assert meta.sensor_count > 0
        assert meta.weather_summary


# ==================== inject_scenario_to_db ====================


@pytest.mark.parametrize("scenario_id", SCENARIO_IDS)
def test_inject_creates_sensors_seasons_and_syncs_field_pointer(
    scenario_database: sessionmaker[Session],
    scenario_id: str,
) -> None:
    """注入场景后：created_sensors>0, created_seasons>0, Field.current_season_id 非空."""
    seeded = _seed_owner_and_farm(scenario_database)

    report = demo_scenario_service.inject_scenario_to_db(
        user_id=seeded["owner_id"],
        farm_id=seeded["farm_id"],
        scenario_id=scenario_id,
    )

    assert report.scenario_id == scenario_id
    assert report.farm_id == seeded["farm_id"]
    assert report.created_sensors > 0
    assert report.created_seasons > 0
    assert report.skipped_sensors == 0
    assert set(report.fields_covered) == {"A1", "A2", "A3"}

    with scenario_database() as session:
        readings = (
            session.query(SensorReading)
            .filter(SensorReading.scenario_id == scenario_id)
            .all()
        )
        assert len(readings) == report.created_sensors
        seasons = (
            session.query(CropSeason)
            .join(Field, Field.id == CropSeason.field_id)
            .filter(Field.farm_id == seeded["farm_id"])
            .all()
        )
        assert len(seasons) == report.created_seasons
        fields = (
            session.query(Field).filter(Field.farm_id == seeded["farm_id"]).all()
        )
        for field in fields:
            assert field.current_season_id is not None
            season_ids = {season.id for season in seasons}
            assert field.current_season_id in season_ids


def test_inject_is_idempotent_on_repeated_calls(
    scenario_database: sessionmaker[Session],
) -> None:
    """连续两次注入同一场景：第二次 created_sensors=0, skipped_sensors 等于首次 created."""
    seeded = _seed_owner_and_farm(scenario_database)

    first = demo_scenario_service.inject_scenario_to_db(
        user_id=seeded["owner_id"],
        farm_id=seeded["farm_id"],
        scenario_id="pest_outbreak",
    )
    second = demo_scenario_service.inject_scenario_to_db(
        user_id=seeded["owner_id"],
        farm_id=seeded["farm_id"],
        scenario_id="pest_outbreak",
    )

    assert first.created_sensors > 0
    assert second.created_sensors == 0
    assert second.skipped_sensors == first.created_sensors
    assert second.created_seasons == 0
    assert second.updated_seasons == first.created_seasons


def test_inject_rejects_foreign_farm_with_forbidden(
    scenario_database: sessionmaker[Session],
) -> None:
    """注入到他人农场 → ForbiddenError."""
    seeded = _seed_owner_and_farm(scenario_database)

    with pytest.raises(ForbiddenError):
        demo_scenario_service.inject_scenario_to_db(
            user_id=seeded["other_id"],
            farm_id=seeded["farm_id"],
            scenario_id="rainstorm",
        )


def test_inject_rejects_missing_fields_with_409(
    scenario_database: sessionmaker[Session],
) -> None:
    """农场缺少 fixture 要求的地块 → AppException(409, SCENARIO_FIELD_MISMATCH)."""
    seeded = _seed_owner_and_farm(
        scenario_database, field_names=("A1",)
    )

    with pytest.raises(AppException) as exc_info:
        demo_scenario_service.inject_scenario_to_db(
            user_id=seeded["owner_id"],
            farm_id=seeded["farm_id"],
            scenario_id="rainstorm",
        )

    assert exc_info.value.status_code == 409
    assert exc_info.value.code == "SCENARIO_FIELD_MISMATCH"
    assert "A2" in exc_info.value.message
    assert "A3" in exc_info.value.message


def test_inject_unknown_scenario_raises_not_found(
    scenario_database: sessionmaker[Session],
) -> None:
    seeded = _seed_owner_and_farm(scenario_database)

    with pytest.raises(NotFoundError):
        demo_scenario_service.inject_scenario_to_db(
            user_id=seeded["owner_id"],
            farm_id=seeded["farm_id"],
            scenario_id="unknown-scenario",
        )


def test_inject_updates_season_stage_on_repeated_injection(
    scenario_database: sessionmaker[Session],
) -> None:
    """重复注入同一场景时，茬次的 current_stage 会被同步更新."""
    seeded = _seed_owner_and_farm(scenario_database)

    demo_scenario_service.inject_scenario_to_db(
        user_id=seeded["owner_id"],
        farm_id=seeded["farm_id"],
        scenario_id="rainstorm",
    )

    with scenario_database() as session:
        seasons_before = (
            session.query(CropSeason)
            .join(Field, Field.id == CropSeason.field_id)
            .filter(Field.farm_id == seeded["farm_id"])
            .all()
        )
        stages_before = {
            season.field_id: season.current_stage for season in seasons_before
        }

    demo_scenario_service.inject_scenario_to_db(
        user_id=seeded["owner_id"],
        farm_id=seeded["farm_id"],
        scenario_id="rainstorm",
    )

    with scenario_database() as session:
        seasons_after = (
            session.query(CropSeason)
            .join(Field, Field.id == CropSeason.field_id)
            .filter(Field.farm_id == seeded["farm_id"])
            .all()
        )
        assert len(seasons_after) == len(seasons_before)
        for season in seasons_after:
            assert season.current_stage == stages_before[season.field_id]


def test_inject_writes_sensor_readings_with_correct_source_tag(
    scenario_database: sessionmaker[Session],
) -> None:
    """注入的 SensorReading.source='demo_scenario', scenario_id 与请求一致."""
    seeded = _seed_owner_and_farm(scenario_database)

    demo_scenario_service.inject_scenario_to_db(
        user_id=seeded["owner_id"],
        farm_id=seeded["farm_id"],
        scenario_id="drought",
    )

    with scenario_database() as session:
        readings = (
            session.query(SensorReading)
            .filter(SensorReading.scenario_id == "drought")
            .all()
        )
        assert len(readings) > 0
        for reading in readings:
            assert reading.source == "demo_scenario"
            assert reading.scenario_id == "drought"
            assert reading.observed_at is not None


def test_inject_syncs_field_redundant_crop_fields(
    scenario_database: sessionmaker[Session],
) -> None:
    """注入后 Field.current_crop / growth_stage / planting_date 与茬次一致."""
    seeded = _seed_owner_and_farm(scenario_database)

    demo_scenario_service.inject_scenario_to_db(
        user_id=seeded["owner_id"],
        farm_id=seeded["farm_id"],
        scenario_id="pest_outbreak",
    )

    with scenario_database() as session:
        fields = (
            session.query(Field).filter(Field.farm_id == seeded["farm_id"]).all()
        )
        by_name = {field.name: field for field in fields}
        a2 = by_name["A2"]
        assert a2.current_crop == "玉米"
        assert a2.growth_stage == "大喇叭口期"
        assert a2.status == "planting"
