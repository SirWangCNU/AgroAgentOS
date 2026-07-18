from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Iterator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.sqlite import AgentRun, Base, sqlite_manager
from app.exceptions import ForbiddenError
from app.models.farm import Farm
from app.models.user import User
from app.services import farm_run_query_service


@pytest.fixture
def run_query_database(monkeypatch: pytest.MonkeyPatch) -> sessionmaker[Session]:
    engine = create_engine(
        "sqlite:///:memory:",
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


@pytest.mark.asyncio
async def test_latest_inspection_run_is_owned_ordered_and_type_filtered(
    run_query_database: sessionmaker[Session],
) -> None:
    with run_query_database() as session:
        owner = User(username="run-owner", email="run-owner@example.com", hashed_password="hash")
        other = User(username="run-other", email="run-other@example.com", hashed_password="hash")
        session.add_all([owner, other])
        session.flush()
        farm = Farm(user_id=owner.id, name="自有农场")
        foreign_farm = Farm(user_id=other.id, name="其他农场")
        session.add_all([farm, foreign_farm])
        session.flush()
        start = datetime(2026, 7, 18, 8, 0, 0)
        session.add_all([
            AgentRun(run_id="older", user_id=owner.id, farm_id=farm.id, run_type="inspection", status="failed", created_at=start),
            AgentRun(run_id="latest", user_id=owner.id, farm_id=farm.id, run_type="inspection", status="completed", created_at=start + timedelta(hours=1)),
            AgentRun(run_id="verification", user_id=owner.id, farm_id=farm.id, run_type="task_verification", status="completed", created_at=start + timedelta(hours=2)),
            AgentRun(run_id="foreign", user_id=other.id, farm_id=foreign_farm.id, run_type="inspection", status="completed", created_at=start + timedelta(hours=3)),
        ])
        session.commit()
        owner_id, farm_id, foreign_farm_id = owner.id, farm.id, foreign_farm.id

    latest = await farm_run_query_service.get_latest_inspection_run(user_id=owner_id, farm_id=farm_id)
    assert latest is not None
    assert latest.run_id == "latest"
    assert latest.status == "completed"

    with pytest.raises(ForbiddenError):
        await farm_run_query_service.get_latest_inspection_run(user_id=owner_id, farm_id=foreign_farm_id)


@pytest.mark.asyncio
async def test_latest_inspection_run_returns_none_when_user_has_no_runs(
    run_query_database: sessionmaker[Session],
) -> None:
    with run_query_database() as session:
        user = User(username="empty-run", email="empty-run@example.com", hashed_password="hash")
        session.add(user)
        session.commit()
        user_id = user.id

    assert await farm_run_query_service.get_latest_inspection_run(user_id=user_id) is None
