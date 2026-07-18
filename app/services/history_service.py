"""诊断历史记录服务 (SQLite-based).

存储结构:
  - SQLite Table: history_records (record_id, question, answer, source, session_id, skill, ...)

设计:
  - 持久化存储，永久保留历史记录
  - 新写入来源: farm_agent/chat/monitoring；历史 aiops 记录保持可读
  - 单条回答截断到 12KB, 防极端情况撑爆数据库
  - 使用 SQLiteManager 进行数据操作
  - 单条记录最大 12KB
  - 支持手动上传到 RAG 知识库 (Milvus)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from app.core.history_source import (
    HistoryWriteSource,
    validate_history_write_source,
)
from app.core.sqlite import sqlite_manager

_MAX_ANSWER_CHARS = 12000


async def add_record(
    *,
    question: str,
    answer: str = "",
    source: HistoryWriteSource = "chat",
    session_id: str = "",
    skill: str = "",
    sources: list[str] | None = None,
    extra: dict[str, Any] | None = None,
) -> str | None:
    """写入一条历史记录, 返回 record_id (失败返回 None)."""
    source = validate_history_write_source(source)
    if not question:
        return None

    record_id = uuid.uuid4().hex[:16]
    try:
        sqlite_manager.save_history_record(
            record_id=record_id,
            question=question[:2000],
            answer=(answer or "")[:_MAX_ANSWER_CHARS],
            source=source,
            session_id=session_id,
            skill=skill,
            sources=sources or [],
            extra=extra,
        )
        logger.info(f"[history] 记录已保存 id={record_id} source={source} q={question[:60]}...")
        return record_id
    except Exception as e:
        logger.warning(f"[history] 写入失败: {type(e).__name__}: {e}")
        return None


async def upload_record_to_kb(record_id: str) -> bool:
    """将历史记录上传到 RAG 知识库 (Milvus 向量库).

    由用户在诊断完成后手动调用此接口上传到知识库。

    格式化为 Markdown 文档，包含问答案例，便于后续 RAG 检索。

    Returns:
        True if uploaded successfully, False otherwise.
    """
    try:
        # 向量库依赖只在显式上传时加载，普通历史查询不应依赖 RAG 运行环境。
        from app.core.vector_store import get_vector_store
        from app.utils.splitter import split_markdown

        record = sqlite_manager.get_history_record(record_id)
        if not record:
            logger.warning(f"[history] 记录不存在 record_id={record_id}")
            return False

        if not record.answer or len(record.answer) < 50:
            logger.warning(f"[history] 记录没有有效报告 record_id={record_id}")
            return False

        title = f"【诊断记录】{record.skill or '通用'} - {record.question[:50]}..."
        content = f"""# {title}

## 问题
{record.question}

## 诊断报告
{record.answer}

---
来源: 智能运维诊断系统
记录ID: {record_id}
时间: {record.created_at.strftime('%Y-%m-%d %H:%M:%S UTC') if record.created_at else 'N/A'}
"""
        chunks = split_markdown(content, source=f"diagnosis:{record_id}")
        if not chunks:
            logger.warning(f"[history] 诊断报告分块为空 record_id={record_id}")
            return False

        for chunk in chunks:
            chunk.metadata.setdefault("h1", "")
            chunk.metadata.setdefault("h2", "")
            chunk.metadata.setdefault("h3", "")

        vs = get_vector_store()
        vs.add_documents(chunks)

        sqlite_manager.update_history_kb_uploaded(record_id, True)
        logger.info(f"[history] 诊断报告已上传知识库 record_id={record_id}, chunks={len(chunks)}")
        return True

    except Exception as e:
        logger.warning(f"[history] 上传知识库失败 record_id={record_id}: {type(e).__name__}: {e}")
        return False


async def list_records(
    *,
    page: int = 1,
    page_size: int = 20,
    source: str | None = None,
) -> dict[str, Any]:
    """分页查询历史记录 (时间倒序).

    Returns:
        {"total": int, "page": int, "page_size": int, "records": [...]}
    """
    try:
        records, total = sqlite_manager.get_history_records(
            page=page, page_size=page_size, source=source
        )

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "records": [_to_dict(r) for r in records],
        }
    except Exception as e:
        logger.warning(f"[history] 查询失败: {type(e).__name__}: {e}")
        return {"total": 0, "page": page, "page_size": page_size, "records": []}


async def get_record(record_id: str) -> dict[str, Any] | None:
    """获取单条记录详情."""
    try:
        record = sqlite_manager.get_history_record(record_id)
        if record is None:
            return None
        return _to_dict(record)
    except Exception as e:
        logger.warning(f"[history] 读取记录失败: {type(e).__name__}: {e}")
        return None


async def delete_record(record_id: str) -> bool:
    """删除单条记录."""
    try:
        return sqlite_manager.delete_history_record(record_id)
    except Exception as e:
        logger.warning(f"[history] 删除记录失败: {type(e).__name__}: {e}")
        return False


async def clear_records(source: str | None = None) -> int:
    """清空历史记录, 返回删除数量."""
    try:
        return sqlite_manager.clear_history_records(source=source)
    except Exception as e:
        logger.warning(f"[history] 清空失败: {type(e).__name__}: {e}")
        return 0


def _to_dict(record: Any) -> dict[str, Any]:
    """将 HistoryRecord 模型转成前端可用的 dict."""
    return {
        "id": record.record_id,
        "question": record.question,
        "answer": record.answer or "",
        "source": record.source,
        "session_id": record.session_id or "",
        "skill": record.skill or "",
        "sources": record.sources,
        "knowledge_base_uploaded": bool(getattr(record, "knowledge_base_uploaded", 0)),
        "ts": record.created_at.timestamp() if record.created_at else 0,
        "ts_iso": record.created_at.isoformat() if record.created_at else "",
    }
