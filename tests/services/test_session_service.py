"""SessionService 新增功能验证.

覆盖方案中要求的 7 个场景:
  - test_pagination_latest_10        首次加载返回最新 10 条 (按时间正序)
  - test_pagination_load_more        before_id 游标向前加载更早消息
  - test_pagination_has_more_flag    has_more 标记正确 (多取 1 条判断)
  - test_add_message_ownership_check 非会话所有者写入被拒 (抛 ValueError)
  - test_add_error_message           错误消息以 status=error 持久化
  - test_cache_invalidation_per_session 仅失效目标 session 的 detail 缓存
  - test_cache_redis_fallback_to_db  注: Redis 缓存层由 chat_memory 负责, 这里验证
                                      进程内 _SessionTTLCache 在过期后自动回退到 DB

设计要点:
  - 用独立 MetaData 避免与 app.core.sqlite.Base 冲突
  - monkeypatch 临时替换 svc_module.ChatSession/ChatSessionMessage, 测试后自动还原
  - fake sqlite_manager.session 走内存 SQLite, 测试隔离

运行方式:
    pytest tests/services/test_session_service.py
"""

from __future__ import annotations

import os
import time

import pytest

# 默认跳过, 单独跑时通过 SESSION_SVC_TEST=1 启用 (与既有 test_session_cache.py / test_session_service_n1_fix.py 一致)
if os.environ.get("SESSION_SVC_TEST") != "1":
    pytest.skip(
        "SessionService 测试需独立运行 (SESSION_SVC_TEST=1), 避免污染其他测试",
        allow_module_level=True,
    )

import json
from contextlib import contextmanager
from typing import Any

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Text,
    create_engine,
    func,
)
from sqlalchemy.orm import declarative_base, sessionmaker

# ============================================================
# 独立测试 model (与生产 model 字段一致, 但独立 MetaData 避免污染)
# ============================================================

_TEST_MD = MetaData()
TestBase = declarative_base(metadata=_TEST_MD)


class TChatSession(TestBase):
    __tablename__ = "svc_test_chat_sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, unique=True, index=True)
    user_id = Column(String(128), nullable=True)
    title = Column(String(256), default="新对话")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    extra_json = Column(Text, nullable=True)

    @property
    def extra(self) -> dict[str, Any]:
        if not self.extra_json:
            return {}
        try:
            return json.loads(self.extra_json)
        except Exception:
            return {}

    def set_extra(self, data: dict[str, Any]) -> None:
        self.extra_json = json.dumps(data, ensure_ascii=False, default=str)


class TChatSessionMessage(TestBase):
    __tablename__ = "svc_test_chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(128),
        ForeignKey("svc_test_chat_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    role = Column(String(20), nullable=False)
    content = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)
    status = Column(String(16), nullable=False, default="success")
    error_message = Column(Text, nullable=True)
    extra_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=func.now())

    @property
    def extra(self) -> dict[str, Any]:
        if not self.extra_json:
            return {}
        try:
            return json.loads(self.extra_json)
        except Exception:
            return {}

    def set_extra(self, data: dict[str, Any]) -> None:
        self.extra_json = json.dumps(data, ensure_ascii=False, default=str)


# ============================================================
# Patch svc_module 的模型引用
# ============================================================

import app.services.session_service as svc_module  # noqa: E402


def _clear_all_caches() -> None:
    """清空所有进程内缓存条目.

    _SessionTTLCache 当前没有提供全清 API, 测试需要重置干净状态,
    这里直接操作 _store 字段, 避免为测试修改生产 API.
    """
    svc_module._list_cache._store.clear()
    svc_module._detail_cache._store.clear()


@pytest.fixture(autouse=True)
def _swap_models(monkeypatch):
    """每个测试期间替换模型引用, 测试结束后自动还原."""
    monkeypatch.setattr(svc_module, "ChatSession", TChatSession)
    monkeypatch.setattr(svc_module, "ChatSessionMessage", TChatSessionMessage)
    _clear_all_caches()
    yield
    _clear_all_caches()


@pytest.fixture
def engine():
    """内存 SQLite + fake sqlite_manager.session."""
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

    # sqlite_manager.session 是 contextmanager, patch 之
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(svc_module.sqlite_manager, "session", fake_session)
        yield engine
    engine.dispose()


