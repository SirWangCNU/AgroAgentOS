"""对话会话业务逻辑.

设计要点:
  - 持久层: SQLite/MySQL (通过 sqlite_manager 单例访问), 表 chat_sessions + chat_session_messages
  - 缓存层: 进程内按 session_uuid 精确失效的 TTL 缓存 (替代早期版本的全局失效)
  - 隔离:   按 (user_id, session_uuid) 双重隔离; 写消息强制校验归属, 防越权
  - 分页:   游标分页 (before_id), 进入会话默认拉最新 N 条, 向前加载用 oldest_id 作游标
"""

from __future__ import annotations

import time
import uuid
from typing import Any, Optional

from loguru import logger
from sqlalchemy import func

from app.core.sqlite import sqlite_manager
from app.models.session import ChatSession, ChatSessionMessage
from app.schemas.session import (
    MessageOut,
    PaginatedMessagesOut,
    SessionCreate,
    SessionDetailOut,
    SessionListOut,
    SessionOut,
)


# ============================================================
# 进程内 TTL 缓存 (按 session_uuid 精确失效)
# ============================================================

class _SessionTTLCache:
    """按 session_uuid 隔离的 TTL 缓存.

    早期版本 _invalidate_session_caches() 会清空所有用户所有会话的缓存,
    高并发下缓存命中率趋零. 现在按 session_uuid 精确失效,
    写 session A 的消息只清 session A 的缓存, 不影响其他会话.
    """

    def __init__(self, ttl_seconds: int = 30) -> None:
        self._ttl = ttl_seconds
        # key 形如 "list:{user_id}:{page}:{page_size}" 或 "detail:{user_id}:{session_uuid}"
        # value: (timestamp, payload)
        self._store: dict[str, tuple[float, object]] = {}

    def get(self, key: str) -> Optional[object]:
        entry = self._store.get(key)
        if entry and (time.time() - entry[0]) < self._ttl:
            return entry[1]
        if entry:
            # 过期懒清理
            self._store.pop(key, None)
        return None

    def set(self, key: str, value: object) -> None:
        self._store[key] = (time.time(), value)

    def invalidate_session(self, user_id: int, session_uuid: str) -> None:
        """精确失效某个会话的 detail 缓存 + 该用户的 list 缓存.

        - detail 缓存按 session_uuid 精确清, 不影响其他会话
        - list 缓存按 user_id 清 (因为消息数变化会影响列表排序/计数)
        """
        prefix_detail = f"detail:{user_id}:{session_uuid}"
        prefix_list = f"list:{user_id}:"
        keys_to_drop = [
            k for k in list(self._store.keys())
            if k == prefix_detail or k.startswith(prefix_list)
        ]
        for k in keys_to_drop:
            self._store.pop(k, None)

    def invalidate_user(self, user_id: int) -> None:
        """用户的所有缓存失效 (创建/删除会话时调用).

        key 格式:
          - list:   ``list:{user_id}:{page}:{page_size}``
          - detail: ``detail:{user_id}:{session_uuid}``

        必须用前缀精确匹配 ``list:{user_id}:`` / ``detail:{user_id}:``,
        而不是 ``:{user_id}:`` 子串匹配 — 否则 user=1 的失效会误清
        ``list:2:1:50`` (user=2 的列表缓存, 子串 ``:1:`` 也命中).
        """
        list_prefix = f"list:{user_id}:"
        detail_prefix = f"detail:{user_id}:"
        keys_to_drop = [
            k for k in list(self._store.keys())
            if k.startswith(list_prefix) or k.startswith(detail_prefix)
        ]
        for k in keys_to_drop:
            self._store.pop(k, None)


# list 缓存 5s (会话列表变更频率低); detail 缓存 30s (含消息, 命中率高)
_list_cache = _SessionTTLCache(ttl_seconds=5)
_detail_cache = _SessionTTLCache(ttl_seconds=30)


