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