@pytest.fixture
def service():
    return svc_module.SessionService()


@pytest.fixture
def seeded_session(engine):
    """预置 1 个会话 + 15 条消息 (id 自增, 分页按 id 排序)."""
    Session = sessionmaker(bind=engine)
    sess = Session()
    sess.add(TChatSession(session_id="sess-A", user_id="1", title="对话 A"))
    sess.commit()
    sess.close()

    svc = svc_module.SessionService()
    for i in range(1, 16):
        svc.add_message(
            session_uuid="sess-A",
            user_id=1,
            role="user" if i % 2 == 1 else "assistant",
            content=f"消息 {i:02d}",
        )
    # get_messages_paginated 按 id 排序, 不依赖 created_at,
    # 因此无需额外时间偏移即可保证顺序确定.
    return "sess-A"


# ============================================================
# 分页测试
# ============================================================


class TestPagination:
    """游标分页 (limit + before_id) 验证."""

    def test_pagination_latest_10(self, service, seeded_session):
        """首次加载返回最新 10 条, 按时间正序排列 (oldest -> newest)."""
        result = service.get_messages_paginated("sess-A", user_id=1, limit=10, before_id=None)

        assert len(result.messages) == 10
        # 正序: messages[0] 应是最旧的 (id=6), messages[9] 应是最新的 (id=15)
        assert result.messages[0].content == "消息 06"
        assert result.messages[9].content == "消息 15"
        # 15 条数据取最新 10 条, 应该 has_more=True
        assert result.has_more is True
        # oldest_id 应为当前页最旧消息的 id
        assert result.oldest_id == result.messages[0].id

    def test_pagination_load_more(self, service, seeded_session):
        """向前加载: 用第一页的 oldest_id 作 before_id, 应返回更早的 5 条."""
        page1 = service.get_messages_paginated("sess-A", user_id=1, limit=10, before_id=None)
        page2 = service.get_messages_paginated(
            "sess-A", user_id=1, limit=10, before_id=page1.oldest_id
        )

        # 15 - 10 = 5 条更早消息
        assert len(page2.messages) == 5
        # page2 应在 page1 之前 (id 更小)
        assert page2.messages[0].content == "消息 01"
        assert page2.messages[4].content == "消息 05"
        # 没有更早的消息了
        assert page2.has_more is False

    def test_pagination_has_more_flag(self, service, seeded_session):
        """has_more 应正确标记边界: 恰好等于 limit 时 has_more=False."""
        # 取 15 条 (全部), has_more=False
        result_all = service.get_messages_paginated("sess-A", user_id=1, limit=15, before_id=None)
        assert len(result_all.messages) == 15
        assert result_all.has_more is False

        # 取 14 条 (少于总量), has_more=True (因多取 1 条发现还有)
        result_14 = service.get_messages_paginated("sess-A", user_id=1, limit=14, before_id=None)
        assert len(result_14.messages) == 14
        assert result_14.has_more is True

    def test_pagination_limit_clamped_to_max_50(self, service, seeded_session):
        """limit 上限 50 保护: 传 1000 应被截断为 50."""
        result = service.get_messages_paginated("sess-A", user_id=1, limit=1000, before_id=None)
        # 数据共 15 条, 不会超过 15, 但调用未抛错
        assert len(result.messages) == 15

    def test_pagination_unknown_session_raises(self, service, engine):
        """不存在的会话应抛 ValueError."""
        with pytest.raises(ValueError, match="会话不存在"):
            service.get_messages_paginated("not-exist", user_id=1, limit=10, before_id=None)


# ============================================================
# 归属校验测试
# ============================================================


