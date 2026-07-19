"""茬次（CropSeason）生命周期与 Field 联动测试.

覆盖：
  - _upsert_season 新建茬次（created=True）和幂等更新（created=False, current_stage 同步）
  - _sync_field_from_season 同步 Field.current_crop/growth_stage/planting_date/status/current_season_id
  - inject_scenario_to_db 端到端：茬次落库 + Field.current_season_id 指针
  - 多场景多次注入推进茬次生育期（同一 season_code 不同 stage）
  - 茬次状态机：planning → growing → harvested
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Any, Iterator

import pytest
from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.sqlite import Base, sqlite_manager
from app.models.farm import CropSeason, Farm, Field
from app.models.user import User
from app.services import demo_scenario_service
from app.services.demo_scenario_service import (
    DemoScenarioSeason,
    _sync_field_from_season,
    _upsert_season,
)


@pytest.fixture
def season_database(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    # 与生产 sqlite_manager.connect 保持一致：启用外键级联（ON DELETE CASCADE 才会生效）
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn: Any, connection_record: Any) -> None:
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

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


def _seed_farm_and_field(
    session_factory: sessionmaker[Session],
    *,
    field_name: str = "A1",
) -> dict[str, int]:
    with session_factory() as session:
        owner = User(
            username="season-owner",
            email="season@example.com",
            hashed_password="hash",
        )
        session.add(owner)
        session.flush()
        farm = Farm(user_id=owner.id, name="茬次农场", location="江苏南京")
        session.add(farm)
        session.flush()
        field = Field(farm_id=farm.id, name=field_name, area_mu=10.0)
        session.add(field)
        session.flush()
        session.commit()
        return {
            "owner_id": owner.id,
            "farm_id": farm.id,
            "field_id": field.id,
        }


def _make_season_payload(
    *,
    field_name: str = "A1",
    crop_name: str = "玉米",
    season_code: str = "2026-S1",
    start_date: date = date(2026, 6, 5),
    current_stage: str = "大喇叭口期",
    status: str = "growing",
    area_mu: float = 10.0,
) -> DemoScenarioSeason:
    return DemoScenarioSeason(
        field_name=field_name,
        crop_name=crop_name,
        variety="苏玉29",
        season_code=season_code,
        start_date=start_date,
        expected_harvest=date(2026, 9, 28),
        current_stage=current_stage,
        area_mu=area_mu,
        target_yield="600 kg/亩",
        status=status,
    )


# ==================== _upsert_season 单元测试 ====================


def test_upsert_season_creates_new_season(season_database: sessionmaker[Session]) -> None:
    """首次 upsert → created=True，茬次字段写入正确."""
    seeded = _seed_farm_and_field(season_database)
    payload = _make_season_payload(current_stage="拔节期")

    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        season, created = _upsert_season(session, field=field, season_payload=payload)
        session.commit()
        season_id = season.id

    assert created is True
    assert season_id > 0

    with season_database() as session:
        saved = (
            session.query(CropSeason).filter(CropSeason.id == season_id).one()
        )
        assert saved.field_id == seeded["field_id"]
        assert saved.crop_name == "玉米"
        assert saved.variety == "苏玉29"
        assert saved.season_code == "2026-S1"
        assert saved.current_stage == "拔节期"
        assert saved.status == "growing"
        assert saved.area_mu == 10.0
        assert saved.target_yield == "600 kg/亩"


def test_upsert_season_updates_existing_same_fingerprint(
    season_database: sessionmaker[Session],
) -> None:
    """同 (field_id, season_code, start_date) 重复 upsert → created=False, 字段被同步."""
    seeded = _seed_farm_and_field(season_database)
    first_payload = _make_season_payload(current_stage="拔节期", status="growing")

    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        first_season, first_created = _upsert_season(
            session, field=field, season_payload=first_payload
        )
        session.commit()
        first_season_id = first_season.id

    second_payload = _make_season_payload(current_stage="抽穗期", status="growing")

    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        second_season, second_created = _upsert_season(
            session, field=field, season_payload=second_payload
        )
        session.commit()
        second_season_id = second_season.id

    assert first_created is True
    assert second_created is False
    assert first_season_id == second_season_id

    with season_database() as session:
        saved = (
            session.query(CropSeason).filter(CropSeason.id == second_season_id).one()
        )
        assert saved.current_stage == "抽穗期"


def test_upsert_season_treats_different_season_code_as_new(
    season_database: sessionmaker[Session],
) -> None:
    """同一 field 不同 season_code → 视为新茬次（created=True）."""
    seeded = _seed_farm_and_field(season_database)
    s1_payload = _make_season_payload(season_code="2026-S1", current_stage="成熟期")
    s2_payload = _make_season_payload(season_code="2026-S2", current_stage="苗期")

    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        s1, c1 = _upsert_season(session, field=field, season_payload=s1_payload)
        s2, c2 = _upsert_season(session, field=field, season_payload=s2_payload)
        session.commit()
        s1_id, s2_id = s1.id, s2.id

    assert c1 is True
    assert c2 is True
    assert s1_id != s2_id

    with season_database() as session:
        seasons = (
            session.query(CropSeason)
            .filter(CropSeason.field_id == seeded["field_id"])
            .order_by(CropSeason.id.asc())
            .all()
        )
        assert len(seasons) == 2
        assert {s.season_code for s in seasons} == {"2026-S1", "2026-S2"}


# ==================== _sync_field_from_season 单元测试 ====================


def test_sync_field_from_season_propagates_crop_and_stage(
    season_database: sessionmaker[Session],
) -> None:
    """茬次同步：Field.current_crop / growth_stage / planting_date / status / current_season_id 全部对齐."""
    seeded = _seed_farm_and_field(season_database)
    payload = _make_season_payload(
        crop_name="玉米",
        current_stage="大喇叭口期",
        start_date=date(2026, 6, 5),
        status="growing",
    )

    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        season, _ = _upsert_season(session, field=field, season_payload=payload)
        _sync_field_from_season(field, season)
        session.commit()

    with season_database() as session:
        saved = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        assert saved.current_crop == "玉米"
        assert saved.growth_stage == "大喇叭口期"
        assert saved.planting_date == date(2026, 6, 5)
        assert saved.expected_harvest == date(2026, 9, 28)
        assert saved.status == "planting"
        assert saved.current_season_id is not None


def test_sync_field_from_season_handles_status_transitions(
    season_database: sessionmaker[Session],
) -> None:
    """茬次 status=growing 时，field.status 应被设为 planting."""
    seeded = _seed_farm_and_field(season_database)
    payload = _make_season_payload(status="growing")

    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        field.status = "idle"
        season, _ = _upsert_season(session, field=field, season_payload=payload)
        _sync_field_from_season(field, season)
        session.commit()

    with season_database() as session:
        saved = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        assert saved.status == "planting"


# ==================== inject_scenario_to_db 端到端茬次联动 ====================


def test_inject_creates_seasons_and_sets_current_season_pointer(
    season_database: sessionmaker[Session],
) -> None:
    """注入场景后：每个地块都有 1 个茬次，Field.current_season_id 指向它."""
    with season_database() as session:
        owner = User(
            username="inject-owner",
            email="inject@example.com",
            hashed_password="hash",
        )
        session.add(owner)
        session.flush()
        farm = Farm(user_id=owner.id, name="阳光农场", location="江苏南京")
        session.add(farm)
        session.flush()
        for name in ("A1", "A2", "A3"):
            session.add(Field(farm_id=farm.id, name=name, area_mu=10.0))
        session.commit()
        owner_id, farm_id = owner.id, farm.id

    report = demo_scenario_service.inject_scenario_to_db(
        user_id=owner_id,
        farm_id=farm_id,
        scenario_id="pest_outbreak",
    )

    assert report.created_seasons == 3

    with season_database() as session:
        fields = (
            session.query(Field).filter(Field.farm_id == farm_id).all()
        )
        for field in fields:
            assert field.current_season_id is not None
            season = (
                session.query(CropSeason)
                .filter(CropSeason.id == field.current_season_id)
                .one()
            )
            assert season.field_id == field.id
            assert season.crop_name == field.current_crop
            assert season.current_stage == field.growth_stage


def test_inject_advances_stage_when_same_season_re_injected_with_new_stage(
    season_database: sessionmaker[Session],
) -> None:
    """同一 season_code 不同 current_stage 的 fixture 注入时，茬次 stage 被推进.

    模拟：先注入 rainstorm（A1 水稻分蘖期），再注入 pest_outbreak（A1 水稻拔节期）。
    两个 fixture 的 season_code 都是 2026-S1，start_date 都是 2026-05-28，
    但 current_stage 不同，应该被更新而不是新建。
    """
    with season_database() as session:
        owner = User(
            username="advance-owner",
            email="advance@example.com",
            hashed_password="hash",
        )
        session.add(owner)
        session.flush()
        farm = Farm(user_id=owner.id, name="推进农场", location="江苏南京")
        session.add(farm)
        session.flush()
        for name in ("A1", "A2", "A3"):
            session.add(Field(farm_id=farm.id, name=name, area_mu=10.0))
        session.commit()
        owner_id, farm_id = owner.id, farm.id

    demo_scenario_service.inject_scenario_to_db(
        user_id=owner_id, farm_id=farm_id, scenario_id="rainstorm"
    )
    with season_database() as session:
        a1_field = (
            session.query(Field).filter(Field.farm_id == farm_id, Field.name == "A1").one()
        )
        first_season_id = a1_field.current_season_id
        first_stage = (
            session.query(CropSeason)
            .filter(CropSeason.id == first_season_id)
            .one()
            .current_stage
        )

    demo_scenario_service.inject_scenario_to_db(
        user_id=owner_id, farm_id=farm_id, scenario_id="pest_outbreak"
    )
    with season_database() as session:
        a1_field = (
            session.query(Field).filter(Field.farm_id == farm_id, Field.name == "A1").one()
        )
        second_season_id = a1_field.current_season_id
        second_stage = (
            session.query(CropSeason)
            .filter(CropSeason.id == second_season_id)
            .one()
            .current_stage
        )

    assert second_season_id == first_season_id
    assert second_stage != first_stage
    assert second_stage == "拔节期"


# ==================== 茬次状态机：planning → growing → harvested ====================


def test_season_status_lifecycle_via_upsert(
    season_database: sessionmaker[Session],
) -> None:
    """茬次状态机：planning → growing → harvested 通过 _upsert_season 推进."""
    seeded = _seed_farm_and_field(season_database)

    planning_payload = _make_season_payload(
        current_stage="备播期", status="planning"
    )
    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        season_planning, c1 = _upsert_season(
            session, field=field, season_payload=planning_payload
        )
        session.commit()
        season_id = season_planning.id

    assert c1 is True

    growing_payload = _make_season_payload(
        current_stage="拔节期", status="growing"
    )
    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        season_growing, c2 = _upsert_season(
            session, field=field, season_payload=growing_payload
        )
        session.commit()

    assert c2 is False
    assert season_growing.id == season_id

    harvested_payload = _make_season_payload(
        current_stage="成熟期", status="harvested"
    )
    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        season_harvested, c3 = _upsert_season(
            session, field=field, season_payload=harvested_payload
        )
        session.commit()

    assert c3 is False
    assert season_harvested.id == season_id

    with season_database() as session:
        final = (
            session.query(CropSeason).filter(CropSeason.id == season_id).one()
        )
        assert final.status == "harvested"
        assert final.current_stage == "成熟期"


def test_season_belongs_to_field_and_cascades_on_field_delete(
    season_database: sessionmaker[Session],
) -> None:
    """茬次外键 field_id ON DELETE CASCADE：删除地块时茬次一起删除."""
    seeded = _seed_farm_and_field(season_database)
    payload = _make_season_payload()

    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        season, _ = _upsert_season(session, field=field, season_payload=payload)
        session.commit()
        season_id = season.id

    with season_database() as session:
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        session.delete(field)
        session.commit()

    with season_database() as session:
        deleted = (
            session.query(CropSeason).filter(CropSeason.id == season_id).first()
        )
        assert deleted is None
