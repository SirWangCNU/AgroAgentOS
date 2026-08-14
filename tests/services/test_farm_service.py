from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.sqlite import Base
from app.models.farm import Farm, Field
from app.models.user import User
from app.schemas.farm import (
    FarmCreateRequest,
    FarmInfo,
    FarmUpdateRequest,
    FieldCreateRequest,
    FieldInfo,
    FieldUpdateRequest,
)
from app.services import farm_service


FIELD_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [
            [116.3000, 40.0000],
            [116.3010, 40.0000],
            [116.3010, 40.0010],
            [116.3000, 40.0010],
            [116.3000, 40.0000],
        ]
    ],
}


ADJACENT_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [
            [116.3010, 40.0000],
            [116.3020, 40.0000],
            [116.3020, 40.0010],
            [116.3010, 40.0010],
            [116.3010, 40.0000],
        ]
    ],
}


OVERLAPPING_BOUNDARY = {
    "type": "Polygon",
    "coordinates": [
        [
            [116.3005, 40.0000],
            [116.3015, 40.0000],
            [116.3015, 40.0010],
            [116.3005, 40.0010],
            [116.3005, 40.0000],
        ]
    ],
}


@pytest.fixture()
def patched_farm_db(monkeypatch):
    farm_implicit_returning = Farm.__table__.implicit_returning
    field_implicit_returning = Field.__table__.implicit_returning
    Farm.__table__.implicit_returning = False
    Field.__table__.implicit_returning = False

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def fake_session():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    class FakeManager:
        session = staticmethod(fake_session)

    monkeypatch.setattr(farm_service, "sqlite_manager", FakeManager())

    with fake_session() as sess:
        sess.add(
            User(
                id=1,
                username="farmer",
                email="farmer@example.com",
                hashed_password="hash",
            )
        )

    try:
        yield engine
    finally:
        Farm.__table__.implicit_returning = farm_implicit_returning
        Field.__table__.implicit_returning = field_implicit_returning


def test_create_farm_returns_model_ready_detached_instance(patched_farm_db):
    farm = farm_service.create_farm(
        1,
        FarmCreateRequest(name="test farm", location="Beijing", area_mu=12.5),
    )

    info = FarmInfo.model_validate(farm)

    assert info.name == "test farm"
    assert info.created_at is not None
    assert info.updated_at is not None


def test_update_farm_returns_model_ready_detached_instance(patched_farm_db):
    farm = farm_service.create_farm(
        1,
        FarmCreateRequest(name="old farm", location="Beijing", area_mu=12.5),
    )

    updated = farm_service.update_farm(
        farm.id,
        1,
        FarmUpdateRequest(name="new farm", area_mu=20.0),
    )
    info = FarmInfo.model_validate(updated)

    assert info.name == "new farm"
    assert info.area_mu == 20.0
    assert info.updated_at is not None


def test_create_and_update_field_return_model_ready_detached_instances(patched_farm_db):
    farm = farm_service.create_farm(
        1,
        FarmCreateRequest(name="test farm", location="Beijing", area_mu=12.5),
    )
    field = farm_service.create_field(
        farm.id,
        1,
        FieldCreateRequest(name="field one", area_mu=3.0),
    )

    created_info = FieldInfo.model_validate(field)
    updated = farm_service.update_field(
        field.id,
        1,
        FieldUpdateRequest(name="field two", area_mu=4.0),
    )
    updated_info = FieldInfo.model_validate(updated)

    assert created_info.created_at is not None
    assert updated_info.name == "field two"
    assert updated_info.updated_at is not None


def test_create_field_with_boundary_overrides_area_and_updates_farm_total(patched_farm_db):
    """Accepting client-provided area for a drawn field would let the map and farm total drift apart."""
    farm = farm_service.create_farm(
        1,
        FarmCreateRequest(name="boundary farm", location="Beijing", area_mu=99.0),
    )

    field = farm_service.create_field(
        farm.id,
        1,
        FieldCreateRequest(name="field one", area_mu=1.0, boundary=FIELD_BOUNDARY),
    )
    field_info = FieldInfo.model_validate(field)
    updated_farm = farm_service.get_farm(farm.id, 1)

    assert field_info.boundary == FIELD_BOUNDARY
    assert field_info.area_mu == pytest.approx(14.22, rel=0.05)
    assert field_info.latitude is not None
    assert field_info.longitude is not None
    assert updated_farm.area_mu == pytest.approx(field_info.area_mu)


def test_same_farm_overlap_is_rejected_but_shared_edge_is_allowed(patched_farm_db):
    """Blocking shared edges or allowing real overlap would both break common field digitizing workflows."""
    farm = farm_service.create_farm(1, FarmCreateRequest(name="overlap farm"))
    farm_service.create_field(
        farm.id,
        1,
        FieldCreateRequest(name="left", boundary=FIELD_BOUNDARY),
    )

    adjacent = farm_service.create_field(
        farm.id,
        1,
        FieldCreateRequest(name="right", boundary=ADJACENT_BOUNDARY),
    )

    assert adjacent.area_mu > 0
    with pytest.raises(Exception) as exc:
        farm_service.create_field(
            farm.id,
            1,
            FieldCreateRequest(name="overlapping", boundary=OVERLAPPING_BOUNDARY),
        )
    assert getattr(exc.value, "status_code", None) == 409


def test_update_boundary_recalculates_field_and_delete_recalculates_farm_total(patched_farm_db):
    """Editing and deleting drawn fields must keep the authoritative farm total in sync."""
    farm = farm_service.create_farm(1, FarmCreateRequest(name="sync farm"))
    drawn = farm_service.create_field(
        farm.id,
        1,
        FieldCreateRequest(name="drawn", boundary=FIELD_BOUNDARY),
    )
    legacy = farm_service.create_field(
        farm.id,
        1,
        FieldCreateRequest(name="legacy", area_mu=3.0),
    )

    updated = farm_service.update_field(
        drawn.id,
        1,
        FieldUpdateRequest(boundary=ADJACENT_BOUNDARY, area_mu=200.0),
    )
    after_update = farm_service.get_farm(farm.id, 1)
    farm_service.delete_field(legacy.id, 1)
    after_delete = farm_service.get_farm(farm.id, 1)

    assert updated.area_mu != 200.0
    assert after_update.area_mu == pytest.approx(updated.area_mu + 3.0)
    assert after_delete.area_mu == pytest.approx(updated.area_mu)