class SessionService:
    """对话会话管理服务."""

    # ============================================================
    # 会话 CRUD
    # ============================================================

    def create_session(self, user_id: int, data: SessionCreate) -> SessionOut:
        """创建新会话."""
        session_uuid = str(uuid.uuid4())
        with sqlite_manager.session() as sess:
            session = ChatSession(
                session_id=session_uuid,
                user_id=str(user_id),
                title=data.title,
            )
            sess.add(session)
            sess.flush()
            result = SessionOut(
                id=session.session_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                message_count=0,
            )
        _list_cache.invalidate_user(user_id)
        return result

    def list_sessions(
        self, user_id: int, page: int = 1, page_size: int = 50
    ) -> SessionListOut:
        """获取用户会话列表.

        使用 LEFT JOIN + GROUP BY 子查询一次完成, 避免早期版本的 N+1 查询.
        """
        cache_key = f"list:{user_id}:{page}:{page_size}"
        cached = _list_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"[sessions] list 缓存命中: {cache_key}")
            return cached  # type: ignore[return-value]

        with sqlite_manager.session() as sess:
            msg_count_subq = (
                sess.query(
                    ChatSessionMessage.session_id.label("session_id"),
                    func.count(ChatSessionMessage.id).label("msg_count"),
                )
                .group_by(ChatSessionMessage.session_id)
                .subquery()
            )

            query = (
                sess.query(
                    ChatSession,
                    func.coalesce(msg_count_subq.c.msg_count, 0).label("msg_count"),
                )
                .outerjoin(
                    msg_count_subq,
                    ChatSession.session_id == msg_count_subq.c.session_id,
                )
                .filter(ChatSession.user_id == str(user_id))
                .order_by(ChatSession.updated_at.desc())
            )
            total = query.count()
            rows = query.offset((page - 1) * page_size).limit(page_size).all()

            result = SessionListOut(
                sessions=[
                    SessionOut(
                        id=s.session_id,
                        title=s.title,
                        created_at=s.created_at,
                        updated_at=s.updated_at,
                        message_count=msg_count or 0,
                    )
                    for s, msg_count in rows
                ],
                total=total,
            )
        _list_cache.set(cache_key, result)
        return result

    def get_session(self, session_uuid: str, user_id: int) -> Optional[SessionDetailOut]:
        """获取会话详情 (含全部消息).

        注意: 此接口返回所有消息, 适合会话首次进入时小数据量场景.
        大数据量场景请使用 get_messages_paginated 游标分页.
        """
        cache_key = f"detail:{user_id}:{session_uuid}"
        cached = _detail_cache.get(cache_key)
        if cached is not None:
            logger.debug(f"[sessions] detail 缓存命中: {cache_key}")
            return cached  # type: ignore[return-value]

        with sqlite_manager.session() as sess:
            session = (
                sess.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_uuid,
                    ChatSession.user_id == str(user_id),
                )
                .first()
            )
            if not session:
                return None

            messages = (
                sess.query(ChatSessionMessage)
                .filter(ChatSessionMessage.session_id == session.session_id)
                .order_by(ChatSessionMessage.created_at.asc())
                .all()
            )

            result = SessionDetailOut(
                id=session.session_id,
                title=session.title,
                created_at=session.created_at,
                updated_at=session.updated_at,
                messages=[self._msg_to_out(m) for m in messages],
            )
        _detail_cache.set(cache_key, result)
        return result

    def update_session(
        self, session_uuid: str, user_id: int, data
    ) -> bool:
        """更新会话标题."""
        with sqlite_manager.session() as sess:
            session = (
                sess.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_uuid,
                    ChatSession.user_id == str(user_id),
                )
                .first()
            )
            if not session:
                return False
            session.title = data.title
        _detail_cache.invalidate_session(user_id, session_uuid)
        _list_cache.invalidate_user(user_id)
        return True

    def delete_session(self, session_uuid: str, user_id: int) -> bool:
        """删除会话.

        chat_session_messages.session_id 外键带 ondelete=CASCADE,
        但 SQLite 的 PRAGMA foreign_keys=ON 已在 connect 时启用,
        这里仍手动先删消息做防御性兜底 (兼容老数据/不同 DB).
        """
        with sqlite_manager.session() as sess:
            session = (
                sess.query(ChatSession)
                .filter(
                    ChatSession.session_id == session_uuid,
                    ChatSession.user_id == str(user_id),
                )
                .first()
            )
            if not session:
                return False
            sess.query(ChatSessionMessage).filter(
                ChatSessionMessage.session_id == session.session_id
            ).delete()
            sess.delete(session)
        _detail_cache.invalidate_session(user_id, session_uuid)
        _list_cache.invalidate_user(user_id)
        return True

    # ============================================================
    # 消息持久化 (含归属校验 + 错误消息)
    # ============================================================

    def add_message(
        self,
        session_uuid: str,
        user_id: int,
        role: str,
        content: str,
        image_url: Optional[str] = None,
        extra: Optional[dict[str, Any]] = None,
        status: str = "success",
        error_message: Optional[str] = None,
    ) -> MessageOut:
        """向会话添加消息.

        安全: 强制校验 session_uuid 属于 user_id, 防止越权写入他人会话.
        幂等: 若最近 5 秒内已存在相同 (session_id, role, content[:200]) 的消息, 跳过写入.
              用于前端 fire-and-forget + 后端 SSE 兜底持久化的双写去重.
        """
        with sqlite_manager.session() as sess:
            session = sess.query(ChatSession).filter(
                ChatSession.session_id == session_uuid,
                ChatSession.user_id == str(user_id),  # 强制归属校验
            ).first()
            if not session:
                raise ValueError(f"会话不存在或不属于该用户: session_uuid={session_uuid} user_id={user_id}")

            # 幂等去重: 同会话同角色同内容前 200 字符 + 5 秒内
            content_key = (content or "")[:200]
            recent_dup = (
                sess.query(ChatSessionMessage)
                .filter(
                    ChatSessionMessage.session_id == session.session_id,
                    ChatSessionMessage.role == role,
                    ChatSessionMessage.content.like(f"{content_key}%"),
                )
                .order_by(ChatSessionMessage.created_at.desc())
                .first()
            )
            if recent_dup and recent_dup.created_at:
                # created_at 是带时区的 datetime; 用 timestamp 比较秒数
                age_sec = (time.time() - recent_dup.created_at.timestamp()) if recent_dup.created_at.tzinfo else 0
                if age_sec < 5:
                    logger.debug(
                        f"[sessions] 幂等去重命中, 跳过写入 session={session_uuid} role={role}"
                    )
                    return self._msg_to_out(recent_dup)

            msg = ChatSessionMessage(
                session_id=session.session_id,
                role=role,
                content=content,
                image_url=image_url,
                status=status,
                error_message=error_message,
            )
            if extra:
                msg.set_extra(extra)
            sess.add(msg)
            sess.flush()

            result = self._msg_to_out(msg)
        # 写入新消息后失效该 session 的 detail 缓存 + 用户的 list 缓存
        _detail_cache.invalidate_session(user_id, session_uuid)
        _list_cache.invalidate_user(user_id)
        return result

    def add_error_message(
        self,
        session_uuid: str,
        user_id: int,
        *,
        content: str,
        error_message: str,
        extra: Optional[dict[str, Any]] = None,
    ) -> MessageOut:
        """AI 回复失败时持久化 assistant 错误消息.

        role=assistant, status=error, error_message=具体异常.
        前端按 status 字段区分渲染 (红色错误样式).
        """
        return self.add_message(
            session_uuid=session_uuid,
            user_id=user_id,
            role="assistant",
            content=content or "（AI 回复失败）",
            extra=extra,
            status="error",
            error_message=error_message,
        )

    def auto_title_from_message(self, session_uuid: str, user_id: int, content: str) -> None:
        """用第一条用户消息自动设置会话标题."""
        title = content[:30].strip()
        if len(content) > 30:
            title += "..."
        with sqlite_manager.session() as sess:
            session = sess.query(ChatSession).filter(
                ChatSession.session_id == session_uuid,
                ChatSession.user_id == str(user_id),
            ).first()
            if session and session.title == "新对话":
                session.title = title
        _detail_cache.invalidate_session(user_id, session_uuid)
        _list_cache.invalidate_user(user_id)

    # ============================================================
    # 分页查询
    # ============================================================

    def get_messages_paginated(
        self,
        session_uuid: str,
        user_id: int,
        *,
        limit: int = 10,
        before_id: Optional[int] = None,
    ) -> PaginatedMessagesOut:
        """游标分页查询会话消息.

        用法:
          - 首次进入会话: limit=10, before_id=None → 返回最新 10 条 (正序)
          - 向前加载更多: limit=10, before_id=<上次返回的 oldest_id>

        Returns:
            PaginatedMessagesOut: messages 按时间正序排列 (oldest -> newest),
                                  has_more 标记是否还有更早消息,
                                  oldest_id 作为下次向前加载的游标.

        Raises:
            ValueError: 会话不存在或不属于该用户.
        """
        # limit 上限保护, 防恶意请求拉满消息
        limit = max(1, min(limit, 50))

        with sqlite_manager.session() as sess:
            session = sess.query(ChatSession).filter(
                ChatSession.session_id == session_uuid,
                ChatSession.user_id == str(user_id),
            ).first()
            if not session:
                raise ValueError(
                    f"会话不存在或不属于该用户: session_uuid={session_uuid} user_id={user_id}"
                )

            query = sess.query(ChatSessionMessage).filter(
                ChatSessionMessage.session_id == session.session_id
            )
            if before_id is not None:
                query = query.filter(ChatSessionMessage.id < before_id)

            # 多取 1 条用于判断 has_more
            rows = (
                query.order_by(ChatSessionMessage.id.desc())
                .limit(limit + 1)
                .all()
            )

            has_more = len(rows) > limit
            page_rows = rows[:limit]
            # 反转为正序 (oldest -> newest), 前端直接 append 显示
            page_rows.reverse()

            oldest_id = page_rows[0].id if page_rows else None

            return PaginatedMessagesOut(
                messages=[self._msg_to_out(m) for m in page_rows],
                has_more=has_more,
                oldest_id=oldest_id,
            )

    # ============================================================
    # 辅助方法
    # ============================================================

    def _msg_to_out(self, msg: ChatSessionMessage) -> MessageOut:
        """ORM 消息转 MessageOut schema."""
        return MessageOut(
            id=msg.id,
            role=msg.role,
            content=msg.content,
            image_url=msg.image_url,
            status=getattr(msg, "status", None) or "success",
            error_message=getattr(msg, "error_message", None),
            extra=getattr(msg, "extra", None) or {},
            created_at=msg.created_at,
        )


session_service = SessionService()
