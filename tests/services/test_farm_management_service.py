"""Farm management MVP service tests."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, datetime, timezone
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.sqlite import Base, sqlite_manager
from app.exceptions import AppException
from app.models.farm import Farm, Field
from app.models.user import User
from app.schemas.farm import (
    CropSeasonCreateRequest,
    FarmEventCreateRequest,
    FieldCreateRequest,
)
from app.services import farm_service


@pytest.fixture
def farm_database(monkeypatch: pytest.MonkeyPatch) -> Iterator[sessionmaker[Session]]:
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


def _seed_owner(session_factory: sessionmaker[Session]) -> dict[str, int]:
    with session_factory() as session:
        owner = User(username="farm-owner", email="owner@example.com", hashed_password="hash")
        other = User(username="farm-other", email="other@example.com", hashed_password="hash")
        session.add_all([owner, other])
        session.flush()
        farm = Farm(user_id=owner.id, name="Owned farm")
        session.add(farm)
        session.flush()
        result = {"owner_id": owner.id, "other_id": other.id, "farm_id": farm.id}
        session.commit()
        return result


def test_create_field_persists_boundary_json(
    farm_database: sessionmaker[Session],
) -> None:
    seeded = _seed_owner(farm_database)
    boundary = '{"type":"Polygon","coordinates":[[[116.1,40.1],[116.2,40.1],[116.2,40.2],[116.1,40.1]]]}'

    field = farm_service.create_field(
        int(seeded["farm_id"]),
        int(seeded["owner_id"]),
        FieldCreateRequest(
            name="A1",
            area_mu=12.5,
            current_crop="玉米",
            growth_stage="拔节期",
            boundary_json=boundary,
        ),
    )

    assert field.boundary_json == boundary
    with farm_database() as session:
        persisted = session.query(Field).filter(Field.id == field.id).one()
        assert persisted.boundary_json == boundary


def test_create_crop_season_updates_field_current_state(
    farm_database: sessionmaker[Session],
) -> None:
    seeded = _seed_owner(farm_database)
    field = farm_service.create_field(
        int(seeded["farm_id"]),
        int(seeded["owner_id"]),
        FieldCreateRequest(name="A1", area_mu=10),
    )

    season = farm_service.create_crop_season(
        field_id=field.id,
        user_id=int(seeded["owner_id"]),
        data=CropSeasonCreateRequest(
            crop_name="春玉米",
            variety="京科968",
            season_code="2026-S1",
            start_date=date(2026, 4, 25),
            expected_harvest=date(2026, 9, 20),
            current_stage="拔节期",
            area_mu=42.6,
            target_yield="650 kg/亩",
            status="growing",
        ),
    )

    with farm_database() as session:
        persisted = session.query(Field).filter(Field.id == field.id).one()
        assert persisted.current_season_id == season.id
        assert persisted.current_crop == "春玉米"
        assert persisted.growth_stage == "拔节期"
        assert persisted.status == "planting"


def test_create_farm_event_uses_current_season_and_structured_payload(
    farm_database: sessionmaker[Session],
) -> None:
    seeded = _seed_owner(farm_database)
    field = farm_service.create_field(
        int(seeded["farm_id"]),
        int(seeded["owner_id"]),
        FieldCreateRequest(name="A1", area_mu=10),
    )
    season = farm_service.create_crop_season(
        field_id=field.id,
        user_id=int(seeded["owner_id"]),
        data=CropSeasonCreateRequest(
            crop_name="春玉米",
            season_code="2026-S1",
            start_date=date(2026, 4, 25),
            status="growing",
        ),
    )

    event = farm_service.create_farm_event(
        field_id=field.id,
        user_id=int(seeded["owner_id"]),
        data=FarmEventCreateRequest(
            event_type="scouting",
            event_time=datetime(2026, 7, 20, 8, 0, tzinfo=timezone.utc),
            operator="demo:巡田员",
            inputs=[{"material": "note", "detail": "低洼积水风险"}],
            geo_payload={"type": "Point", "coordinates": [116.433, 40.155]},
            note="巡田发现局部低洼积水风险。",
        ),
    )

    assert event.season_id == season.id
    assert event.source == "human_entry"
    assert event.inputs == [{"material": "note", "detail": "低洼积水风险"}]
    assert event.geo_payload["type"] == "Point"


def test_create_farm_event_rejects_cross_user_field(
    farm_database: sessionmaker[Session],
) -> None:
    seeded = _seed_owner(farm_database)
    field = farm_service.create_field(
        int(seeded["farm_id"]),
        int(seeded["owner_id"]),
        FieldCreateRequest(name="A1", area_mu=10),
    )

    with pytest.raises(AppException) as exc_info:
        farm_service.create_farm_event(
            field_id=field.id,
            user_id=int(seeded["other_id"]),
            data=FarmEventCreateRequest(event_type="scouting"),
        )
    assert exc_info.value.status_code == 403
