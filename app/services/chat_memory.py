from __future__ import annotations

import asyncio
import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Optional

from loguru import logger

from app.config import settings

_redis_client: Any | None = None
_redis_import_failed = False
_redis_connect_failed_logged = False


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _session_digest(session_id: str) -> str:
    return hashlib.sha256(session_id.encode("utf-8")).hexdigest()[:32]


def _messages_key(session_id: str) -> str:
    return f"rag:chat:{_session_digest(session_id)}:messages"


def _summary_key(session_id: str) -> str:
    return f"rag:chat:{_session_digest(session_id)}:summary"


def _meta_key(session_id: str) -> str:
    return f"rag:chat:{_session_digest(session_id)}:meta"


# Farm Agent 报告共享缓存 (跨 session, 给 RAG Chat 联网判断用)
_DIAGNOSIS_REPORTS_KEY = "rag:diagnosis:reports"
_DIAGNOSIS_REPORTS_MAX = 5
_DIAGNOSIS_REPORT_MAX_CHARS = 8000


def _sanitize_message(raw: Any) -> dict[str, Any] | None:
    if not isinstance(raw, dict):
        return None
    role = raw.get("role")
    content = raw.get("content")
    if role not in {"user", "assistant"} or not isinstance(content, str):
        return None
    return {
        "role": role,
        "content": content,
        "ts": raw.get("ts") or "",
        "rewritten_query": raw.get("rewritten_query") or "",
        "sources": raw.get("sources") or [],
    }


async def _get_redis() -> Any | None:
    global _redis_client, _redis_import_failed, _redis_connect_failed_logged
    if not settings.rag_chat_memory_enabled:
        return None
    if _redis_import_failed:
        return None
    if _redis_client is not None:
        return _redis_client
    try:
        from redis.asyncio import Redis
    except Exception as e:
        _redis_import_failed = True
        logger.warning(f"[chat-memory] redis 包不可用, 会话记忆降级关闭: {e}")
        return None
    try:
        client = Redis.from_url(settings.redis_url, decode_responses=True)
        await client.ping()
        _redis_client = client
        logger.info(f"[chat-memory] Redis 会话记忆已连接: {settings.redis_url}")
        return _redis_client
    except Exception as e:
        if not _redis_connect_failed_logged:
            logger.warning(f"[chat-memory] Redis 连接失败, 会话记忆降级关闭: {type(e).__name__}: {e}")
            _redis_connect_failed_logged = True
        return None


async def is_available() -> bool:
    return await _get_redis() is not None


async def get_messages(session_id: str) -> list[dict[str, Any]]:
    client = await _get_redis()
    if client is None:
        return []
    try:
        rows = await client.lrange(_messages_key(session_id), 0, -1)
        messages: list[dict[str, Any]] = []
        for row in rows:
            try:
                item = _sanitize_message(json.loads(row))
            except Exception:
                item = None
            if item is not None:
                messages.append(item)
        return messages
    except Exception as e:
        logger.warning(f"[chat-memory] 读取消息失败: {type(e).__name__}: {e}")
        return []


async def get_recent_messages(session_id: str, turns: int | None = None) -> list[dict[str, Any]]:
    messages = await get_messages(session_id)
    keep = max(0, (turns or settings.rag_chat_history_turns) * 2)
    if keep <= 0:
        return []
    return messages[-keep:]


