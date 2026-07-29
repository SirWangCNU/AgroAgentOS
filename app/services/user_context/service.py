"""用户上下文服务 — 聚合各模块数据, 为智能问答提供上下文.

核心职责:
  1. 根据用户查询意图, 按需检索相关模块数据
  2. 将检索结果格式化为结构化文本摘要
  3. 控制注入量, 避免挤占 LLM 上下文窗口
"""

from __future__ import annotations

from loguru import logger
from sqlalchemy.orm import Session

from app.services.user_context.farm_context import build_farm_summary
from app.services.user_context.intent import detect_intent

# 上下文注入量上限 (字符)
_MAX_CONTEXT_CHARS = 6000


class UserContextService:
    """聚合用户各模块数据, 为智能问答提供上下文.

    用法:
        svc = UserContextService(db, user_id=1)
        context = svc.get_context("我A1地块最近作业质量怎么样")
    """

    def __init__(self, db: Session, user_id: int):
        self.db = db
        self.user_id = user_id

    def get_context(self, query: str) -> str:
        """根据用户查询, 返回相关模块数据的结构化摘要.

        Args:
            query: 用户原始问题或改写后的检索 query

        Returns:
            拼接后的上下文文本, 无数据时返回空字符串
        """
        intent = detect_intent(query)
        parts: list[str] = []

        # 1. 农场概况 (默认注入)
        if intent.has_farm:
            farm_ctx = build_farm_summary(self.db, self.user_id)
            if farm_ctx:
                parts.append(farm_ctx)

        # 拼接并截断
        context = "\n\n".join(parts)
        if len(context) > _MAX_CONTEXT_CHARS:
            context = context[:_MAX_CONTEXT_CHARS] + "\n...(数据已截断)"

        if context:
            logger.info(
                f"[UserContext] user={self.user_id} "
                f"farm={intent.has_farm} chars={len(context)}"
            )
        return context


def get_user_context(db: Session, user_id: int, query: str) -> str:
    """便捷函数: 一行调用获取用户上下文.

    Args:
        db: SQLAlchemy Session
        user_id: 用户 ID
        query: 用户查询

    Returns:
        结构化上下文文本
    """
    svc = UserContextService(db, user_id)
    return svc.get_context(query)