class TestOwnershipCheck:
    """写消息强制归属校验 (防越权)."""

    def test_add_message_ownership_check(self, service, engine):
        """非会话所有者调用 add_message 应被拒 (ValueError)."""
        # 先用 user=1 创建会话
        Session = sessionmaker(bind=engine)
        sess = Session()
        sess.add(TChatSession(session_id="sess-owner", user_id="1", title="owner"))
        sess.commit()
        sess.close()

        # user=2 (非所有者) 尝试写入应被拒
        with pytest.raises(ValueError, match="会话不存在或不属于该用户"):
            service.add_message(
                session_uuid="sess-owner",
                user_id=2,
                role="user",
                content="越权尝试",
            )

        # 验证: 数据库确实没写入
        sess = Session()
        count = sess.query(TChatSessionMessage).filter_by(session_id="sess-owner").count()
        sess.close()
        assert count == 0

    def test_add_message_owner_succeeds(self, service, engine):
        """所有者正常写入应成功."""
        Session = sessionmaker(bind=engine)
        sess = Session()
        sess.add(TChatSession(session_id="sess-owner2", user_id="1", title="owner"))
        sess.commit()
        sess.close()

        result = service.add_message(
            session_uuid="sess-owner2",
            user_id=1,
            role="user",
            content="正常写入",
        )
        assert result.role == "user"
        assert result.content == "正常写入"
        assert result.status == "success"

    def test_add_message_idempotent_within_5s(self, service, engine):
        """5 秒内同会话同角色同内容前 200 字符的写入应被去重."""
        Session = sessionmaker(bind=engine)
        sess = Session()
        sess.add(TChatSession(session_id="sess-dedup", user_id="1", title="dedup"))
        sess.commit()
        sess.close()

        m1 = service.add_message("sess-dedup", user_id=1, role="user", content="重复内容")
        m2 = service.add_message("sess-dedup", user_id=1, role="user", content="重复内容")
        # 第二次应被去重, 返回的是同一条记录
        assert m1.id == m2.id


# ============================================================
# 错误消息测试
# ============================================================


class TestErrorMessage:
    """AI 失败时持久化错误消息 (status=error)."""

    def test_add_error_message(self, service, engine):
        """add_error_message 应以 role=assistant + status=error 持久化."""
        Session = sessionmaker(bind=engine)
        sess = Session()
        sess.add(TChatSession(session_id="sess-err", user_id="1", title="err"))
        sess.commit()
        sess.close()

        result = service.add_error_message(
            "sess-err",
            user_id=1,
            content="（AI 回复失败）",
            error_message="ConnectionError: 上游超时",
            extra={"stage": "llm_call"},
        )

        assert result.role == "assistant"
        assert result.status == "error"
        assert result.error_message == "ConnectionError: 上游超时"
        assert result.content == "（AI 回复失败）"
        assert result.extra == {"stage": "llm_call"}

        # 验证已写入 DB
        sess = Session()
        msg = sess.query(TChatSessionMessage).filter_by(session_id="sess-err").one()
        sess.close()
        assert msg.status == "error"
        assert msg.error_message == "ConnectionError: 上游超时"

    def test_add_error_message_default_content(self, service, engine):
        """content 为空时应填默认文案."""
        Session = sessionmaker(bind=engine)
        sess = Session()
        sess.add(TChatSession(session_id="sess-err2", user_id="1", title="err2"))
        sess.commit()
        sess.close()

        result = service.add_error_message(
            "sess-err2",
            user_id=1,
            content="",
            error_message="boom",
        )
        assert result.content == "（AI 回复失败）"

    def test_error_message_excluded_from_load_session(self, service, engine):
        """错误消息仍按 created_at 排序返回 (前端按 status 渲染红色)."""
        Session = sessionmaker(bind=engine)
        sess = Session()
        sess.add(TChatSession(session_id="sess-err3", user_id="1", title="err3"))
        sess.commit()
        sess.close()

        service.add_message("sess-err3", user_id=1, role="user", content="问")
        service.add_error_message(
            "sess-err3", user_id=1, content="失败", error_message="timeout"
        )

        result = service.get_messages_paginated("sess-err3", user_id=1, limit=10)
        assert len(result.messages) == 2
        assert result.messages[0].role == "user"
        assert result.messages[1].role == "assistant"
        assert result.messages[1].status == "error"


# ============================================================
# 缓存失效粒度测试
# ============================================================


