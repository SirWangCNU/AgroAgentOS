"""对话会话 ORM 模型."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from loguru import logger
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func

from app.core.sqlite import Base


class ChatSession(Base):
    """对话会话."""

    __tablename__ = "chat_sessions"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(128), nullable=False, unique=True, index=True)
    user_id = Column(String(128), nullable=True)
    title = Column(String(256), default="新对话")
    created_at = Column(DateTime, default=func.now(), nullable=False)
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now(), nullable=False)
    extra_json = Column(Text, nullable=True)

    @property
    def extra(self) -> dict[str, Any]:
        """解析 extra_json 字段为 dict (遵循 _json 后缀属性约定)."""
        if not self.extra_json:
            return {}
        try:
            return json.loads(self.extra_json)
        except Exception:
            return {}

    def set_extra(self, data: dict[str, Any]) -> None:
        """设置 extra_json 字段."""
        self.extra_json = json.dumps(data, ensure_ascii=False, default=str)


class ChatSessionMessage(Base):
    """会话消息.

    status 字段语义:
      - success: 正常完成的 user / assistant 消息
      - error:   AI 回复失败时持久化的 assistant 错误消息 (error_message 存具体异常)
      - partial: 流式中断但已有部分内容 (兜底场景, 当前未启用)
    """

    __tablename__ = "chat_session_messages"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String(128), ForeignKey("chat_sessions.session_id", ondelete="CASCADE"), nullable=False, index=True
    )
    role = Column(String(20), nullable=False)  # user / assistant
    content = Column(Text, nullable=False)
    image_url = Column(String(500), nullable=True)  # 图片 URL (可选)
    status = Column(String(16), nullable=False, default="success")  # success / error / partial
    error_message = Column(Text, nullable=True)  # AI 失败时的错误信息 (仅 status=error 有值)
    extra_json = Column(Text, nullable=True)  # tokens/sources/rewritten_query 等元数据
    created_at = Column(DateTime, default=func.now())

    @property
    def extra(self) -> dict[str, Any]:
        """解析 extra_json 字段为 dict (遵循 _json 后缀属性约定)."""
        if not self.extra_json:
            return {}
        try:
            return json.loads(self.extra_json)
        except Exception as exc:
            logger.warning("解析 ChatSessionMessage.extra_json 失败，返回空对象: {}", exc)
            return {}

    def set_extra(self, data: dict[str, Any]) -> None:
        """设置 extra_json 字段."""
        self.extra_json = json.dumps(data, ensure_ascii=False, default=str)