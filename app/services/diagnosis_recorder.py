"""诊断记录管理器 (DiagnosisRecorder).

负责将诊断过程和结果记录到历史记录中，使用 SQLite 轻量化数据库存储。

核心功能:
  - record_diagnosis: 保存诊断结果
  - record_conversation: 保存对话历史
  - list_records: 分页查询记录
  - get_record: 获取单条记录
  - delete_record: 删除记录

设计原则:
  - 模块化设计，便于被其他脚本调用
  - 高可维护性，统一的数据模型和接口
  - 支持异步操作，兼容 FastAPI
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

from loguru import logger

from app.core.sqlite import sqlite_manager, HistoryRecord


class RecordType(str, Enum):
    """记录类型枚举."""
    DIAGNOSIS = "diagnosis"  # 诊断结果
    CONVERSATION = "conversation"  # 对话历史
    BOTH = "both"  # 诊断结果和对话


class DiagnosisRecorder:
    """诊断记录管理器.

    提供统一的接口来记录和查询诊断相关的所有信息。
    """

    def __init__(self):
        self._max_question_length = 2000
        self._max_answer_length = 12000

    async def record_diagnosis(
        self,
        *,
        question: str,
        answer: str = "",
        source: str = "aiops",
        session_id: str = "",
        skill: str = "",
        sources: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> str | None:
        """保存诊断结果到历史记录.

        Args:
            question: 用户问题或诊断查询
            answer: 诊断结果或回答
            source: 来源 (aiops/chat/monitoring)
            session_id: 会话 ID
            skill: 使用的技能名称
            sources: 参考来源列表
            extra: 额外信息

        Returns:
            record_id: 成功返回记录 ID，失败返回 None
        """
        if not question:
            logger.warning("[recorder] question 为空，跳过记录")
            return None

        record_id = uuid.uuid4().hex[:16]
        try:
            sqlite_manager.save_history_record(
                record_id=record_id,
                question=question[: self._max_question_length],
                answer=answer[: self._max_answer_length] if answer else "",
                source=source,
                session_id=session_id,
                skill=skill,
                sources=sources or [],
                extra=extra,
            )
            logger.info(
                f"[recorder] 诊断记录已保存: id={record_id}, source={source}, "
                f"q={question[:60]}..."
            )
            return record_id
        except Exception as e:
            logger.warning(f"[recorder] 保存诊断记录失败: {type(e).__name__}: {e}")
            return None

    async def record_conversation(
        self,
        *,
        session_id: str,
        user_message: str,
        assistant_response: str,
        source: str = "chat",
        skill: str = "",
        extra: dict[str, Any] | None = None,
    ) -> str | None:
        """保存对话历史到历史记录.

        Args:
            session_id: 会话 ID
            user_message: 用户消息
            assistant_response: 助手回复
            source: 来源
            skill: 技能名称
            extra: 额外信息

        Returns:
            record_id: 成功返回记录 ID，失败返回 None
        """
        if not user_message:
            logger.warning("[recorder] user_message 为空，跳过记录")
            return None

        record_id = uuid.uuid4().hex[:16]
        try:
            # 组装成完整的问答对
            full_content = f"用户: {user_message}\n\n助手: {assistant_response}"

            sqlite_manager.save_history_record(
                record_id=record_id,
                question=user_message[: self._max_question_length],
                answer=full_content[: self._max_answer_length],
                source=source,
                session_id=session_id,
                skill=skill,
                extra=extra,
            )
            logger.info(
                f"[recorder] 对话记录已保存: id={record_id}, session={session_id}"
            )
            return record_id
        except Exception as e:
            logger.warning(f"[recorder] 保存对话记录失败: {type(e).__name__}: {e}")
            return None

    async def list_records(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        source: str | None = None,
    ) -> dict[str, Any]:
        """分页查询历史记录 (时间倒序).

        Args:
            page: 页码，从 1 开始
            page_size: 每页数量，最大 100
            source: 按来源筛选

        Returns:
            {"total": int, "page": int, "page_size": int, "records": [...]}
        """
        try:
            records, total = sqlite_manager.get_history_records(
                page=page,
                page_size=min(page_size, 100),
                source=source,
            )
            return {
                "total": total,
                "page": page,
                "page_size": page_size,
                "records": [self._record_to_dict(r) for r in records],
            }
        except Exception as e:
            logger.warning(f"[recorder] 查询记录失败: {type(e).__name__}: {e}")
            return {"total": 0, "page": page, "page_size": page_size, "records": []}

    async def get_record(self, record_id: str) -> dict[str, Any] | None:
        """获取单条记录详情.

        Args:
            record_id: 记录 ID

        Returns:
            记录详情 dict，不存在返回 None
        """
        try:
            record = sqlite_manager.get_history_record(record_id)
            if record is None:
                return None
            return self._record_to_dict(record)
        except Exception as e:
            logger.warning(f"[recorder] 获取记录失败: {type(e).__name__}: {e}")
            return None

    async def delete_record(self, record_id: str) -> bool:
        """删除单条记录.

        Args:
            record_id: 记录 ID

        Returns:
            删除成功返回 True，失败返回 False
        """
        try:
            return sqlite_manager.delete_history_record(record_id)
        except Exception as e:
            logger.warning(f"[recorder] 删除记录失败: {type(e).__name__}: {e}")
            return False

    async def clear_records(self, source: str | None = None) -> int:
        """清空历史记录.

        Args:
            source: 按来源筛选清空

        Returns:
            删除的记录数量
        """
        try:
            return sqlite_manager.clear_history_records(source=source)
        except Exception as e:
            logger.warning(f"[recorder] 清空记录失败: {type(e).__name__}: {e}")
            return 0

    async def get_records_by_session(self, session_id: str) -> list[dict[str, Any]]:
        """根据 session_id 获取所有相关记录.

        Args:
            session_id: 会话 ID

        Returns:
            该会话的所有记录列表
        """
        try:
            records, _ = sqlite_manager.get_history_records(
                page=1,
                page_size=1000,  # 获取所有
                source=None,
            )
            # 过滤指定 session_id 的记录
            filtered = [r for r in records if r.session_id == session_id]
            return [self._record_to_dict(r) for r in filtered]
        except Exception as e:
            logger.warning(f"[recorder] 获取会话记录失败: {type(e).__name__}: {e}")
            return []

    def _record_to_dict(self, record: HistoryRecord) -> dict[str, Any]:
        """将 HistoryRecord 模型转成前端可用的 dict."""
        return {
            "id": record.record_id,
            "question": record.question,
            "answer": record.answer or "",
            "source": record.source,
            "session_id": record.session_id or "",
            "skill": record.skill or "",
            "sources": record.sources,
            "knowledge_base_uploaded": bool(
                getattr(record, "knowledge_base_uploaded", 0)
            ),
            "ts": record.created_at.timestamp() if record.created_at else 0,
            "ts_iso": record.created_at.isoformat() if record.created_at else "",
        }


# 模块级单例，便于其他模块导入使用
diagnosis_recorder = DiagnosisRecorder()