async def append_message(
    session_id: str,
    *,
    role: str,
    content: str,
    rewritten_query: str = "",
    sources: list[str] | None = None,
) -> None:
    client = await _get_redis()
    if client is None:
        return
    if role not in {"user", "assistant"}:
        return
    hard_limit = max(settings.rag_chat_max_messages * 4, settings.rag_chat_compact_keep_messages, 20)
    payload = {
        "role": role,
        "content": content[:8000],
        "ts": _now_iso(),
        "rewritten_query": rewritten_query,
        "sources": sources or [],
    }
    try:
        messages_key = _messages_key(session_id)
        summary_key = _summary_key(session_id)
        meta_key = _meta_key(session_id)
        await client.rpush(messages_key, json.dumps(payload, ensure_ascii=False))
        await client.ltrim(messages_key, -hard_limit, -1)
        await client.hset(meta_key, mapping={"session_id": session_id, "updated_at": _now_iso()})
        ttl = max(60, settings.rag_chat_memory_ttl_sec)
        await client.expire(messages_key, ttl)
        await client.expire(summary_key, ttl)
        await client.expire(meta_key, ttl)
    except Exception as e:
        logger.warning(f"[chat-memory] 写入消息失败: {type(e).__name__}: {e}")


async def replace_messages(session_id: str, messages: list[dict[str, Any]]) -> None:
    client = await _get_redis()
    if client is None:
        return
    try:
        key = _messages_key(session_id)
        await client.delete(key)
        if messages:
            rows = [json.dumps(m, ensure_ascii=False) for m in messages]
            await client.rpush(key, *rows)
        await client.expire(key, max(60, settings.rag_chat_memory_ttl_sec))
    except Exception as e:
        logger.warning(f"[chat-memory] 替换消息失败: {type(e).__name__}: {e}")


async def get_summary(session_id: str) -> str:
    client = await _get_redis()
    if client is None:
        return ""
    try:
        value = await client.get(_summary_key(session_id))
        return value or ""
    except Exception as e:
        logger.warning(f"[chat-memory] 读取摘要失败: {type(e).__name__}: {e}")
        return ""


async def set_summary(session_id: str, summary: str) -> None:
    client = await _get_redis()
    if client is None:
        return
    try:
        key = _summary_key(session_id)
        await client.set(key, summary[: settings.rag_chat_summary_max_chars])
        await client.expire(key, max(60, settings.rag_chat_memory_ttl_sec))
    except Exception as e:
        logger.warning(f"[chat-memory] 写入摘要失败: {type(e).__name__}: {e}")


async def clear_session(session_id: str) -> bool:
    client = await _get_redis()
    if client is None:
        return False
    try:
        await client.delete(_messages_key(session_id), _summary_key(session_id), _meta_key(session_id))
        return True
    except Exception as e:
        logger.warning(f"[chat-memory] 清空会话失败: {type(e).__name__}: {e}")
        return False


async def load_session(
    session_id: str, user_id: Optional[int] = None
) -> dict[str, Any]:
    """加载会话记忆 (多级缓存: Redis → DB fallback).

    Args:
        session_id: 会话 UUID
        user_id:    可选. 提供时启用 DB fallback —— Redis miss/TTL 过期时
                    从 SQLite chat_session_messages 表读取最近 N 条消息回填.
                    不提供时仅读 Redis (兼容无 auth 的旧调用方).

    Returns:
        {"summary": str, "messages": list, "recent_messages": list}
    """
    summary = await get_summary(session_id)
    messages = await get_messages(session_id)

    # Redis 未命中或 TTL 过期 → 从 DB 回填 (确保 RAG 上下文不丢失历史)
    if not messages and user_id is not None:
        messages = await _load_messages_from_db(session_id, user_id)
        if messages:
            logger.info(
                f"[chat-memory] Redis miss, 从 DB 回填 {len(messages)} 条消息 "
                f"session={session_id[:8]}..."
            )
            # 回填到 Redis, 下次命中 (best-effort, 失败不影响主流程)
            await _warm_cache_from_db(session_id, messages)

    recent = messages[-max(0, settings.rag_chat_history_turns * 2):]
    return {"summary": summary, "messages": messages, "recent_messages": recent}


