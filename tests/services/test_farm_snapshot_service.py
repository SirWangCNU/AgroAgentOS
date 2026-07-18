"""农场快照聚合服务测试。"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.sqlite import Base, sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm, Field
from app.models.farm_agent import FarmTask
from app.models.trajectory import TrajectoryFile
from app.models.user import User
from app.services import farm_snapshot_service


@pytest.fixture
def snapshot_database(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    """让服务使用真实的内存 SQLite 会话。"""

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


def _seed_snapshot_data(session_factory: sessionmaker[Session]) -> dict[str, int | str]:
    with session_factory() as session:
        owner = User(
            username="snapshot-owner",
            email="snapshot-owner@example.com",
            hashed_password="hash",
        )
        other_user = User(
            username="snapshot-other",
            email="snapshot-other@example.com",
            hashed_password="hash",
        )
        session.add_all([owner, other_user])
        session.flush()

        owned_farm = Farm(
            user_id=owner.id,
            name="不可泄露的农场名称",
            location="山东寿光",
            area_mu=20.0,
        )
        other_farm = Farm(
            user_id=other_user.id,
            name="其他用户农场",
            location="河南",
            area_mu=30.0,
        )
        session.add_all([owned_farm, other_farm])
        session.flush()

        owned_field = Field(
            farm_id=owned_farm.id,
            name="A1 地块",
            area_mu=20.0,
            current_crop="小麦",
            growth_stage="拔节期",
            boundary_json='{"type":"Polygon","coordinates":[]}',
        )
        other_field = Field(
            farm_id=other_farm.id,
            name="B1 地块",
            area_mu=30.0,
            current_crop="玉米",
        )
        session.add_all([owned_field, other_field])
        session.flush()

        now = datetime(2026, 7, 18, 8, 0, 0)
        owned_trajectories = [
            TrajectoryFile(
                field_id=owned_field.id,
                filename=f"owned-{index}.xlsx",
                work_area_mu=18.0,
                depth_std=2.0,
                created_at=now - timedelta(hours=index),
            )
            for index in range(4)
        ]
        other_trajectory = TrajectoryFile(
            field_id=other_field.id,
            filename="other-user.xlsx",
            work_area_mu=25.0,
            created_at=now + timedelta(hours=1),
        )
        session.add_all([*owned_trajectories, other_trajectory])

        session.add_all(
            [
                FarmTask(
                    task_id="snapshot-pending",
                    farm_id=owned_farm.id,
                    field_id=owned_field.id,
                    title="检查排水沟",
                    task_type="drainage",
                    instructions="清理堵塞点",
                    status="pending",
                ),
                FarmTask(
                    task_id="snapshot-completed",
                    farm_id=owned_farm.id,
                    field_id=owned_field.id,
                    title="已完成任务",
                    task_type="drainage",
                    instructions="无需处理",
                    status="completed",
                ),
                FarmTask(
                    task_id="snapshot-other-user",
                    farm_id=other_farm.id,
                    field_id=other_field.id,
                    title="其他用户任务",
                    task_type="inspection",
                    instructions="不得聚合",
                    status="pending",
                ),
            ]
        )
        session.commit()

        return {
            "owner_id": owner.id,
            "other_user_id": other_user.id,
            "owned_farm_id": owned_farm.id,
            "owned_farm_name": owned_farm.name,
            "owned_field_id": owned_field.id,
        }


def test_get_snapshot_returns_only_owned_detached_business_data(
    snapshot_database: sessionmaker[Session],
) -> None:
    seeded = _seed_snapshot_data(snapshot_database)

    snapshot = farm_snapshot_service.get_snapshot(
        farm_id=int(seeded["owned_farm_id"]),
        user_id=int(seeded["owner_id"]),
    )

    assert snapshot.farm.id == seeded["owned_farm_id"]
    assert {field.id for field in snapshot.fields} == {seeded["owned_field_id"]}
    assert snapshot.fields[0].current_crop == "小麦"
    assert snapshot.fields[0].growth_stage == "拔节期"
    assert snapshot.fields[0].boundary_json.startswith('{"type":"Polygon"')
    assert len(snapshot.recent_trajectory_files) == 3
    assert snapshot.recent_trajectory_files[0].field_id == seeded["owned_field_id"]
    assert [item.filename for item in snapshot.recent_trajectory_files] == [
        "owned-0.xlsx",
        "owned-1.xlsx",
        "owned-2.xlsx",
    ]
    assert snapshot.pending_task_count == 1
    assert snapshot.captured_at is not None
    assert snapshot.data_gaps == []
    assert snapshot.model_dump()["farm"]["name"] == seeded["owned_farm_name"]


def test_get_snapshot_rejects_cross_user_access_without_leaking_farm_name(
    snapshot_database: sessionmaker[Session],
) -> None:
    seeded = _seed_snapshot_data(snapshot_database)

    with pytest.raises(AppException) as exc_info:
        farm_snapshot_service.get_snapshot(
            farm_id=int(seeded["owned_farm_id"]),
            user_id=int(seeded["other_user_id"]),
        )

    assert exc_info.value.status_code == 403
    assert str(seeded["owned_farm_name"]) not in exc_info.value.message
    assert str(seeded["owned_farm_name"]) not in str(exc_info.value.detail)


def test_get_snapshot_preserves_not_found_for_unknown_farm(
    snapshot_database: sessionmaker[Session],
) -> None:
    seeded = _seed_snapshot_data(snapshot_database)

    with pytest.raises(AppException) as exc_info:
        farm_snapshot_service.get_snapshot(
            farm_id=999_999,
            user_id=int(seeded["owner_id"]),
        )

    assert exc_info.value.status_code == 404
