"""B8 任务完成自动写 FarmEvent 的事件流测试.

覆盖：
  - _map_task_type_to_event_type 各类映射（spraying/pest_control/fertilize/irrigate/drainage/...）
  - complete() 完成任务时自动写入 FarmEvent(source=task_completion)
  - FarmEvent 字段：event_type, source, related_task_id, field_id, season_id, operator
  - uq_event_task_type 幂等约束：再次调用 _maybe_record_completion_event 不重复写
  - 任务无 field_id 时不写事件
  - 输入品清单从 execution 推导（note + attachment_urls）
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.sqlite import Base, sqlite_manager
from app.exceptions import AppException
from app.models.farm import CropSeason, Farm, Field
from app.models.farm_agent import FarmEvent, FarmTask
from app.models.user import User
from app.schemas.farm_agent import (
    TaskExecution,
    TaskSubmitRequest,
    TaskVerificationDraft,
)
from app.services import farm_task_service


@pytest.fixture
def event_database(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
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
    yield session_factory
    engine.dispose()


def _seed_farm_with_field(
    session_factory: sessionmaker[Session],
) -> dict[str, int]:
    with session_factory() as session:
        owner = User(
            username="event-owner",
            email="event@example.com",
            hashed_password="hash",
        )
        session.add(owner)
        session.flush()
        farm = Farm(user_id=owner.id, name="事件流农场", location="江苏南京")
        session.add(farm)
        session.flush()
        field = Field(farm_id=farm.id, name="A1", area_mu=10.0, current_crop="水稻")
        session.add(field)
        session.flush()
        session.commit()
        return {
            "owner_id": owner.id,
            "farm_id": farm.id,
            "field_id": field.id,
        }


def _seed_pending_task(
    session_factory: sessionmaker[Session],
    *,
    farm_id: int,
    field_id: int | None,
    task_type: str = "spraying",
    task_id: str = "task-event-1",
    title: str = "玉米田喷雾防治草地贪夜蛾",
) -> str:
    with session_factory() as session:
        task = FarmTask(
            task_id=task_id,
            farm_id=farm_id,
            field_id=field_id,
            title=title,
            task_type=task_type,
            instructions="按推荐剂量喷施",
            status="pending",
        )
        task.set_acceptance_criteria(["喷施均匀", "提交作业照片"])
        session.add(task)
        session.commit()
    return task_id


def _drive_task_to_completed(
    *,
    user_id: int,
    task_id: str,
    note: str = "已完成作业",
    attachment_urls: list[str] | None = None,
) -> FarmTask:
    """驱动任务 pending → in_progress → submitted → completed 全流程."""
    farm_task_service.start(user_id=user_id, task_id=task_id)
    farm_task_service.submit(
        user_id=user_id,
        task_id=task_id,
        request=TaskSubmitRequest(
            note=note,
            trajectory_file_ids=[],
            attachment_urls=attachment_urls or [],
        ),
    )
    farm_task_service.save_verification_draft(
        user_id=user_id,
        task_id=task_id,
        verdict=TaskVerificationDraft(verdict="pass", note="证据充分"),
    )
    return farm_task_service.complete(user_id=user_id, task_id=task_id, note=note)


# ==================== _map_task_type_to_event_type 单元测试 ====================


@pytest.mark.parametrize(
    ("task_type", "expected_event_type"),
    [
        ("spraying", "spraying"),
        ("pest_control", "spraying"),
        ("fertilizing", "fertilizing"),
        ("fertilize", "fertilizing"),
        ("irrigating", "irrigating"),
        ("irrigate", "irrigating"),
        ("drainage", "irrigating"),
        ("scouting", "scouting"),
        ("harvest", "harvest"),
        ("seeding", "seeding"),
        ("unknown_type", "scouting"),
        ("SPRAYING", "spraying"),
        ("  Spraying  ", "spraying"),
    ],
)
def test_map_task_type_to_event_type(task_type: str, expected_event_type: str) -> None:
    assert farm_task_service._map_task_type_to_event_type(task_type) == expected_event_type


# ==================== complete() 自动写 FarmEvent 集成测试 ====================


def test_complete_task_writes_farm_event(
    event_database: sessionmaker[Session],
) -> None:
    """完成任务后：FarmEvent 表新增 1 条 source=task_completion 的记录."""
    seeded = _seed_farm_with_field(event_database)
    task_id = _seed_pending_task(
        event_database,
        farm_id=seeded["farm_id"],
        field_id=seeded["field_id"],
        task_type="spraying",
    )

    completed = _drive_task_to_completed(
        user_id=seeded["owner_id"],
        task_id=task_id,
        note="已完成玉米田喷雾",
        attachment_urls=["https://example.com/spray.jpg"],
    )

    assert completed.status == "completed"

    with event_database() as session:
        events = (
            session.query(FarmEvent)
            .filter(FarmEvent.related_task_id == task_id)
            .all()
        )
        assert len(events) == 1
        event = events[0]
        assert event.event_type == "spraying"
        assert event.source == "task_completion"
        assert event.field_id == seeded["field_id"]
        assert event.operator == f"user:{seeded['owner_id']}"
        assert event.note == "已完成玉米田喷雾"
        inputs = event.inputs
        assert isinstance(inputs, list)
        assert len(inputs) == 2
        materials = {item.get("material") for item in inputs}
        assert materials == {"note", "attachment"}


@pytest.mark.parametrize(
    ("task_type", "expected_event_type"),
    [
        ("spraying", "spraying"),
        ("fertilizing", "fertilizing"),
        ("irrigating", "irrigating"),
        ("drainage", "irrigating"),
        ("scouting", "scouting"),
    ],
)
def test_complete_task_maps_event_type_for_various_task_types(
    event_database: sessionmaker[Session],
    task_type: str,
    expected_event_type: str,
) -> None:
    """不同 task_type 完成时写入正确的 event_type."""
    seeded = _seed_farm_with_field(event_database)
    task_id = _seed_pending_task(
        event_database,
        farm_id=seeded["farm_id"],
        field_id=seeded["field_id"],
        task_type=task_type,
        task_id=f"task-{task_type}",
    )

    _drive_task_to_completed(user_id=seeded["owner_id"], task_id=task_id)

    with event_database() as session:
        event = (
            session.query(FarmEvent)
            .filter(FarmEvent.related_task_id == task_id)
            .one()
        )
        assert event.event_type == expected_event_type
        assert event.source == "task_completion"


def test_complete_task_without_field_id_does_not_write_event(
    event_database: sessionmaker[Session],
) -> None:
    """任务 field_id 为 None 时，_maybe_record_completion_event 不写事件."""
    seeded = _seed_farm_with_field(event_database)
    task_id = _seed_pending_task(
        event_database,
        farm_id=seeded["farm_id"],
        field_id=None,
        task_type="spraying",
        task_id="task-no-field",
    )

    _drive_task_to_completed(user_id=seeded["owner_id"], task_id=task_id)

    with event_database() as session:
        events = (
            session.query(FarmEvent)
            .filter(FarmEvent.related_task_id == task_id)
            .all()
        )
        assert events == []


def test_maybe_record_completion_event_is_idempotent(
    event_database: sessionmaker[Session],
) -> None:
    """防御性检查：同一任务同一 event_type 重复调用 → 不重复写入."""
    seeded = _seed_farm_with_field(event_database)
    task_id = _seed_pending_task(
        event_database,
        farm_id=seeded["farm_id"],
        field_id=seeded["field_id"],
        task_type="spraying",
    )

    _drive_task_to_completed(user_id=seeded["owner_id"], task_id=task_id)

    with event_database() as session:
        task = (
            session.query(FarmTask).filter(FarmTask.task_id == task_id).one()
        )
        execution = TaskExecution.model_validate(task.execution)
        first_event_count = (
            session.query(FarmEvent)
            .filter(FarmEvent.related_task_id == task_id)
            .count()
        )
        assert first_event_count == 1

        farm_task_service._maybe_record_completion_event(
            session,
            task=task,
            actor_user_id=seeded["owner_id"],
            note="重复触发",
            execution=execution,
        )
        session.commit()

        second_event_count = (
            session.query(FarmEvent)
            .filter(FarmEvent.related_task_id == task_id)
            .count()
        )
        assert second_event_count == 1


def test_complete_task_sets_event_season_id_from_field_pointer(
    event_database: sessionmaker[Session],
) -> None:
    """任务的 field 关联了 current_season_id 时，事件 season_id 应跟随."""
    seeded = _seed_farm_with_field(event_database)
    with event_database() as session:
        season = CropSeason(
            field_id=seeded["field_id"],
            crop_name="水稻",
            season_code="2026-S1",
            start_date=date(2026, 5, 28),
            current_stage="分蘖期",
            area_mu=10.0,
            status="growing",
        )
        session.add(season)
        session.flush()
        field = session.query(Field).filter(Field.id == seeded["field_id"]).one()
        field.current_season_id = season.id
        session.commit()
        season_id = season.id

    task_id = _seed_pending_task(
        event_database,
        farm_id=seeded["farm_id"],
        field_id=seeded["field_id"],
        task_type="spraying",
        task_id="task-with-season",
    )

    _drive_task_to_completed(user_id=seeded["owner_id"], task_id=task_id)

    with event_database() as session:
        event = (
            session.query(FarmEvent)
            .filter(FarmEvent.related_task_id == task_id)
            .one()
        )
        assert event.season_id == season_id


def test_complete_task_event_inputs_include_note_and_attachments(
    event_database: sessionmaker[Session],
) -> None:
    """事件 inputs 包含 note 和 attachment_urls 推导的投入品清单."""
    seeded = _seed_farm_with_field(event_database)
    task_id = _seed_pending_task(
        event_database,
        farm_id=seeded["farm_id"],
        field_id=seeded["field_id"],
        task_type="spraying",
    )

    _drive_task_to_completed(
        user_id=seeded["owner_id"],
        task_id=task_id,
        note="使用甲维盐 10ml/亩",
        attachment_urls=[
            "https://example.com/photo1.jpg",
            "https://example.com/photo2.jpg",
        ],
    )

    with event_database() as session:
        event = (
            session.query(FarmEvent)
            .filter(FarmEvent.related_task_id == task_id)
            .one()
        )
        inputs = event.inputs
        assert len(inputs) == 3
        attachment_items = [item for item in inputs if item.get("material") == "attachment"]
        assert len(attachment_items) == 2
        note_items = [item for item in inputs if item.get("material") == "note"]
        assert len(note_items) == 1
        assert note_items[0]["detail"] == "使用甲维盐 10ml/亩"


def test_complete_task_does_not_write_event_when_already_completed(
    event_database: sessionmaker[Session],
) -> None:
    """completed 是终态，再次 complete 会抛 409，不会重复写事件."""
    seeded = _seed_farm_with_field(event_database)
    task_id = _seed_pending_task(
        event_database,
        farm_id=seeded["farm_id"],
        field_id=seeded["field_id"],
        task_type="spraying",
    )

    _drive_task_to_completed(user_id=seeded["owner_id"], task_id=task_id)

    with pytest.raises(AppException) as exc_info:
        farm_task_service.complete(
            user_id=seeded["owner_id"],
            task_id=task_id,
            note="重复完成",
        )
    assert exc_info.value.code == "INVALID_TASK_TRANSITION"

    with event_database() as session:
        event_count = (
            session.query(FarmEvent)
            .filter(FarmEvent.related_task_id == task_id)
            .count()
        )
        assert event_count == 1
