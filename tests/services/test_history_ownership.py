"""农业问答历史必须按用户隔离。"""

import asyncio
from contextlib import contextmanager

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.sqlite import Base
from app.services import history_service


@pytest.fixture()
def history_database(monkeypatch):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, expire_on_commit=False)

    @contextmanager
    def session_scope():
        session = factory()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    monkeypatch.setattr(history_service.sqlite_manager, "session", session_scope)
    yield
    engine.dispose()


def test_history_records_are_private_to_their_owner(history_database):
    """移除 user_id 过滤会让另一位用户读取和删除私人问答。"""
    first_record = asyncio.run(
        history_service.add_record(
            user_id=101,
            question="我的水稻叶片发黄怎么办？",
            answer="先检查田间排水和氮肥施用情况。",
        )
    )
    second_record = asyncio.run(
        history_service.add_record(
            user_id=202,
            question="我的玉米何时追肥？",
            answer="结合苗期和土壤墒情安排追肥。",
        )
    )

    first_page = asyncio.run(history_service.list_records(user_id=101))
    assert [record["id"] for record in first_page["records"]] == [first_record]
    assert asyncio.run(history_service.get_record(second_record, user_id=101)) is None
    assert asyncio.run(history_service.delete_record(second_record, user_id=101)) is False

    removed = asyncio.run(history_service.clear_records(user_id=101))
    assert removed == 1
    assert asyncio.run(history_service.get_record(second_record, user_id=202))["id"] == second_record