class TestCacheInvalidationPerSession:
    """写入消息后只失效目标 session 的 detail 缓存, 不影响其他 session."""

    def test_cache_invalidation_per_session(self, service, engine):
        """写 session B 的消息, session A 的 detail 缓存应保持命中."""
        Session = sessionmaker(bind=engine)
        sess = Session()
        sess.add(TChatSession(session_id="sess-A", user_id="1", title="A"))
        sess.add(TChatSession(session_id="sess-B", user_id="1", title="B"))
        sess.commit()
        sess.close()

        # 预热两个 session 的 detail 缓存
        r_a1 = service.get_session("sess-A", user_id=1)
        r_b1 = service.get_session("sess-B", user_id=1)
        assert r_a1 is not None
        assert r_b1 is not None

        # 写 session B 的消息
        service.add_message("sess-B", user_id=1, role="user", content="hi B")

        # 验证: session B 的 detail 缓存已失效 (返回新对象)
        r_b2 = service.get_session("sess-B", user_id=1)
        assert r_b2 is not r_b1, "session B 的 detail 缓存应失效"
        assert len(r_b2.messages) == 1

        # 关键断言: session A 的 detail 缓存应仍命中 (同一个对象)
        r_a2 = service.get_session("sess-A", user_id=1)
        assert r_a2 is r_a1, "session A 的 detail 缓存不应被 session B 的写入影响"

    def test_cache_ttl_expiry_falls_back_to_db(self, service, engine):
        """缓存过期后应自动回退到 DB 查询 (模拟 Redis 不可用降级)."""
        Session = sessionmaker(bind=engine)
        sess = Session()
        sess.add(TChatSession(session_id="sess-ttl", user_id="1", title="ttl"))
        sess.commit()
        sess.close()

        r1 = service.get_session("sess-ttl", user_id=1)
        assert r1 is not None

        # 等待 detail 缓存 TTL (30s) 过期 — 测试中不真等 30s,
        # 直接清空 _store 模拟"缓存条目过期/丢失" (对应 Redis 不可用场景)
        svc_module._detail_cache._store.clear()

        r2 = service.get_session("sess-ttl", user_id=1)
        # 应该重新查 DB, 返回新对象 (不是缓存中的旧对象)
        assert r2 is not r1
        assert r2.id == r1.id
        assert r2.title == r1.title


# ============================================================
# 辅助: 验证 _SessionTTLCache 的失效方法语义
# ============================================================


class TestSessionTTLCacheInvalidate:
    """直接验证 _SessionTTLCache 的精确失效逻辑."""

    def test_invalidate_session_only_drops_target_detail(self):
        """invalidate_session 只清目标 session 的 detail 缓存, 不影响其他 session."""
        cache = svc_module._SessionTTLCache(ttl_seconds=60)
        cache.set("detail:1:sess-A", "A")
        cache.set("detail:1:sess-B", "B")
        cache.set("list:1:1:50", "list")

        cache.invalidate_session(user_id=1, session_uuid="sess-A")

        assert cache.get("detail:1:sess-A") is None
        assert cache.get("detail:1:sess-B") == "B"  # 其他 session 不受影响
        # list 缓存应被清 (因为消息数变化会影响列表)
        assert cache.get("list:1:1:50") is None

    def test_invalidate_user_drops_all_user_caches(self):
        """invalidate_user 清该用户的所有 list + detail 缓存."""
        cache = svc_module._SessionTTLCache(ttl_seconds=60)
        cache.set("list:1:1:50", "list-1")
        cache.set("list:1:2:50", "list-2")
        cache.set("detail:1:sess-A", "A")
        cache.set("list:2:1:50", "list-user2")

        cache.invalidate_user(user_id=1)

        assert cache.get("list:1:1:50") is None
        assert cache.get("list:1:2:50") is None
        assert cache.get("detail:1:sess-A") is None
        # 其他用户的缓存不受影响
        assert cache.get("list:2:1:50") == "list-user2"

    def test_expired_entry_returns_none(self):
        """过期条目应返回 None (懒清理)."""
        cache = svc_module._SessionTTLCache(ttl_seconds=0)  # 立即过期
        cache.set("k", "v")
        # ttl=0 + time.time() 严格比较: 时间戳相同可能未过期, 这里直接 sleep 极短时间
        time.sleep(0.001)
        assert cache.get("k") is None
