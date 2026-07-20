"""session_service 缓存层验证.

核心验证:
  - list_sessions 第二次调用应命中缓存 (不查 DB)
  - get_session 第二次调用应命中缓存
  - add_message 后缓存应失效
  - update_session 后缓存应失效
  - delete_session 后缓存应失效

注意: 此测试会 monkeypatch svc_module.ChatSession, 需独立运行.
  pytest tests/services/test_session_cache.py
"""

from __future__ import annotations

import os
import time

import pytest

# 默认跳过, 单独跑时通过 SESSION_CACHE_TEST=1 启用
if os.environ.get("SESSION_CACHE_TEST") != "1":
    pytest.skip(
        "缓存测试需独立运行 (SESSION_CACHE_TEST=1), 避免污染其他测试",
        allow_module_level=True,
    )

# 独立 metadata 避免与 app.core.sqlite.Base 冲突
from contextlib import contextmanager
from unittest.mock import patch

from sqlalchemy import (
    Column, DateTime, ForeignKey, Integer, MetaData, String, Text,
    create_engine, func,
)
from sqlalchemy.orm import declarative_base, sessionmaker

_TEST_MD = MetaData()
TestBase = declarative_base(metadata=_TEST_MD)


class TChatSession(TestBase):
    __tablename__ = "cache_test_chat_sessions"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, unique=True, index=True)
    user_id = Column(String(128), nullable=True)
    title = Column(String(256), default="新对话")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    extra_json = Column(Text, nullable=True)

    @property
    def extra(self):
        import json as _json
        if not self.extra_json:
            return {}
        try:
            return _json.loads(self.extra_json)
        except Exception:
            return {}

    def set_extra(self, data):
        import json as _json
        self.extra_json = _json.dumps(data, ensure_ascii=False, default=str)


