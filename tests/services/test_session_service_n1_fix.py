"""SessionService N+1 查询修复验证.

核心验证: list_sessions 应只触发少量 SQL 查询 (用 GROUP BY 一次性统计消息数).
修复前: 1 (sessions) + N (count) 次 = 51 次 (50 个 session 时)
修复后: 2-3 次 (count + data fetch)

注意: 此测试需独立运行 (会修改 app.services.session_service.ChatSession 引用).
  pytest tests/services/test_session_service_n1_fix.py
全套测试中默认跳过, 避免污染其他测试的 Base.metadata.
"""

from __future__ import annotations

import os

import pytest

# 标记: 默认跳过, 单独跑时通过 SESSION_N1_TEST=1 启用
if os.environ.get("SESSION_N1_TEST") != "1":
    pytest.skip(
        "N+1 测试需独立运行 (SESSION_N1_TEST=1), 避免污染其他测试",
        allow_module_level=True,
    )

from contextlib import contextmanager

import pytest
from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, MetaData, String, Text,
    create_engine, event, func,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# 关键: 独立 MetaData, 不与 app.core.sqlite.Base 共享, 彻底避免全局表冲突.
_TEST_MD = MetaData()
TestBase = declarative_base(metadata=_TEST_MD)


class TChatSession(TestBase):
    __tablename__ = "n1_test_chat_sessions"  # 独立表名避免 metadata 冲突
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, unique=True, index=True)
    user_id = Column(String(128), nullable=True)
    title = Column(String(256), default="新对话")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    extra_json = Column(Text, nullable=True)


class TChatSessionMessage(TestBase):
    __tablename__ = "n1_test_chat_session_messages"  # 独立表名
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(128), ForeignKey("n1_test_chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    created_at = Column(DateTime, default=func.now())


# 关键: 不在 import 时全局替换, 避免污染其他测试.
# SessionService 内部引用 svc_module.ChatSession, 通过 autouse fixture 临时替换.
from app.services.session_service import SessionService  # noqa: E402
from app.models.session import ChatSession as RealChatSession  # noqa: E402
from app.models.session import ChatSessionMessage as RealChatSessionMessage  # noqa: E402

import app.services.session_service as _svc_module  # noqa: E402


@pytest.fixture(autouse=True)
def _swap_models(monkeypatch):
    """每个测试期间替换模型, 测试结束后自动恢复 (monkeypatch 自动还原)."""
    monkeypatch.setattr(_svc_module, "ChatSession", TChatSession)
    monkeypatch.setattr(_svc_module, "ChatSessionMessage", TChatSessionMessage)
    yield


class QueryCounter:
    def __init__(self) -> None:
        self.count = 0
        self.queries: list[str] = []

    def reset(self) -> None:
        self.count = 0
        self.queries = []


@pytest.fixture
def counter():
    return QueryCounter()


@pytest.fixture
def engine_with_data(counter):
    """内存 SQLite, 注入 50 个 session, 每个 3 条消息."""
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    sess = Session()
    for i in range(50):
        sess.add(TChatSession(
            session_id=f"session-{i:03d}",
            user_id="1",
            title=f"对话 {i}",
        ))
        for j in range(3):
            sess.add(TChatSessionMessage(
                session_id=f"session-{i:03d}",
                role="user" if j % 2 == 0 else "assistant",
                content=f"消息 {j}",
            ))
    sess.commit()
    sess.close()

    @event.listens_for(engine, "before_cursor_execute")
    def _record(conn, cursor, statement, parameters, context, executemany):
        counter.count += 1
        counter.queries.append(statement)

    yield engine
    engine.dispose()


@pytest.fixture
def patched_sqlite_manager(engine_with_data, monkeypatch):
    """用测试 engine 替换 sqlite_manager."""
    Session = sessionmaker(bind=engine_with_data)
    SessionFactory = lambda: Session()  # noqa: E731

    @contextmanager
    def fake_session():
        sess = SessionFactory()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    monkeypatch.setattr("app.services.session_service.sqlite_manager.session", fake_session)
    return engine_with_data


# ============================================================
# Tests
# ============================================================

class TestListSessionsN1Fix:
    """list_sessions N+1 修复验证."""

    def test_query_count_for_50_sessions(self, patched_sqlite_manager, counter):
        """50 个 session 时, list_sessions 应只触发少量 SQL (非 51 次 N+1)."""
        counter.reset()
        service = SessionService()
        result = service.list_sessions(user_id=1, page=1, page_size=50)

        assert result.total == 50
        assert len(result.sessions) == 50
        # 修复后: 1 (count total) + 1 (data fetch) = 2 次
        # 阈值设为 5 容忍 SQLAlchemy 内部
        assert counter.count < 5, (
            f"list_sessions 触发了 {counter.count} 次 SQL, 应 <5 (N+1 修复失败)"
        )

    def test_message_count_correct(self, patched_sqlite_manager):
        """消息数应正确 (每个 session 3 条)."""
        service = SessionService()
        result = service.list_sessions(user_id=1, page=1, page_size=50)
        for s in result.sessions:
            assert s.message_count == 3, f"{s.id}: {s.message_count}"

    def test_pagination_works(self, patched_sqlite_manager):
        """分页正确."""
        service = SessionService()
        p1 = service.list_sessions(user_id=1, page=1, page_size=20)
        p2 = service.list_sessions(user_id=1, page=2, page_size=20)
        p3 = service.list_sessions(user_id=1, page=3, page_size=20)
        assert p1.total == 50
        assert len(p1.sessions) == 20
        assert len(p2.sessions) == 20
        assert len(p3.sessions) == 10
        all_ids = {s.id for s in p1.sessions + p2.sessions + p3.sessions}
        assert len(all_ids) == 50

    def test_other_user_returns_empty(self, patched_sqlite_manager):
        """其他用户应返回空."""
        service = SessionService()
        result = service.list_sessions(user_id=999, page=1, page_size=50)
        assert result.total == 0
        assert result.sessions == []

    def test_session_with_no_messages(self, patched_sqlite_manager, engine_with_data):
        """无消息的 session message_count=0."""
        with engine_with_data.connect() as conn:
            conn.execute(TChatSession.__table__.insert().values(
                session_id="empty", user_id="1", title="空",
            ))
            conn.commit()
        service = SessionService()
        result = service.list_sessions(user_id=1, page=1, page_size=100)
        empty = next((s for s in result.sessions if s.id == "empty"), None)
        assert empty is not None
        assert empty.message_count == 0