async def _load_messages_from_db(
    session_id: str, user_id: int
) -> list[dict[str, Any]]:
    """从 DB (chat_session_messages) 读取最近 N 条消息作为 Redis 缓存 fallback.

    返回的 dict 形状与 Redis 存储的一致: {role, content, ts, rewritten_query, sources}.
    使用 asyncio.to_thread 卸载同步 DB 调用, 避免阻塞事件循环.
    """
    try:
        # 延迟导入避免循环依赖
        from app.services.session_service import session_service

        # 读取最近 N 条 (N = rag_chat_max_messages, 通常 50)
        limit = max(20, settings.rag_chat_max_messages)
        result = await asyncio.to_thread(
            session_service.get_messages_paginated,
            session_id,
            user_id,
            limit=limit,
            before_id=None,
        )
        # 转换 MessageOut → Redis 消息格式
        messages: list[dict[str, Any]] = []
        for msg in result.messages:
            # 跳过错误消息, 不喂给 LLM 上下文
            if msg.status == "error":
                continue
            extra = msg.extra or {}
            messages.append(
                {
                    "role": msg.role,
                    "content": msg.content,
                    "ts": msg.created_at.isoformat() if msg.created_at else "",
                    "rewritten_query": extra.get("rewritten_query", ""),
                    "sources": extra.get("sources", []),
                }
            )
        return messages
    except ValueError as exc:
        # 会话不存在或不属于该用户
        logger.debug(f"[chat-memory] DB fallback 跳过 (会话校验失败): {exc}")
        return []
    except Exception as exc:
        logger.warning(
            f"[chat-memory] DB fallback 读取失败: {type(exc).__name__}: {exc}"
        )
        return []


async def _warm_cache_from_db(
    session_id: str, messages: list[dict[str, Any]]
) -> None:
    """DB fallback 命中后, 把消息回填到 Redis 缓存, 下次直接命中.

    best-effort: 失败仅 warning, 不影响主流程.
    """
    try:
        await replace_messages(session_id, messages)
    except Exception as exc:
        logger.warning(
            f"[chat-memory] 回填 Redis 缓存失败: {type(exc).__name__}: {exc}"
        )


async def append_diagnosis_report(report: str, *, session_id: str | None = None) -> None:
    """Farm Agent 生成的最终报告写到共享 list, 供 RAG Chat 联网判断使用.

    设计:
      - 跨 RAG Chat session 共享 (key 不带 session_id), 因为农场巡检报告的
        session_id 与 RAG Chat 的 'web-chat' 不同, 用全局 list 最简单.
      - 只保留最近 N 份, 避免无限增长.
      - 单份报告内容截断到 8KB, 防止极端情况撑爆 Redis.
    """
    if not report:
        return
    client = await _get_redis()
    if client is None:
        return
    payload = {
        "ts": _now_iso(),
        "session_id": session_id or "",
        "report": report[:_DIAGNOSIS_REPORT_MAX_CHARS],
    }
    try:
        await client.lpush(_DIAGNOSIS_REPORTS_KEY, json.dumps(payload, ensure_ascii=False))
        await client.ltrim(_DIAGNOSIS_REPORTS_KEY, 0, _DIAGNOSIS_REPORTS_MAX - 1)
        await client.expire(_DIAGNOSIS_REPORTS_KEY, max(60, settings.rag_chat_memory_ttl_sec))
    except Exception as e:
        logger.warning(f"[chat-memory] 诊断报告写入失败: {type(e).__name__}: {e}")


async def get_recent_diagnosis_reports(limit: int = 3) -> list[dict[str, Any]]:
    """RAG Chat 联网判断时读取最近若干份 Farm Agent 报告 (按时间倒序).

    Returns:
        list[{"ts": iso, "session_id": str, "report": str}]
    """
    client = await _get_redis()
    if client is None:
        return []
    try:
        rows = await client.lrange(_DIAGNOSIS_REPORTS_KEY, 0, max(0, limit - 1))
        out: list[dict[str, Any]] = []
        for row in rows:
            try:
                item = json.loads(row)
            except Exception:
                continue
            if isinstance(item, dict) and item.get("report"):
                out.append(item)
        return out
    except Exception as e:
        logger.warning(f"[chat-memory] 诊断报告读取失败: {type(e).__name__}: {e}")
        return []