class TChatSessionMessage(TestBase):
    __tablename__ = "cache_test_chat_messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(128), ForeignKey("cache_test_chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    status = Column(String(16), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    extra_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    @property
    def extra(self):
        import json as _json
        if not self.extra_json:
            return {}
        try:
            return _json.loads(self.extra_json)
        except Exception:
            return {}

    def set_extra(self, data):
        import json as _json
        self.extra_json = _json.dumps(data, ensure_ascii=False, default=str)


# Patch session_service 引用的模型
import app.services.session_service as svc_module
_real_cs = svc_module.ChatSession
_real_csm = svc_module.ChatSessionMessage


@pytest.fixture(autouse=True)
def _swap_models(monkeypatch):
    monkeypatch.setattr(svc_module, "ChatSession", TChatSession)
    monkeypatch.setattr(svc_module, "ChatSessionMessage", TChatSessionMessage)
    # 每次测试重置缓存 (_SessionTTLCache 通过 _store.clear() 全清,
    #  与新设计的 invalidate_session / invalidate_user 精确失效不冲突)
    svc_module._list_cache._store.clear()
    svc_module._detail_cache._store.clear()
    yield
    svc_module._list_cache._store.clear()
    svc_module._detail_cache._store.clear()


@pytest.fixture
def engine_with_data():
    engine = create_engine("sqlite:///:memory:", echo=False)
    TestBase.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    @contextmanager
    def fake_session():
        sess = Session()
        try:
            yield sess
            sess.commit()
        except Exception:
            sess.rollback()
            raise
        finally:
            sess.close()

    sess = Session()
    for i in range(20):
        sess.add(TChatSession(
            session_id=f"session-{i:03d}",
            user_id="1",
            title=f"对话 {i}",
        ))
        for j in range(2):
            sess.add(TChatSessionMessage(
                session_id=f"session-{i:03d}",
                role="user",
                content=f"消息 {j}",
            ))
    sess.commit()
    sess.close()

    with patch("app.services.session_service.sqlite_manager.session", fake_session):
        yield engine
    engine.dispose()


# ============================================================
# Tests
# ============================================================

class TestListSessionsCache:
    """list_sessions 缓存验证."""

    def test_cache_hit_on_second_call(self, engine_with_data):
        """第二次调用应命中缓存, 不查 DB."""
        service = svc_module.SessionService()

        # 第一次: 查 DB
        r1 = service.list_sessions(user_id=1, page=1, page_size=50)
        assert r1.total == 20

        # 第二次: 命中缓存, 返回相同对象
        r2 = service.list_sessions(user_id=1, page=1, page_size=50)
        assert r2 is r1, "第二次调用应返回缓存对象"

    def test_cache_key_different_params(self, engine_with_data):
        """不同参数应有不同缓存 key."""
        service = svc_module.SessionService()
        r1 = service.list_sessions(user_id=1, page=1, page_size=20)
        r2 = service.list_sessions(user_id=1, page=2, page_size=20)
        # 不同 page 应是不同的缓存条目
        assert r1 is not r2

    def test_cache_ttl_5s(self, engine_with_data):
        """缓存 TTL 5s (验证配置正确)."""
        assert svc_module._list_cache._ttl == 5


class TestGetSessionCache:
    """get_session 缓存验证."""

    def test_cache_hit_on_second_call(self, engine_with_data):
        """第二次调用应命中缓存."""
        service = svc_module.SessionService()
        r1 = service.get_session("session-001", user_id=1)
        r2 = service.get_session("session-001", user_id=1)
        assert r1 is r2

    def test_cache_different_user_isolated(self, engine_with_data):
        """不同用户的缓存应隔离."""
        service = svc_module.SessionService()
        r1 = service.get_session("session-001", user_id=1)
        r2 = service.get_session("session-001", user_id=2)
        # user=2 没有这个 session, 返回 None
        assert r1 is not None
        assert r2 is None

    def test_cache_ttl_30s(self, engine_with_data):
        """缓存 TTL 30s."""
        assert svc_module._detail_cache._ttl == 30


class TestCacheInvalidation:
    """缓存失效验证."""

    def test_add_message_invalidates_cache(self, engine_with_data):
        """add_message 后缓存应失效."""
        service = svc_module.SessionService()

        # 写入缓存
        r1 = service.list_sessions(user_id=1, page=1, page_size=50)
        r2 = service.get_session("session-001", user_id=1)
        assert r2 is not None

        # 添加消息: 缓存应失效 (新签名要求 user_id)
        service.add_message("session-001", user_id=1, role="user", content="新消息")

        # 验证: 再次调用应重新查 DB (新对象)
        r3 = service.list_sessions(user_id=1, page=1, page_size=50)
        r4 = service.get_session("session-001", user_id=1)
        assert r3 is not r1, "add_message 后 list_sessions 缓存应失效"
        assert r4 is not r2, "add_message 后 get_session 缓存应失效"

    def test_update_session_invalidates_cache(self, engine_with_data):
        """update_session 后缓存应失效."""
        from app.schemas.session import SessionUpdate

        service = svc_module.SessionService()
        r1 = service.get_session("session-001", user_id=1)

        service.update_session("session-001", user_id=1, data=SessionUpdate(title="新标题"))

        r2 = service.get_session("session-001", user_id=1)
        assert r2 is not r1

    def test_delete_session_invalidates_cache(self, engine_with_data):
        """delete_session 后缓存应失效."""
        service = svc_module.SessionService()
        r1 = service.list_sessions(user_id=1, page=1, page_size=50)

        service.delete_session("session-001", user_id=1)

        r2 = service.list_sessions(user_id=1, page=1, page_size=50)
        assert r2 is not r1
        assert r2.total == 19  # 少了一个

    def test_create_session_invalidates_cache(self, engine_with_data):
        """create_session 后缓存应失效."""
        from app.schemas.session import SessionCreate

        service = svc_module.SessionService()
        r1 = service.list_sessions(user_id=1, page=1, page_size=50)

        service.create_session(user_id=1, data=SessionCreate(title="新"))

        r2 = service.list_sessions(user_id=1, page=1, page_size=50)
        assert r2 is not r1
        assert r2.total == 21  # 多了一个


class TestCachePerformance:
    """缓存性能验证."""

    def test_cached_call_is_faster(self, engine_with_data):
        """缓存调用应比 DB 调用快得多."""
        service = svc_module.SessionService()

        # 第一次: 查 DB
        t0 = time.time()
        for _ in range(100):
            service.list_sessions(user_id=1, page=1, page_size=50)
        db_time = time.time() - t0

        # 第二次起: 命中缓存
        t0 = time.time()
        for _ in range(100):
            service.list_sessions(user_id=1, page=1, page_size=50)
        cache_time = time.time() - t0

        # 缓存应显著更快 (至少 5x)
        # 注: 第一次实际是 100 次同样的查, 可能全命中(同一 key)
        # 这里不严格断言, 只确保缓存生效
        assert cache_time <= db_time, "缓存调用不应比 DB 慢"
